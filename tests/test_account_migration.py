import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor


MIGRATION = Path(__file__).resolve().parents[1] / "config" / "supabase_accounts.sql"
MAX_PAYLOAD_BYTES = 20 * 1024 * 1024


def postgres_tools():
    configured = os.environ.get("PG_BINDIR")
    directories = [Path(configured)] if configured else []
    located = shutil.which("initdb")
    if located:
        directories.append(Path(located).parent)
    for root in (Path("/opt/homebrew/opt"), Path("/usr/local/opt")):
        directories.extend(root.glob("postgresql*/bin"))
    directories.extend(Path("/usr/lib/postgresql").glob("*/bin"))
    for directory in directories:
        tools = {name: directory / name for name in ("initdb", "pg_ctl", "psql")}
        if all(path.is_file() and os.access(path, os.X_OK) for path in tools.values()):
            return tools
    return None


class AccountMigrationStructureTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MIGRATION.is_file(), "The private-account SQL migration is missing")
        self.sql = MIGRATION.read_text()
        self.normalized = " ".join(self.sql.lower().split())

    def test_table_contract_and_bounds(self):
        for fragment in (
            "create table if not exists public.job_hunter_accounts",
            "owner_id text primary key",
            "revision bigint not null",
            "encrypted_payload text",
            "updated_at timestamptz not null",
            "revision > 0",
            "^[0-9a-f]{64}$",
            str(MAX_PAYLOAD_BYTES),
        ):
            self.assertIn(fragment, self.normalized)

    def test_only_service_role_gets_table_and_rpc_privileges(self):
        self.assertIn("enable row level security", self.normalized)
        self.assertIn(
            "revoke all on table public.job_hunter_accounts from public, anon, authenticated, service_role",
            self.normalized,
        )
        self.assertIn(
            "grant select, insert, update on table public.job_hunter_accounts to service_role",
            self.normalized,
        )
        for signature in ("job_hunter_load(text)", "job_hunter_save(text, bigint, text)"):
            self.assertIn(
                f"revoke all on function public.{signature} from public, anon, authenticated, service_role",
                self.normalized,
            )
            self.assertIn(f"grant execute on function public.{signature} to service_role", self.normalized)
        self.assertNotRegex(self.normalized, r"grant\s+delete\b|create\s+policy\b")

    def test_functions_are_invokers_with_empty_search_path(self):
        self.assertEqual(self.normalized.count("security invoker"), 2)
        self.assertEqual(self.normalized.count("set search_path = ''"), 2)
        self.assertNotIn("security definer", self.normalized)
        self.assertIn("pg_catalog.jsonb_build_object", self.normalized)
        self.assertIn("pg_catalog.octet_length", self.normalized)

    def test_compare_and_swap_and_tombstones_are_explicit(self):
        self.assertIn("on conflict (owner_id) do nothing", self.normalized)
        self.assertIn("account.revision = p_expected_revision", self.normalized)
        self.assertIn("revision = account.revision + 1", self.normalized)
        self.assertIn("encrypted_payload = p_payload", self.normalized)
        self.assertIn("raise sqlstate 'pt409'", self.normalized)
        self.assertNotRegex(self.normalized, r"\bdelete\s+from\b|\btruncate\b")

    def test_rpc_validation_and_error_messages_do_not_echo_inputs(self):
        self.assertEqual(self.normalized.count("p_owner_id is null"), 2)
        self.assertIn("p_expected_revision is null", self.normalized)
        self.assertIn("p_expected_revision < 0", self.normalized)
        self.assertIn("p_expected_revision >= 9223372036854775807", self.normalized)
        self.assertIn("raise sqlstate 'pt400'", self.normalized)
        self.assertNotRegex(self.normalized, r"\b(detail|hint)\s*=")
        for message in re.findall(r"message\s*=\s*'([^']*)'", self.sql, re.I):
            self.assertNotIn("%", message)
        self.assertTrue(self.normalized.startswith("begin;"))
        self.assertTrue(self.normalized.endswith("commit;"))


class AccountMigrationPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = postgres_tools()
        if cls.tools is None:
            if os.environ.get("REQUIRE_ACCOUNT_SQL_TESTS") == "1":
                raise AssertionError("Account SQL tests require PostgreSQL tools in CI")
            raise unittest.SkipTest("No local PostgreSQL tools; functional SQL is unverified")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            if os.environ.get("REQUIRE_ACCOUNT_SQL_TESTS") == "1":
                raise AssertionError("Account SQL tests require a non-root CI user")
            raise unittest.SkipTest("Disposable PostgreSQL must not run as root")
        cls.directory = tempfile.TemporaryDirectory(prefix="jhpg-", dir="/tmp")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.data = cls.root / "data"
        cls.env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
        cls.env["PGCONNECT_TIMEOUT"] = "5"
        subprocess.run(
            [str(cls.tools["initdb"]), "-D", str(cls.data), "-A", "trust", "--no-locale",
             "-E", "UTF8", "-U", "migration_test_owner"],
            env=cls.env, check=True, capture_output=True, text=True, timeout=60,
        )
        cls.addClassCleanup(cls.stop_cluster)
        subprocess.run(
            [str(cls.tools["pg_ctl"]), "-D", str(cls.data), "-l", str(cls.root / "server.log"),
             "-o", f"-F -k {cls.root} -p 55439 -c listen_addresses=''", "-w", "start"],
            env=cls.env, check=True, capture_output=True, text=True, timeout=60,
        )
        cls.run_sql(
            "CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; "
            "CREATE ROLE service_role NOLOGIN BYPASSRLS; CREATE ROLE migration_outsider NOLOGIN;"
        )
        cls.run_sql(MIGRATION.read_text())

    @classmethod
    def stop_cluster(cls):
        subprocess.run(
            [str(cls.tools["pg_ctl"]), "-D", str(cls.data), "-m", "immediate", "-w", "stop"],
            env=cls.env, capture_output=True, text=True, timeout=30,
        )

    @classmethod
    def run_sql(cls, sql, *, role=None, check=True):
        prefix = f"SET ROLE {role};\n" if role else ""
        result = subprocess.run(
            [str(cls.tools["psql"]), "-X", "-q", "-t", "-A", "-h", str(cls.root),
             "-p", "55439", "-U", "migration_test_owner", "-d", "postgres",
             "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose"],
            input=prefix + sql, env=cls.env, capture_output=True, text=True, timeout=20,
        )
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result

    def setUp(self):
        self.run_sql("TRUNCATE public.job_hunter_accounts;")
        self.owner = hashlib.sha256(self.id().encode()).hexdigest()

    def rpc(self, expression):
        return json.loads(self.run_sql(f"SELECT {expression};", role="service_role").stdout)

    def save(self, revision, payload="'ciphertext'"):
        return self.rpc(f"public.job_hunter_save('{self.owner}', {revision}, {payload})")

    def assert_rejected(self, expression, code):
        result = self.run_sql(f"SELECT {expression};", role="service_role", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(code, result.stderr)

    def test_absent_insert_update_and_owner_isolation(self):
        self.assertEqual(self.rpc(f"public.job_hunter_load('{self.owner}')"), {"revision": 0, "payload": None})
        self.assertEqual(self.save(0), {"revision": 1})
        self.assertEqual(self.save(1, "'replacement'"), {"revision": 2})
        self.assertEqual(self.rpc(f"public.job_hunter_load('{self.owner}')"), {"revision": 2, "payload": "replacement"})
        self.assertEqual(self.rpc(f"public.job_hunter_load('{hashlib.sha256(b'other').hexdigest()}')"),
                         {"revision": 0, "payload": None})

    def test_stale_insert_update_and_missing_update_conflict(self):
        self.assert_rejected(f"public.job_hunter_save('{self.owner}', 1, 'secret')", "PT409")
        self.save(0)
        for revision in (0, 2):
            self.assert_rejected(f"public.job_hunter_save('{self.owner}', {revision}, 'secret')", "PT409")
        self.assertEqual(self.rpc(f"public.job_hunter_load('{self.owner}')"), {"revision": 1, "payload": "ciphertext"})

    def test_clear_retains_revision_and_cannot_be_undone_by_stale_tabs(self):
        self.save(0)
        self.assertEqual(self.save(1, "NULL"), {"revision": 2})
        for revision in (0, 1):
            self.assert_rejected(f"public.job_hunter_save('{self.owner}', {revision}, 'old CV')", "PT409")
        self.assertEqual(self.rpc(f"public.job_hunter_load('{self.owner}')"), {"revision": 2, "payload": None})
        self.assertEqual(self.save(2), {"revision": 3})

    def test_initial_clear_also_creates_a_tombstone(self):
        self.assertEqual(self.save(0, "NULL"), {"revision": 1})
        self.assert_rejected(f"public.job_hunter_save('{self.owner}', 0, 'old CV')", "PT409")

    def test_invalid_owners_revisions_and_payload_sizes(self):
        for owner in ("NULL", "''", "'A' || repeat('a', 63)", "repeat('a', 63)", "repeat('a', 65)", "repeat('g', 64)"):
            for name, arguments in (("load", owner), ("save", f"{owner}, 0, 'ciphertext'")):
                self.assert_rejected(f"public.job_hunter_{name}({arguments})", "PT400")
        for revision in ("NULL", "-1", "9223372036854775807"):
            self.assert_rejected(f"public.job_hunter_save('{self.owner}', {revision}, 'ciphertext')", "PT400")
        for payload in ("''", f"repeat('a', {MAX_PAYLOAD_BYTES + 1})", f"repeat(chr(233), {MAX_PAYLOAD_BYTES // 2 + 1})"):
            self.assert_rejected(f"public.job_hunter_save('{self.owner}', 0, {payload})", "PT400")
        self.assertEqual(self.save(0, f"repeat('a', {MAX_PAYLOAD_BYTES})"), {"revision": 1})

    def test_privileges_rls_and_function_execution_configuration(self):
        for role in ("anon", "authenticated", "migration_outsider"):
            for sql in (
                "SELECT * FROM public.job_hunter_accounts;",
                f"SELECT public.job_hunter_load('{self.owner}');",
                f"SELECT public.job_hunter_save('{self.owner}', 0, 'ciphertext');",
                f"INSERT INTO public.job_hunter_accounts VALUES ('{self.owner}', 1, 'ciphertext', now());",
                "UPDATE public.job_hunter_accounts SET encrypted_payload = NULL;",
                "DELETE FROM public.job_hunter_accounts;",
            ):
                result = self.run_sql(sql, role=role, check=False)
                self.assertNotEqual(result.returncode, 0, (role, sql))
                self.assertIn("42501", result.stderr)
        self.save(0)
        denied = self.run_sql("DELETE FROM public.job_hunter_accounts;", role="service_role", check=False)
        self.assertIn("42501", denied.stderr)
        self.assertEqual(self.run_sql("SELECT relrowsecurity FROM pg_class WHERE oid = 'public.job_hunter_accounts'::regclass;").stdout.strip(), "t")
        settings = self.run_sql("SELECT bool_and(NOT prosecdef AND proconfig = ARRAY['search_path=\"\"']) FROM pg_proc WHERE oid IN ('public.job_hunter_load(text)'::regprocedure, 'public.job_hunter_save(text,bigint,text)'::regprocedure);")
        self.assertEqual(settings.stdout.strip(), "t")

    def test_migration_is_repeatable_without_erasing_data(self):
        self.save(0)
        self.run_sql(MIGRATION.read_text())
        self.assertEqual(self.rpc(f"public.job_hunter_load('{self.owner}')"), {"revision": 1, "payload": "ciphertext"})

    def test_concurrent_insert_update_and_clear_have_one_winner(self):
        for initial_revision, payloads in ((0, ("'first'", "'second'")), (1, ("'new CV'", "NULL"))):
            self.run_sql("TRUNCATE public.job_hunter_accounts;")
            if initial_revision:
                self.save(0)
            barrier = threading.Barrier(2)

            def writer(payload):
                barrier.wait(timeout=5)
                return self.run_sql(
                    f"SELECT public.job_hunter_save('{self.owner}', {initial_revision}, {payload});",
                    role="service_role", check=False,
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(writer, payloads))
            self.assertEqual(sum(result.returncode == 0 for result in results), 1)
            self.assertIn("PT409", next(result.stderr for result in results if result.returncode))
            winner = next(result for result in results if not result.returncode)
            self.assertEqual(json.loads(winner.stdout), {"revision": initial_revision + 1})
            loaded = self.rpc(f"public.job_hunter_load('{self.owner}')")
            self.assertEqual(loaded["revision"], initial_revision + 1)
            self.assertIn(loaded["payload"], ("first", "second") if not initial_revision else ("new CV", None))
