"""Find installed PostgreSQL tools without hardcoding a machine-specific path."""
import os
import shutil
from pathlib import Path


def postgres_tool(name: str, major: str | None = None) -> Path:
    executable = f"{name}.exe" if os.name == "nt" else name
    if configured := os.environ.get("POSTGRES_BIN"):
        candidate = Path(configured) / executable
        if not candidate.is_file():
            raise FileNotFoundError(f"PostgreSQL tool not found: {candidate}")
        return candidate
    if os.name == "nt":
        root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PostgreSQL"
        versions = [p for p in root.glob("*") if p.name.isdigit()]
        for version in sorted(versions, key=lambda p: int(p.name), reverse=True):
            candidate = version / "bin" / executable
            if (major is None or version.name == major) and candidate.is_file():
                return candidate
    if found := shutil.which(executable):
        return Path(found)
    raise FileNotFoundError(f"{name} not found. Install PostgreSQL or set POSTGRES_BIN to its bin directory.")
