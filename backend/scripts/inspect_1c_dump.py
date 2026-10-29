"""Restore a 1C .dt into a NEW local database and export its configuration.

Run with --help. Never points 1C at the application's PostgreSQL database.
Local databases, logs and metadata may contain private data: keep output in .devdata.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def run_platform(platform: Path, args: list[str], log: Path) -> None:
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    result = subprocess.run(
        [str(platform), *args, "/Out", str(log), "/DisableStartupDialogs",
         "/DisableStartupMessages"], startupinfo=startup, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"1C exited with code {result.returncode}; see {log}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("destination", type=Path, help="New, non-existing directory")
    parser.add_argument("--platform", required=True, type=Path, help="Path to 1cv8.exe")
    parser.add_argument("--user", default=os.environ.get("ONEC_USER"),
                        help="1C user name (or ONEC_USER environment variable)")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Retry metadata export for a database restored by this script")
    args = parser.parse_args()
    dump, destination, platform = (p.resolve() for p in (args.dump, args.destination, args.platform))
    if not platform.is_file():
        parser.error("Platform executable not found")
    if dump.suffix.lower() != ".dt" or not dump.is_file():
        parser.error("Expected an existing .dt file")
    with dump.open("rb") as stream:
        if stream.read(9) != b"1CIBDmpF2":
            parser.error("Unsupported 1C dump header")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest_path = destination / "manifest.json"
    if args.metadata_only:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous.get("sha256") != digest or previous.get("status") not in ("restored", "metadata_exported"):
            parser.error("Destination does not contain a successful restore of this dump")
    else:
        # Exclusive creation prevents accidental replacement of an existing database.
        destination.mkdir(parents=True, exist_ok=False)
    manifest = {"source": str(dump), "bytes": dump.stat().st_size,
                "sha256": digest, "platform": str(platform),
                "status": "restored" if args.metadata_only else "started"}
    def save():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    save()
    try:
        database = destination / "database"
        if not args.metadata_only:
            run_platform(platform, ["DESIGNER", "/F", str(database), "/RestoreIB", str(dump)],
                         destination / "restore.log")
        if not (database / "1Cv8.1CD").is_file():
            raise RuntimeError("Restore did not create the database")
        manifest["status"] = "restored"
        save()
        metadata = destination / "metadata"
        metadata.mkdir(exist_ok=args.metadata_only)
        user_args = ["/N", args.user] if args.user else []
        run_platform(platform, ["DESIGNER", "/F", str(database), *user_args,
                                "/DumpConfigToFiles", str(metadata)],
                     destination / "metadata.log")
        if not (metadata / "Configuration.xml").is_file():
            raise RuntimeError("1C did not export Configuration.xml; inspect metadata.log")
        manifest["status"] = "metadata_exported"
    except Exception as exc:
        manifest["error"] = str(exc)
        raise
    finally:
        save()
    print(manifest_path)


if __name__ == "__main__":
    main()
