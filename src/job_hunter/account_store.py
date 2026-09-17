"""Server-only encrypted Supabase RPC adapter with revision-aware writes."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import Callable

from cryptography.fernet import Fernet, InvalidToken
import requests

from job_hunter.account_config import AccountConfig, AccountIdentity
from job_hunter.account_snapshot import MAX_SNAPSHOT_BYTES


class AccountStorageError(RuntimeError):
    pass


class AccountConflict(AccountStorageError):
    pass


@dataclass(frozen=True)
class StoredAccount:
    revision: int
    payload: str | None = field(repr=False)


class SupabaseAccountStore:
    def __init__(self, config: AccountConfig, *, post: Callable = requests.post) -> None:
        self._config = config
        self._post = post
        self._cipher = Fernet(config.encryption_key.encode())

    def load(self, identity: AccountIdentity) -> StoredAccount:
        body = self._rpc(identity, "job_hunter_load", {"p_owner_id": identity.owner_id})
        revision = _revision(body)
        if "payload" not in body:
            raise AccountStorageError("Account storage returned incomplete data; nothing has been replaced.")
        token = body.get("payload")
        if token is None:
            return StoredAccount(revision, None)
        if not isinstance(token, str) or revision == 0 or len(token) > 20 * 1024 * 1024:
            raise AccountStorageError("Account storage returned invalid data; nothing has been replaced.")
        try:
            content = self._cipher.decrypt(token.encode("ascii"))
            if len(content) > MAX_SNAPSHOT_BYTES:
                raise ValueError()
            return StoredAccount(revision, content.decode("utf-8"))
        except (InvalidToken, ValueError, UnicodeError):
            raise AccountStorageError("Saved account data cannot be decrypted. Check the original encryption key; do not replace it.") from None

    def save(self, identity: AccountIdentity, revision: int, payload: str) -> int:
        if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise AccountStorageError("Account data exceeds the storage size limit; nothing has been replaced.")
        token = self._cipher.encrypt(payload.encode("utf-8")).decode("ascii")
        return self._write(identity, revision, token)

    def clear(self, identity: AccountIdentity, revision: int) -> int:
        return self._write(identity, revision, None)

    def _write(self, identity: AccountIdentity, revision: int, payload: str | None) -> int:
        if type(revision) is not int or revision < 0:
            raise AccountStorageError("Invalid account revision; reload saved data before continuing.")
        body = self._rpc(identity, "job_hunter_save", {
            "p_owner_id": identity.owner_id, "p_expected_revision": revision, "p_payload": payload,
        })
        saved_revision = _revision(body)
        if saved_revision != revision + 1:
            raise AccountStorageError("Account save could not be confirmed. Reload saved data before continuing.")
        return saved_revision

    def _rpc(self, identity: AccountIdentity, name: str, payload: dict[str, object]) -> dict[str, object]:
        if (not self._config.enabled or identity.email not in self._config.allowed_emails
                or not isinstance(identity.subject, str) or not identity.subject.strip()
                or type(identity.expires_at) not in {int, float}
                or not math.isfinite(identity.expires_at) or identity.expires_at <= time.time()):
            raise AccountStorageError("Account access is not authorized or has expired. Sign in again.")
        try:
            response = self._post(
                f"{self._config.supabase_url}/rest/v1/rpc/{name}", json=payload,
                headers={"apikey": self._config.supabase_secret_key, "Content-Type": "application/json"},
                timeout=(5, 15), allow_redirects=False,
            )
        except requests.RequestException:
            raise AccountStorageError("Private account storage is unreachable. Changes remain unsaved; retry when connectivity returns.") from None
        if response.status_code == 409:
            raise AccountConflict("Saved data changed in another tab. Reload saved data before making more changes.")
        if response.status_code in {401, 403}:
            raise AccountStorageError("Account storage access was denied. Check the server secret key and database grants.")
        if response.status_code == 404:
            raise AccountStorageError("Account storage is not configured. Run the documented Supabase migration.")
        if response.status_code != 200:
            raise AccountStorageError("Private account storage request failed. Changes have not been confirmed saved.")
        try:
            body = response.json()
        except (ValueError, TypeError):
            raise AccountStorageError("Account storage returned an unreadable response; reload before continuing.") from None
        if not isinstance(body, dict):
            raise AccountStorageError("Account storage returned invalid data; reload before continuing.")
        return body


def _revision(body: dict[str, object]) -> int:
    value = body.get("revision")
    if type(value) is not int or not 0 <= value < 2**53:
        raise AccountStorageError("Account storage returned an invalid revision; reload before continuing.")
    return value
