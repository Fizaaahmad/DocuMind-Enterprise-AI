-- NEW demo volume only. Separate roles from the normal production deployment.
CREATE EXTENSION IF NOT EXISTS vector;
DO $$
BEGIN
    EXECUTE format('CREATE ROLE documind_demo_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
                   trim(pg_read_file('/run/secrets/app_password')));
    EXECUTE format('CREATE ROLE documind_demo_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
                   trim(pg_read_file('/run/secrets/migration_password')));
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'Demo role initialization failed (secret values suppressed)';
END $$;
ALTER DATABASE documind_demo OWNER TO documind_demo_migrator;
ALTER SCHEMA public OWNER TO documind_demo_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE documind_demo TO documind_demo_app;
GRANT USAGE ON SCHEMA public TO documind_demo_app;
ALTER DEFAULT PRIVILEGES FOR ROLE documind_demo_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO documind_demo_app;
