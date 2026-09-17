import unittest
from unittest.mock import MagicMock

from cryptography.fernet import Fernet
import requests

from job_hunter.account_config import AccountIdentity, identity_from_claims, load_account_config
from job_hunter.account_store import AccountConflict, AccountStorageError, SupabaseAccountStore
from test_account_config import account_secrets, google_claims


def response(body, status=200):
    value = MagicMock()
    value.status_code = status
    value.json.return_value = body
    return value


class AccountStoreTest(unittest.TestCase):
    def setUp(self):
        self.config = load_account_config(account_secrets())
        self.identity = identity_from_claims(google_claims(), self.config)

    def test_save_encrypts_payload_and_returns_atomic_revision(self):
        post = MagicMock(return_value=response({"revision": 1}))
        store = SupabaseAccountStore(self.config, post=post)
        revision = store.save(self.identity, 0, "synthetic-private-cv-and-history")
        self.assertEqual(revision, 1)
        url = post.call_args.args[0]
        options = post.call_args.kwargs
        self.assertTrue(url.endswith("/rest/v1/rpc/job_hunter_save"))
        self.assertEqual(options["json"]["p_owner_id"], self.identity.owner_id)
        self.assertEqual(options["json"]["p_expected_revision"], 0)
        token = options["json"]["p_payload"]
        self.assertNotIn("synthetic-private", token)
        self.assertEqual(Fernet(self.config.encryption_key.encode()).decrypt(token.encode()).decode(), "synthetic-private-cv-and-history")
        self.assertEqual(options["headers"]["apikey"], self.config.supabase_secret_key)
        self.assertNotIn("Authorization", options["headers"])
        self.assertFalse(options["allow_redirects"])
        self.assertEqual(options["timeout"], (5, 15))

    def test_load_decrypts_only_the_selected_account(self):
        encrypted = Fernet(self.config.encryption_key.encode()).encrypt(b"synthetic snapshot").decode()
        post = MagicMock(return_value=response({"revision": 8, "payload": encrypted}))
        loaded = SupabaseAccountStore(self.config, post=post).load(self.identity)
        self.assertEqual((loaded.revision, loaded.payload), (8, "synthetic snapshot"))
        self.assertEqual(post.call_args.kwargs["json"], {"p_owner_id": self.identity.owner_id})

    def test_empty_account_and_clear_tombstone(self):
        post = MagicMock(side_effect=[response({"revision": 0, "payload": None}), response({"revision": 1})])
        store = SupabaseAccountStore(self.config, post=post)
        self.assertIsNone(store.load(self.identity).payload)
        self.assertEqual(store.clear(self.identity, 0), 1)
        self.assertIsNone(post.call_args.kwargs["json"]["p_payload"])

    def test_stale_writes_raise_conflict_without_exposing_provider_body(self):
        post = MagicMock(return_value=response({"message": "private-key-and-cv"}, status=409))
        with self.assertRaises(AccountConflict) as raised:
            SupabaseAccountStore(self.config, post=post).save(self.identity, 5, "private")
        self.assertNotIn("private-key-and-cv", str(raised.exception))

    def test_redirect_auth_service_and_transport_errors_are_safe(self):
        for status in (301, 302, 401, 403, 404, 500):
            post = MagicMock(return_value=response({"message": "private-key-and-cv"}, status))
            with self.subTest(status=status), self.assertRaises(AccountStorageError) as raised:
                SupabaseAccountStore(self.config, post=post).load(self.identity)
            self.assertNotIn("private-key-and-cv", str(raised.exception))
        with self.assertRaises(AccountStorageError) as raised:
            SupabaseAccountStore(self.config, post=MagicMock(side_effect=requests.Timeout("private-key"))).load(self.identity)
        self.assertNotIn("private-key", str(raised.exception))

    def test_invalid_replies_and_wrong_encryption_key_fail_closed(self):
        for body in ({"revision": 3}, {"revision": True, "payload": None}, {"revision": -1, "payload": None}, {"revision": 0, "payload": "cipher"}, {"revision": 1, "payload": "not-cipher"}, [], {}):
            with self.subTest(body=body), self.assertRaises(AccountStorageError):
                SupabaseAccountStore(self.config, post=MagicMock(return_value=response(body))).load(self.identity)
        token = Fernet(Fernet.generate_key()).encrypt(b"private").decode()
        with self.assertRaises(AccountStorageError):
            SupabaseAccountStore(self.config, post=MagicMock(return_value=response({"revision": 1, "payload": token}))).load(self.identity)

    def test_save_revision_must_advance_exactly_once(self):
        with self.assertRaises(AccountStorageError):
            SupabaseAccountStore(self.config, post=MagicMock(return_value=response({"revision": 99}))).save(self.identity, 4, "private")

    def test_nonfinite_identity_never_reaches_storage(self):
        for expiry in (float("nan"), float("inf"), True, "future"):
            post = MagicMock()
            identity = AccountIdentity("test-subject", "owner@example.test", expiry)
            with self.subTest(expiry=expiry), self.assertRaises(AccountStorageError):
                SupabaseAccountStore(self.config, post=post).load(identity)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
