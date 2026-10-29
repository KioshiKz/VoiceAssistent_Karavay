"""Restore the bundled snapshot only into an empty database, then run migrations."""
import argparse
import asyncio
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import BACKEND_ROOT, settings
from scripts.postgres_tools import postgres_tool


def start_local_postgres() -> None:
    url = make_url(settings.database_url)
    host, port = url.host or "localhost", url.port or 5432
    if host not in {"localhost", "127.0.0.1", "::1"}:
        print("[postgres] using the configured remote server")
        return
    try:
        with socket.create_connection((host, port), timeout=1):
            print(f"[postgres] already listening on {host}:{port}")
            return
    except OSError:
        pass

    data = BACKEND_ROOT.parent / ".devdata" / "pgdata"
    data.parent.mkdir(parents=True, exist_ok=True)
    major = (data / "PG_VERSION").read_text().strip() if (data / "PG_VERSION").exists() else None
    pg_ctl = postgres_tool("pg_ctl", major)
    if major is None:
        if not url.password:
            raise ValueError("Set a PostgreSQL password in DATABASE_URL before creating a local cluster.")
        with tempfile.TemporaryDirectory() as temp:
            password_file = Path(temp) / "postgres-password"
            password_file.write_text(url.password + "\n", encoding="utf-8")
            subprocess.run(
                [str(pg_ctl.with_name("initdb" + pg_ctl.suffix)), "-D", str(data),
                 "-U", url.username or "postgres", "-A", "scram-sha-256",
                 "--encoding=UTF8", "--locale=C", "--pwfile", str(password_file)],
                check=True,
            )
    print(f"[postgres] starting on {host}:{port}")
    subprocess.run(
        [str(pg_ctl), "-D", str(data), "-l", str(data.parent / "pg.log"),
         "-o", f"-p {port} -h 127.0.0.1,::1", "-w", "start"],
        check=True,
    )


async def restore_snapshot() -> bool:
    url = make_url(settings.database_url).set(drivername="postgresql")
    dsn = url.render_as_string(hide_password=False)
    try:
        connection = await asyncpg.connect(dsn)
    except asyncpg.InvalidCatalogNameError:
        admin = await asyncpg.connect(url.set(database="postgres").render_as_string(hide_password=False))
        try:
            database = (url.database or "karavay").replace('"', '""')
            try:
                await admin.execute(f'CREATE DATABASE "{database}"')
            except asyncpg.DuplicateDatabaseError:
                pass  # Another startup created it while we were connecting.
        finally:
            await admin.close()
        connection = await asyncpg.connect(dsn)
    try:
        async with connection.transaction():
            await connection.execute("SELECT pg_advisory_xact_lock(hashtext('karavay-database-bootstrap'))")
            populated = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f'))"
            )
            if populated:
                print("[database] existing database preserved")
                return False
            snapshot = settings.database_snapshot_path
            print(f"[database] restoring {snapshot}")
            await connection.execute(snapshot.read_text(encoding="utf-8"))
        print("[database] snapshot restored")
        return True
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-local", action="store_true", help="Start or create a local PostgreSQL cluster if needed")
    args = parser.parse_args()
    if args.start_local:
        start_local_postgres()
    asyncio.run(restore_snapshot())
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_ROOT, check=True,
    )


if __name__ == "__main__":
    main()
