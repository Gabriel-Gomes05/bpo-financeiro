#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=runtime_user="$APP_DB_USER" \
  --set=runtime_password="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'runtime_user', :'runtime_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_user')
\gexec

SELECT format('ALTER ROLE %I PASSWORD %L', :'runtime_user', :'runtime_password')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'runtime_user')
\gexec

SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'runtime_user')
\gexec

SELECT format('REVOKE CREATE ON SCHEMA public FROM %I', :'runtime_user')
\gexec
SQL
