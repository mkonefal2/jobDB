"""Backup MySQL database.

Usage:
    python scripts/backup_db.py                # mysqldump-based backup
    python scripts/backup_db.py --auto         # backup only if enough time passed since last
    python scripts/backup_db.py --interval 6   # min hours between auto-backups (default: 12)
    python scripts/backup_db.py --list         # list existing backups
    python scripts/backup_db.py --keep 5       # keep only last N backups (default: 10)
    python scripts/backup_db.py --schedule     # register Windows scheduled task (every 6h)
    python scripts/backup_db.py --unschedule   # remove Windows scheduled task
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DATA_DIR, MYSQL_CONFIG

BACKUP_DIR = DATA_DIR / "backups"
TASK_NAME = "JobDB_AutoBackup"


def _latest_backup() -> Path | None:
    """Return the most recent .sql backup, or None."""
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob("jobdb_*.sql"), key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def _needs_backup(interval_hours: float) -> bool:
    """Check if a new backup is needed (time-based)."""
    latest = _latest_backup()
    if latest is None:
        return True

    age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
    if age < timedelta(hours=interval_hours):
        age_h, age_m = age.seconds // 3600, (age.seconds % 3600) // 60
        print(f"Skipping: last backup is {age_h}h {age_m}m old (interval: {interval_hours}h)")
        return False

    return True


def backup_dump() -> Path:
    """Create a mysqldump backup of the database."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"jobdb_{timestamp}.sql"

    cmd = [
        "mysqldump",
        f"--host={MYSQL_CONFIG['host']}",
        f"--port={MYSQL_CONFIG['port']}",
        f"--user={MYSQL_CONFIG['user']}",
        f"--password={MYSQL_CONFIG['password']}",
        "--single-transaction",
        "--routines",
        "--triggers",
        MYSQL_CONFIG["database"],
    ]
    with open(dest, "w", encoding="utf-8") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"mysqldump error: {result.stderr.strip()}")
        dest.unlink(missing_ok=True)
        sys.exit(1)

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"Backup created: {dest}  ({size_mb:.2f} MB)")
    return dest


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
        "schtasks",
        "/Create",
        "/F",
        "/TN",
        TASK_NAME,
        "/TR",
        f'"{python_exe}" "{script_path}" --auto --interval {interval_hours}',
        "/SC",
        "HOURLY",
        "/MO",
        str(interval_hours),
        "/ST",
        "00:00",
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
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"Scheduled task '{TASK_NAME}' removed.")
    else:
        print(f"Failed to remove task: {result.stderr.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup MySQL database")
    parser.add_argument("--auto", action="store_true", help="Only backup if interval passed")
    parser.add_argument("--interval", type=float, default=12, help="Min hours between auto-backups (default: 12)")
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

    if args.auto and not _needs_backup(args.interval):
        return

    backup_dump()

    cleanup_old(keep=args.keep)


if __name__ == "__main__":
    main()
