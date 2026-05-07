"""
setup_scheduler.py
------------------
One-time setup. Registers a Windows Task Scheduler task that runs
run_reports.bat on the 1st of every month at 7:00 AM.

HOW TO RUN (run once, then you're done):
  python setup_scheduler.py

TO CHECK IT WAS CREATED:
  python setup_scheduler.py --status

TO REMOVE IT:
  python setup_scheduler.py --delete

NOTES:
  - Task runs even if you're not logged in (SYSTEM account)
  - If the PC is off on the 1st, Task Scheduler runs it as soon as
    the PC is next turned on (MISSED trigger)
  - You can also trigger it manually any time:
    python setup_scheduler.py --run-now
"""

import sys
import subprocess
import pathlib

TASK_NAME = "FinancialReportsMonthly"
ROOT      = pathlib.Path(__file__).parent
BAT_FILE  = ROOT / "run_reports.bat"


def _run(cmd: list[str], capture=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        shell=True,
    )


def create_task():
    """Register the monthly task in Windows Task Scheduler."""
    if not BAT_FILE.exists():
        print(f"  ERROR: run_reports.bat not found at {BAT_FILE}")
        print("  Make sure run_reports.bat exists in the project folder.")
        sys.exit(1)

    print(f"\n  Creating scheduled task: {TASK_NAME}")
    print(f"  Batch file : {BAT_FILE}")
    print(f"  Schedule   : 1st of every month at 7:00 AM")
    print()

    # schtasks command:
    #   /SC MONTHLY        — monthly schedule
    #   /D 1               — on the 1st
    #   /ST 07:00          — at 7:00 AM
    #   /TR                — what to run
    #   /RU SYSTEM         — run as SYSTEM (no login needed)
    #   /RL HIGHEST        — highest privileges
    #   /F                 — force-overwrite if already exists
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{BAT_FILE}"',
        "/SC", "MONTHLY",
        "/D",  "1",
        "/ST", "07:00",
        "/RU", "SYSTEM",
        "/RL", "HIGHEST",
        "/F",
    ]

    result = _run(cmd)

    if result.returncode == 0:
        print("  Task created successfully!")
        print()
        print("  The reports will run automatically on the 1st of each month.")
        print("  You'll receive a summary email when the batch completes.")
        print()
        print("  To verify: python setup_scheduler.py --status")
    else:
        print("  ERROR creating task:")
        print(f"  {result.stderr or result.stdout}")
        print()
        print("  If you see 'Access is denied', run this script as Administrator:")
        print("  Right-click Command Prompt -> 'Run as administrator'")
        print("  Then run: python setup_scheduler.py")


def task_status():
    """Show the current status of the scheduled task."""
    result = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"])

    if result.returncode != 0:
        print(f"\n  Task '{TASK_NAME}' not found.")
        print("  Run: python setup_scheduler.py")
        return

    # Parse key fields from the verbose output
    lines = result.stdout.splitlines()
    fields = ["Task Name", "Status", "Next Run Time", "Last Run Time",
              "Last Result", "Schedule Type", "Start Time", "Days"]

    print(f"\n  Scheduled Task: {TASK_NAME}")
    print("  " + "-" * 54)
    for line in lines:
        for field in fields:
            if line.strip().startswith(field + ":"):
                print(f"  {line.strip()}")
    print()


def delete_task():
    """Remove the scheduled task."""
    print(f"\n  Deleting task: {TASK_NAME}")
    result = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if result.returncode == 0:
        print("  Task deleted.")
    else:
        print(f"  Error: {result.stderr or result.stdout}")


def run_now():
    """Trigger the task to run immediately (for testing)."""
    print(f"\n  Running task now: {TASK_NAME}")
    result = _run(["schtasks", "/Run", "/TN", TASK_NAME])
    if result.returncode == 0:
        print("  Task triggered. Check logs/ for output.")
        print("  You'll receive the summary email when it finishes (~2-5 min).")
    else:
        print(f"  Error: {result.stderr or result.stdout}")
        print("  Make sure the task exists: python setup_scheduler.py --status")


def main():
    args = sys.argv[1:]

    if "--status" in args:
        task_status()
    elif "--delete" in args:
        delete_task()
    elif "--run-now" in args:
        run_now()
    else:
        create_task()


if __name__ == "__main__":
    main()
