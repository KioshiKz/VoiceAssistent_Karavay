"""Save the current database as the repository's portable initial snapshot."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import settings
from scripts.postgres_tools import postgres_tool


def main() -> None:
    url = make_url(settings.database_url)
    destination = settings.database_snapshot_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".sql", delete=False) as temp:
        temporary = Path(temp.name)
    try:
        subprocess.run(
            [
                str(postgres_tool("pg_dump")),
                "--host", url.host or "localhost",
                "--port", str(url.port or 5432),
                "--username", url.username or "postgres",
                "--dbname", url.database or "karavay",
                "--no-password", "--no-owner", "--no-privileges", "--no-comments",
                "--schema=public", "--column-inserts", "--rows-per-insert=100",
                "--encoding=UTF8", "--file", str(temporary),
            ],
            env={**os.environ, "PGPASSWORD": url.password or ""},
            check=True,
        )
        # These pg_dump 17/18 additions are psql-only or unavailable on PostgreSQL 16.
        # INSERTs allow asyncpg to restore everything in a single transaction.
        header, schema, body = temporary.read_text(encoding="utf-8").partition("CREATE SCHEMA public;")
        if not schema:
            raise ValueError("The database dump does not contain the public schema.")
        if restriction := re.search(r"(?m)^\\restrict (\S+)\n", header):
            header = header.replace(restriction.group(0), "", 1)
            body = body.replace(f"\\unrestrict {restriction.group(1)}\n", "", 1)
        header = header.replace("SET transaction_timeout = 0;\n", "", 1)
        sql = header + "CREATE SCHEMA IF NOT EXISTS public;" + body
        temporary.write_text(sql, encoding="utf-8", newline="\n")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Database snapshot saved: {destination}")


if __name__ == "__main__":
    main()
