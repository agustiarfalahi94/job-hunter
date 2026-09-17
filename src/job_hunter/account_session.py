"""Account restore/save lifecycle independent of Streamlit and background work."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

from job_hunter.account_config import AccountConfig, AccountIdentity
from job_hunter.account_snapshot import RestoredAccount, SnapshotError, decode_snapshot, encode_snapshot
from job_hunter.account_store import AccountConflict, AccountStorageError, SupabaseAccountStore
from job_hunter.session_workspace import SessionWorkspace


class AccountSession:
    def __init__(self, identity: AccountIdentity, config: AccountConfig, store: SupabaseAccountStore) -> None:
        self.identity = identity
        self.config = config
        self.store = store
        self.ready = False
        self.load_attempted = False
        self.conflicted = False
        self.revision: int | None = None
        self.error = ""
        self.message = "Private account ready."
        self._saved_digest = ""

    def restore(self) -> RestoredAccount:
        self.load_attempted = True
        self.ready = False
        try:
            stored = self.store.load(self.identity)
            content = self._empty_payload() if stored.payload is None else stored.payload
            restored = decode_snapshot(self.identity.owner_id, content)
            canonical = encode_snapshot(self.identity.owner_id, restored.workspace, restored.settings, restored.mode)
        except (AccountStorageError, SnapshotError) as exc:
            self.error = str(exc)
            self.revision = None
            raise
        self.revision = stored.revision
        self._saved_digest = _digest(canonical)
        self.ready = True
        self.conflicted = False
        self.error = ""
        self.message = "Saved account data loaded." if stored.payload else "Private account ready. No saved data."
        return restored

    def flush(self, workspace: SessionWorkspace, settings: dict[str, object], mode: str, *, retry: bool = False) -> bool:
        if not self.ready or self.conflicted or (self.error and not retry):
            return False
        try:
            content = encode_snapshot(self.identity.owner_id, workspace, settings, mode)
            digest = _digest(content)
            if digest == self._saved_digest:
                self.error = ""
                return False
            revision = self.store.save(self.identity, self.revision, content)
        except AccountConflict as exc:
            self.conflicted = True
            self.error = str(exc)
            return False
        except (AccountStorageError, SnapshotError) as exc:
            self.error = str(exc)
            return False
        self.revision = revision
        self._saved_digest = digest
        self.error = ""
        self.message = f"Saved to your account at {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC."
        return True

    def clear(self) -> RestoredAccount:
        if not self.ready or self.conflicted or self.revision is None:
            raise AccountStorageError("Reload saved account data before deleting it.")
        try:
            revision = self.store.clear(self.identity, self.revision)
        except AccountConflict as exc:
            self.conflicted = True
            self.error = str(exc)
            raise
        except AccountStorageError as exc:
            self.error = str(exc)
            raise
        content = self._empty_payload()
        self.revision = revision
        self._saved_digest = _digest(content)
        self.error = ""
        self.message = "Saved account data deleted."
        return decode_snapshot(self.identity.owner_id, content)

    def _empty_payload(self) -> str:
        return encode_snapshot(self.identity.owner_id, SessionWorkspace(), {}, "Criteria-based search")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
