-- The database role owns both metadata and analytics in this local demo.
SELECT 'CREATE DATABASE eurostat'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'eurostat')\gexec
\connect eurostat
\i /schema/schema.sql
