import copy
import hashlib
import unittest

from cryptography.fernet import Fernet

from job_hunter.account_config import (
    AccountAccessError, AccountConfigError, identity_from_claims, load_account_config,
)


def account_secrets():
    return {
        "accounts": {
            "enabled": True, "allowed_emails": ["owner@example.test"],
            "supabase_url": "https://testproject.supabase.co",
            "supabase_secret_key": "sb_secret_test-only-key",
            "encryption_key": Fernet.generate_key().decode(),
        },
        "auth": {
            "redirect_uri": "https://jobs-hunter.streamlit.app/oauth2callback",
            "cookie_secret": "synthetic-cookie-secret-with-at-least-32-chars",
            "google": {
                "client_id": "synthetic.apps.googleusercontent.com",
                "client_secret": "synthetic-client-secret",
                "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
            },
        },
    }


def google_claims(subject="test-subject", email="owner@example.test"):
    return {
        "iss": "https://accounts.google.com", "sub": subject,
        "email": email, "email_verified": True,
        "aud": "synthetic.apps.googleusercontent.com", "exp": 4_000_000_000,
    }


class AccountConfigTest(unittest.TestCase):
    def test_accounts_are_disabled_without_explicit_enablement(self):
        self.assertFalse(load_account_config({}).enabled)
        self.assertFalse(load_account_config({"accounts": {"enabled": False}}).enabled)

    def test_enabled_configuration_requires_every_private_value(self):
        for field in ("allowed_emails", "supabase_url", "supabase_secret_key", "encryption_key"):
            secrets = account_secrets()
            secrets["accounts"].pop(field)
            with self.subTest(field=field), self.assertRaises(AccountConfigError):
                load_account_config(secrets)

    def test_enabled_configuration_requires_google_oauth_setup(self):
        for section, field in (("auth", "redirect_uri"), ("auth", "cookie_secret"), ("google", "client_id"), ("google", "client_secret")):
            secrets = account_secrets()
            (secrets["auth"] if section == "auth" else secrets["auth"]["google"]).pop(field)
            with self.subTest(field=field), self.assertRaises(AccountConfigError):
                load_account_config(secrets)

    def test_configuration_never_reveals_secret_values(self):
        secrets = account_secrets()
        config = load_account_config(secrets)
        for value in (secrets["accounts"]["supabase_secret_key"], secrets["accounts"]["encryption_key"], "synthetic-client-secret"):
            self.assertNotIn(value, repr(config))
        secrets["accounts"]["encryption_key"] = "private-invalid-key"
        with self.assertRaises(AccountConfigError) as raised:
            load_account_config(secrets)
        self.assertNotIn("private-invalid-key", str(raised.exception))

    def test_only_official_https_supabase_endpoint_is_accepted(self):
        for url in ("https://[broken", "http://test.supabase.co", "https://evil.test", "https://test.supabase.co.evil.test", "https://localhost", "https://user:secret@test.supabase.co", "https://test.supabase.co/path", "https://test.supabase.co?key=private", "https://test.supabase.co:444"):
            secrets = account_secrets()
            secrets["accounts"]["supabase_url"] = url
            with self.subTest(url=url), self.assertRaises(AccountConfigError):
                load_account_config(secrets)

    def test_publishable_keys_and_ambiguous_enablement_are_rejected(self):
        for value in ("false", "true", 1, None):
            secrets = account_secrets()
            secrets["accounts"]["enabled"] = value
            with self.subTest(value=value), self.assertRaises(AccountConfigError):
                load_account_config(secrets)
        secrets = account_secrets()
        secrets["accounts"]["supabase_secret_key"] = "sb_publishable_test"
        with self.assertRaises(AccountConfigError):
            load_account_config(secrets)

    def test_google_metadata_and_secure_callback_are_required(self):
        secrets = account_secrets()
        secrets["auth"]["google"]["server_metadata_url"] = "https://evil.test"
        with self.assertRaises(AccountConfigError):
            load_account_config(secrets)
        secrets = account_secrets()
        secrets["auth"]["redirect_uri"] = "http://remote.test/oauth2callback"
        with self.assertRaises(AccountConfigError):
            load_account_config(secrets)

    def test_identity_uses_stable_google_subject_not_email(self):
        secrets = account_secrets()
        secrets["accounts"]["allowed_emails"].append("second@example.test")
        config = load_account_config(secrets)
        first = identity_from_claims(google_claims(), config, now=100)
        renamed = identity_from_claims(google_claims(email="second@example.test"), config, now=100)
        other = identity_from_claims(google_claims(subject="other"), config, now=100)
        self.assertEqual(first.owner_id, renamed.owner_id)
        self.assertNotEqual(first.owner_id, other.owner_id)
        self.assertEqual(first.owner_id, hashlib.sha256(b"https://accounts.google.com\0test-subject").hexdigest())

    def test_google_issuer_variants_share_the_same_owner(self):
        config = load_account_config(account_secrets())
        claims = google_claims()
        first = identity_from_claims(claims, config, now=100)
        claims["iss"] = "accounts.google.com"
        self.assertEqual(first.owner_id, identity_from_claims(claims, config, now=100).owner_id)

    def test_invalid_claims_and_disallowed_accounts_are_denied(self):
        config = load_account_config(account_secrets())
        for field, value in (("iss", "https://evil.test"), ("sub", ""), ("email", "other@example.test"), ("email_verified", False), ("email_verified", "true"), ("aud", "another-client"), ("exp", 99), ("exp", "future"), ("exp", True)):
            claims = google_claims()
            claims[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(AccountAccessError):
                identity_from_claims(claims, config, now=100)

    def test_email_allowlist_comparison_ignores_capitalization(self):
        identity = identity_from_claims(google_claims(email="OWNER@EXAMPLE.TEST"), load_account_config(account_secrets()), now=100)
        self.assertEqual(identity.email, "owner@example.test")

    def test_malformed_issuer_claims_fail_closed(self):
        config = load_account_config(account_secrets())
        for issuer in ([], {}, None):
            claims = google_claims()
            claims["iss"] = issuer
            with self.subTest(issuer=issuer), self.assertRaises(AccountAccessError):
                identity_from_claims(claims, config)


if __name__ == "__main__":
    unittest.main()
