BEGIN;

CREATE TABLE IF NOT EXISTS public.job_hunter_accounts (
    owner_id text PRIMARY KEY
        CHECK (pg_catalog.octet_length(owner_id) = 64 AND owner_id ~ '^[0-9a-f]{64}$'),
    revision bigint NOT NULL CHECK (revision > 0),
    encrypted_payload text
        CHECK (encrypted_payload IS NULL OR pg_catalog.octet_length(encrypted_payload) BETWEEN 1 AND 20971520),
    updated_at timestamptz NOT NULL DEFAULT pg_catalog.now()
);

ALTER TABLE public.job_hunter_accounts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.job_hunter_accounts FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.job_hunter_accounts TO service_role;

CREATE OR REPLACE FUNCTION public.job_hunter_load(p_owner_id text)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $function$
DECLARE
    result jsonb;
BEGIN
    IF p_owner_id IS NULL OR pg_catalog.octet_length(p_owner_id) <> 64
        OR p_owner_id !~ '^[0-9a-f]{64}$' THEN
        RAISE SQLSTATE 'PT400' USING MESSAGE = 'Invalid account owner.';
    END IF;

    SELECT pg_catalog.jsonb_build_object('revision', account.revision, 'payload', account.encrypted_payload)
        INTO result
        FROM public.job_hunter_accounts AS account
        WHERE account.owner_id = p_owner_id;

    IF FOUND THEN
        RETURN result;
    END IF;
    RETURN pg_catalog.jsonb_build_object('revision', 0, 'payload', NULL);
END;
$function$;

CREATE OR REPLACE FUNCTION public.job_hunter_save(
    p_owner_id text,
    p_expected_revision bigint,
    p_payload text
)
RETURNS jsonb
LANGUAGE plpgsql
VOLATILE
SECURITY INVOKER
SET search_path = ''
AS $function$
DECLARE
    next_revision bigint;
BEGIN
    IF p_owner_id IS NULL OR pg_catalog.octet_length(p_owner_id) <> 64
        OR p_owner_id !~ '^[0-9a-f]{64}$' THEN
        RAISE SQLSTATE 'PT400' USING MESSAGE = 'Invalid account owner.';
    END IF;
    IF p_expected_revision IS NULL OR p_expected_revision < 0
        OR p_expected_revision >= 9223372036854775807 THEN
        RAISE SQLSTATE 'PT400' USING MESSAGE = 'Invalid account revision.';
    END IF;
    IF p_payload IS NOT NULL AND
        (pg_catalog.octet_length(p_payload) = 0 OR pg_catalog.octet_length(p_payload) > 20971520) THEN
        RAISE SQLSTATE 'PT400' USING MESSAGE = 'Invalid account payload size.';
    END IF;

    -- Keep NULL payload rows: deleting a row would let a stale revision-zero tab restore it.
    IF p_expected_revision = 0 THEN
        INSERT INTO public.job_hunter_accounts AS account (owner_id, revision, encrypted_payload)
            VALUES (p_owner_id, 1, p_payload)
            ON CONFLICT (owner_id) DO NOTHING
            RETURNING account.revision INTO next_revision;
    ELSE
        UPDATE public.job_hunter_accounts AS account
            SET revision = account.revision + 1,
                encrypted_payload = p_payload,
                updated_at = pg_catalog.now()
            WHERE account.owner_id = p_owner_id AND account.revision = p_expected_revision
            RETURNING account.revision INTO next_revision;
    END IF;

    IF NOT FOUND THEN
        RAISE SQLSTATE 'PT409' USING MESSAGE = 'Account revision conflict.';
    END IF;
    RETURN pg_catalog.jsonb_build_object('revision', next_revision);
END;
$function$;

REVOKE ALL ON FUNCTION public.job_hunter_load(text) FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.job_hunter_save(text, bigint, text) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.job_hunter_load(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.job_hunter_save(text, bigint, text) TO service_role;

COMMIT;
