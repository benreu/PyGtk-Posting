-- posting_role.sql
--
-- Makes the login posting the owner of this database and of everything
-- Posting keeps in it, creating the login the first time, so that no
-- workstation has to run Posting as the postgres superuser. One login owns
-- every Posting database on the server.
--
-- Posting's SQL window runs whatever is typed into it, and as a superuser
-- that includes COPY ... TO PROGRAM, which is a shell on the database server.
-- The owner of these tables can do everything Posting does, upgrades
-- included, and nothing outside the databases it owns.
--
-- A login belongs to the server, not to a database, so no backup carries it,
-- and pg_restore into a database Posting has just created makes everything
-- belong to whoever restored it. Posting's own restore therefore runs this
-- script itself once the data is in, with the login it asked for. Run it by
-- hand on a database created from the database tools window, or restored any
-- other way.
--
-- Run it as postgres, connected to the database to convert, with Posting
-- closed on every workstation: changing a table's owner locks the table until
-- the end, so it waits behind anyone using it and blocks them meanwhile.
--
--   psql -h 192.168.50.120 -U postgres -d silrep -f src/db/posting_role.sql
--
-- psql asks for the postgres password, then, the first time, for the new
-- login's password, twice. \password sends it hashed, so it is in no server
-- log, no shell history and no command line.
--
-- Run it again whenever the list it prints at the end is not empty. A second
-- run changes nothing that is already right, and leaves an existing password
-- alone.
--
-- Needs PostgreSQL 11 or later.

\set ON_ERROR_STOP on
-- the same name in the DO block below, which psql variables cannot reach
\set posting_role posting

BEGIN;

DO $$
DECLARE
	target name := 'posting';
	item record;
BEGIN
	IF current_setting('server_version_num')::int < 110000 THEN
		RAISE EXCEPTION 'posting_role.sql needs PostgreSQL 11 or later';
	END IF;

	IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = target) THEN
		EXECUTE format('CREATE ROLE %I LOGIN', target);
	END IF;
	-- every run, so a login somebody widened is put back: creating and
	-- restoring databases is done as postgres from the database tools window
	EXECUTE format('ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
					'NOREPLICATION NOBYPASSRLS', target);

	EXECUTE format('ALTER DATABASE %I OWNER TO %I', current_database(), target);
	-- without this every login on the server may connect here
	EXECUTE format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC',
					current_database());

	-- Posting's schemas are every one but the system's. Whatever belongs to an
	-- extension is the extension's business and is left alone throughout.
	-- On PostgreSQL 15 and later public is owned by pg_database_owner, which
	-- already means whoever owns the database.
	FOR item IN
		SELECT n.nspname
		FROM pg_namespace AS n
		WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
		AND pg_get_userbyid(n.nspowner) NOT IN (target, 'pg_database_owner')
		AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
						WHERE (d.classid, d.objid, d.deptype) =
							('pg_namespace'::regclass, n.oid, 'e'))
	LOOP
		EXECUTE format('ALTER SCHEMA %I OWNER TO %I', item.nspname, target);
	END LOOP;

	-- a table takes its indexes and the sequences behind its serial and
	-- identity columns with it
	FOR item IN
		SELECT c.oid::regclass AS relation,
			CASE c.relkind WHEN 'v' THEN 'VIEW'
							WHEN 'm' THEN 'MATERIALIZED VIEW'
							WHEN 'f' THEN 'FOREIGN TABLE'
							ELSE 'TABLE' END AS kind
		FROM pg_class AS c
		JOIN pg_namespace AS n ON n.oid = c.relnamespace
		WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
		AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
		AND pg_get_userbyid(c.relowner) <> target
		AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
						WHERE (d.classid, d.objid, d.deptype) =
							('pg_class'::regclass, c.oid, 'e'))
	LOOP
		EXECUTE format('ALTER %s %s OWNER TO %I', item.kind, item.relation,
						target);
	END LOOP;

	-- only the sequences no column owns: ALTER SEQUENCE refuses those, and the
	-- loop above has already moved them with their tables
	FOR item IN
		SELECT c.oid::regclass AS relation
		FROM pg_class AS c
		JOIN pg_namespace AS n ON n.oid = c.relnamespace
		WHERE c.relkind = 'S'
		AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
		AND pg_get_userbyid(c.relowner) <> target
		AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
						WHERE d.classid = 'pg_class'::regclass
						AND d.objid = c.oid
						AND d.deptype IN ('a', 'i', 'e'))
	LOOP
		EXECUTE format('ALTER SEQUENCE %s OWNER TO %I', item.relation, target);
	END LOOP;

	FOR item IN
		SELECT p.oid::regprocedure AS routine,
			CASE p.prokind WHEN 'p' THEN 'PROCEDURE'
							WHEN 'a' THEN 'AGGREGATE'
							ELSE 'FUNCTION' END AS kind
		FROM pg_proc AS p
		JOIN pg_namespace AS n ON n.oid = p.pronamespace
		WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
		AND pg_get_userbyid(p.proowner) <> target
		AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
						WHERE (d.classid, d.objid, d.deptype) =
							('pg_proc'::regclass, p.oid, 'e'))
	LOOP
		EXECUTE format('ALTER %s %s OWNER TO %I', item.kind, item.routine,
						target);
	END LOOP;

	-- domains, enums, ranges and stand-alone composite types. Array types,
	-- multiranges and a table's row type follow whatever they belong to
	FOR item IN
		SELECT t.oid::regtype AS type_name,
			CASE t.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END AS kind
		FROM pg_type AS t
		JOIN pg_namespace AS n ON n.oid = t.typnamespace
		LEFT JOIN pg_class AS c ON c.oid = t.typrelid
		WHERE (t.typtype IN ('d', 'e', 'r')
				OR (t.typtype = 'c' AND c.relkind = 'c'))
		AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
		AND pg_get_userbyid(t.typowner) <> target
		AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
						WHERE (d.classid, d.objid, d.deptype) =
							('pg_type'::regclass, t.oid, 'e'))
	LOOP
		EXECUTE format('ALTER %s %s OWNER TO %I', item.kind, item.type_name,
						target);
	END LOOP;

	-- before 15, anyone who could connect could create tables in public
	IF current_setting('server_version_num')::int < 150000
			AND EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'public') THEN
		REVOKE CREATE ON SCHEMA public FROM PUBLIC;
	END IF;

	RAISE NOTICE 'Everything Posting keeps in % now belongs to %',
					current_database(), target;
END
$$;

COMMIT;

\echo
\echo 'Anything listed here still belongs to another login, and should not:'
SELECT 'database' AS kind, d.datname::text AS name,
	pg_get_userbyid(d.datdba) AS owner
FROM pg_database AS d
WHERE d.datname = current_database()
AND pg_get_userbyid(d.datdba) <> :'posting_role'
UNION ALL
SELECT 'schema', n.nspname::text, pg_get_userbyid(n.nspowner)
FROM pg_namespace AS n
WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(n.nspowner) NOT IN (:'posting_role', 'pg_database_owner')
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_namespace'::regclass, n.oid, 'e'))
UNION ALL
SELECT 'relation', c.oid::regclass::text, pg_get_userbyid(c.relowner)
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S', 'c')
AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(c.relowner) <> :'posting_role'
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_class'::regclass, c.oid, 'e'))
UNION ALL
SELECT 'routine', p.oid::regprocedure::text, pg_get_userbyid(p.proowner)
FROM pg_proc AS p
JOIN pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(p.proowner) <> :'posting_role'
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_proc'::regclass, p.oid, 'e'))
UNION ALL
SELECT 'type', t.oid::regtype::text, pg_get_userbyid(t.typowner)
FROM pg_type AS t
JOIN pg_namespace AS n ON n.oid = t.typnamespace
WHERE t.typtype IN ('d', 'e', 'r')
AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
AND pg_get_userbyid(t.typowner) <> :'posting_role'
AND NOT EXISTS (SELECT 1 FROM pg_depend AS d
				WHERE (d.classid, d.objid, d.deptype) =
					('pg_type'::regclass, t.oid, 'e'))
ORDER BY 1, 2;

-- the password last, and only when the login has none: an empty answer to
-- \password would not keep the old one, it would clear it
SELECT rolpassword IS NULL AS posting_role_needs_password
FROM pg_authid WHERE rolname = :'posting_role' \gset
\if :posting_role_needs_password
\echo 'Now the password Posting will log in with, as' :posting_role
\password :posting_role
\else
\echo :posting_role 'already has a password, left as it is. To change it, in psql: \\password' :posting_role
\endif
