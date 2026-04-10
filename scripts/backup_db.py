"""Backup DuckDB database.

Usage:
    python scripts/backup_db.py                # copy-based backup (always)
    python scripts/backup_db.py --auto         # backup only if DB changed since last backup
    python scripts/backup_db.py --interval 6   # min hours between auto-backups (default: 12)
    python scripts/backup_db.py --export       # SQL export (portable)
    python scripts/backup_db.py --list         # list existing backups
    python scripts/backup_db.py --keep 5       # keep only last N backups (default: 10)
    python scripts/backup_db.py --schedule     # register Windows scheduled task (every 6h)
    python scripts/backup_db.py --unschedule   # remove Windows scheduled task
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DATA_DIR, DB_PATH

BACKUP_DIR = DATA_DIR / "backups"
TASK_NAME = "JobDB_AutoBackup"


def _db_checksum(db_path: Path) -> str:
    """Fast MD5 checksum of the database file."""
    h = hashlib.md5()
    with open(db_path, "rb") as f:
        while chunk := f.read(1 << 20):  # 1 MB chunks
            h.update(chunk)
    return h.hexdigest()


def _latest_backup() -> Path | None:
    """Return the most recent .duckdb backup, or None."""
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob("jobdb_*.duckdb"), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def _needs_backup(db_path: Path, interval_hours: float) -> bool:
    """Check if a new backup is needed (time + content change)."""
    latest = _latest_backup()
    if latest is None:
        return True

    age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
    if age < timedelta(hours=interval_hours):
        print(f"Skipping: last backup is {age.seconds // 3600}h {(age.seconds % 3600) // 60}m old (interval: {interval_hours}h)")
        return False

    if _db_checksum(db_path) == _db_checksum(latest):
        print("Skipping: database unchanged since last backup.")
        return False

    return True


def backup_copy(db_path: Path = DB_PATH) -> Path:
    """Create a file-level copy of the database."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"jobdb_{timestamp}.duckdb"
    shutil.copy2(db_path, dest)
    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"Backup created: {dest}  ({size_mb:.2f} MB)")
    return dest


def backup_export(db_path: Path = DB_PATH) -> Path:
    """Export database to SQL (schema + data) via DuckDB EXPORT."""
    import duckdb

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = BACKUP_DIR / f"export_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        conn.execute(f"EXPORT DATABASE '{export_dir}' (FORMAT CSV)")
        print(f"SQL export created: {export_dir}")
    finally:
        conn.close()
    return export_dir


def list_backups() -> None:
    """List existing backups sorted by date."""
    if not BACKUP_DIR.exists():
        print("No backups found.")
        return

    items = sorted(BACKUP_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    if not items:
        print("No backups found.")
        return

    print(f"{'Name':<45} {'Size':>10}  {'Date'}")
    print("-" * 75)
    for item in items:
        size = (
            item.stat().st_size / (1024 * 1024)
            if item.is_file()
            else sum(f.stat().st_size for f in item.rglob("*") if f.is_file()) / (1024 * 1024)
        )
        mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{item.name:<45} {size:>8.2f}MB  {mtime}")


def cleanup_old(keep: int = 10) -> None:
    """Remove old backups, keeping only the most recent `keep`."""
    if not BACKUP_DIR.exists():
        return

    items = sorted(BACKUP_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    to_remove = items[keep:]
    for item in to_remove:
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        print(f"Removed old backup: {item.name}")


def schedule_task(interval_hours: int = 6) -> None:
    """Register a Windows scheduled task for auto-backup."""
    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", f'"{python_exe}" "{script_path}" --auto --interval {interval_hours}',
        "/SC", "HOURLY",
        "/MO", str(interval_hours),
        "/ST", "00:00",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Scheduled task '{TASK_NAME}' created (every {interval_hours}h).")
        print(f"  Python: {python_exe}")
        print(f"  Script: {script_path}")
    else:
        print(f"Failed to create task: {result.stderr.strip()}")
        sys.exit(1)


def unschedule_task() -> None:
    """Remove the Windows scheduled task."""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"Scheduled task '{TASK_NAME}' removed.")
    else:
        print(f"Failed to remove task: {result.stderr.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup DuckDB database")
    parser.add_argument("--auto", action="store_true", help="Only backup if DB changed and interval passed")
    parser.add_argument("--interval", type=float, default=12, help="Min hours between auto-backups (default: 12)")
    parser.add_argument("--export", action="store_true", help="SQL export instead of file copy")
    parser.add_argument("--list", action="store_true", help="List existing backups")
    parser.add_argument("--keep", type=int, default=10, help="Keep only last N backups (default: 10)")
    parser.add_argument("--schedule", action="store_true", help="Register Windows scheduled task")
    parser.add_argument("--unschedule", action="store_true", help="Remove Windows scheduled task")
    parser.add_argument("--schedule-interval", type=int, default=6, help="Hours between scheduled runs (default: 6)")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return

    if args.schedule:
        schedule_task(args.schedule_interval)
        return

    if args.unschedule:
        unschedule_task()
        return

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    if args.auto and not _needs_backup(DB_PATH, args.interval):
        return

    if args.export:
        backup_export()
    else:
        backup_copy()

    cleanup_old(keep=args.keep)


if __name__ == "__main__":
    main()
