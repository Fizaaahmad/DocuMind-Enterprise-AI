-- Only used by PostgreSQL on a NEW production volume. Never alters development.
CREATE EXTENSION IF NOT EXISTS vector;
DO $$
BEGIN
    EXECUTE format('CREATE ROLE documind_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
                   trim(pg_read_file('/run/secrets/app_password')));
    EXECUTE format('CREATE ROLE documind_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
                   trim(pg_read_file('/run/secrets/migration_password')));
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'Database role initialization failed (secret values suppressed)';
END $$;
ALTER DATABASE documind OWNER TO documind_migrator;
ALTER SCHEMA public OWNER TO documind_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE documind TO documind_app;
GRANT USAGE ON SCHEMA public TO documind_app;
ALTER DEFAULT PRIVILEGES FOR ROLE documind_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO documind_app;
ALTER DEFAULT PRIVILEGES FOR ROLE documind_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO documind_app;
