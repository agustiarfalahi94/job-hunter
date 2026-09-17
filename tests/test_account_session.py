import unittest
from unittest.mock import MagicMock

from job_hunter.account_config import identity_from_claims, load_account_config
from job_hunter.account_session import AccountSession
from job_hunter.account_snapshot import encode_snapshot
from job_hunter.account_store import AccountConflict, AccountStorageError, StoredAccount
from job_hunter.session_workspace import SessionWorkspace
from test_account_config import account_secrets, google_claims
from test_account_snapshot import private_workspace, SETTINGS


class AccountSessionTest(unittest.TestCase):
    def test_empty_plaintext_is_invalid_not_a_new_account(self):
        from job_hunter.account_snapshot import SnapshotError
        from job_hunter.account_store import StoredAccount
        from unittest.mock import MagicMock
        config = load_account_config(account_secrets())
        store = MagicMock()
        store.load.return_value = StoredAccount(2, "")
        session = AccountSession(identity_from_claims(google_claims(), config), config, store)
        with self.assertRaises(SnapshotError):
            session.restore()
        self.assertFalse(session.flush(private_workspace(), SETTINGS, "Criteria-based search"))
        store.save.assert_not_called()

    def setUp(self):
        self.config = load_account_config(account_secrets())
        self.identity = identity_from_claims(google_claims(), self.config)
        self.store = MagicMock()
        self.store.load.return_value = StoredAccount(0, None)
        self.store.save.return_value = 1
        self.session = AccountSession(self.identity, self.config, self.store)

    def test_new_account_stays_empty_without_a_write_on_every_rerun(self):
        restored = self.session.restore()
        self.assertTrue(self.session.ready)
        self.assertEqual(self.session.revision, 0)
        self.assertEqual(restored.settings["target_roles"], [])
        self.assertFalse(self.session.flush(restored.workspace, restored.settings, restored.mode))
        self.assertEqual(self.store.save.call_count, 0)

    def test_changed_cv_settings_and_applied_record_save_and_restore(self):
        self.session.restore()
        workspace = private_workspace()
        self.assertTrue(self.session.flush(workspace, SETTINGS, "Criteria-based search"))
        payload = self.store.save.call_args.args[2]
        self.assertEqual(self.session.revision, 1)
        self.assertFalse(self.session.flush(workspace, SETTINGS, "Criteria-based search"))
        self.store.load.return_value = StoredAccount(1, payload)
        restarted = AccountSession(self.identity, self.config, self.store).restore()
        self.assertEqual(restarted.workspace.cv, workspace.cv)
        self.assertEqual(restarted.workspace.list_jobs()[0].application_status, "applied")
        self.assertEqual(restarted.settings["hard_skip_keywords"], ["AZURE"])

    def test_failed_load_cannot_save_or_delete_existing_account(self):
        self.store.load.side_effect = AccountStorageError("Safe unavailable message")
        with self.assertRaises(AccountStorageError):
            self.session.restore()
        self.assertFalse(self.session.ready)
        self.assertFalse(self.session.flush(private_workspace(), SETTINGS, "Criteria-based search", retry=True))
        with self.assertRaises(AccountStorageError):
            self.session.clear()
        self.assertEqual(self.store.save.call_count, 0)
        self.assertEqual(self.store.clear.call_count, 0)

    def test_wrong_owner_snapshot_does_not_replace_saved_data(self):
        self.store.load.return_value = StoredAccount(3, encode_snapshot("b" * 64, private_workspace(), SETTINGS, "CV-based search"))
        with self.assertRaises(ValueError):
            self.session.restore()
        self.assertFalse(self.session.ready)
        self.assertFalse(self.session.flush(SessionWorkspace(), {}, "Criteria-based search"))

    def test_conflict_blocks_further_writes_until_explicit_reload(self):
        self.session.restore()
        self.store.save.side_effect = AccountConflict("Changed in another tab")
        self.assertFalse(self.session.flush(private_workspace(), SETTINGS, "CV-based search"))
        self.assertTrue(self.session.conflicted)
        self.assertFalse(self.session.flush(private_workspace(), SETTINGS, "CV-based search", retry=True))
        self.assertEqual(self.store.save.call_count, 1)
        self.store.save.side_effect = None
        self.store.load.return_value = StoredAccount(5, None)
        self.session.restore()
        self.store.save.return_value = 6
        self.assertTrue(self.session.flush(private_workspace(), SETTINGS, "CV-based search"))
        self.assertEqual(self.session.revision, 6)

    def test_storage_outage_does_not_retry_on_every_fragment_tick(self):
        self.session.restore()
        self.store.save.side_effect = AccountStorageError("Safe offline message")
        workspace = private_workspace()
        self.assertFalse(self.session.flush(workspace, SETTINGS, "CV-based search"))
        self.assertFalse(self.session.flush(workspace, SETTINGS, "CV-based search"))
        self.assertEqual(self.store.save.call_count, 1)
        self.store.save.side_effect = None
        self.assertTrue(self.session.flush(workspace, SETTINGS, "CV-based search", retry=True))
        self.assertEqual(self.store.save.call_count, 2)

    def test_clear_keeps_new_revision_without_immediately_recreating_data(self):
        self.store.load.return_value = StoredAccount(9, encode_snapshot(self.identity.owner_id, private_workspace(), SETTINGS, "CV-based search"))
        self.session.restore()
        self.store.clear.return_value = 10
        restored = self.session.clear()
        self.assertEqual(self.session.revision, 10)
        self.assertIsNone(restored.workspace.cv)
        self.assertEqual(restored.workspace.list_jobs(), [])
        self.assertFalse(self.session.flush(restored.workspace, restored.settings, restored.mode))
        self.assertEqual(self.store.save.call_count, 0)


if __name__ == "__main__":
    unittest.main()
