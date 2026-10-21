"""Check that meaningful unit tests catch 12 intentional business-rule regressions.

Only temporary copies are changed. Run from backend/: python check_test_strength.py
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
MUTATIONS = [
    ("remind users too early", "notifications.py", "position <= 2", "position <= 3"),
    ("remind while queue is closed", "notifications.py", "queue_open and position", "position"),
    ("repeat near-front reminders", "notifications.py", ' and not record["closeNotified"]', ""),
    ("mix recipient notifications", "notifications.py", 'if item["recipientId"] == user_id])', 'if True])'),
    ("clear the wrong recipient", "notifications.py", 'item["recipientId"] != user_id', 'item["recipientId"] == user_id'),
    ("record served users as removed", "history.py", '"served": "Served"', '"served": "Removed"'),
    ("lose original join timestamp", "history.py", 'record["completedAt"] = self.clock()', 'record["joinedAt"] = self.clock(); record["completedAt"] = self.clock()'),
    ("exclude start-date midnight", "history.py", 'record["joinedAt"] < start', 'record["joinedAt"] <= start'),
    ("include the next midnight", "history.py", 'record["joinedAt"] >= end', 'record["joinedAt"] > end'),
    ("filter by completion instead of join", "history.py", 'record["joinedAt"] < start', 'record["completedAt"] < start'),
    ("keep partial history after batch failure", "service.py", 'self.history.records, self.notifications.items = previous', 'self.notifications.items = previous[1]'),
    ("reject valid maximum field lengths", "schemas.py", 'max_length=100)', 'max_length=99)'),
]


def run_tests(folder):
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "unit_tests"],
                          cwd=folder, capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def main():
    with tempfile.TemporaryDirectory(prefix="queuesmart-strength-") as temporary:
        folder = Path(temporary)
        shutil.copytree(ROOT / "app", folder / "app", ignore=shutil.ignore_patterns("__pycache__"))
        (folder / "unit_tests").mkdir()
        shutil.copy(ROOT / "tests/test_activity.py", folder / "unit_tests/test_activity.py")
        baseline = run_tests(folder)
        if baseline.returncode:
            raise RuntimeError("Baseline must pass.\n" + baseline.stdout + baseline.stderr)
        caught = 0
        for name, filename, before, after in MUTATIONS:
            target = folder / "app/activity" / filename
            original = target.read_text()
            if before not in original:
                raise RuntimeError("Mutation no longer matches: " + name)
            changed = original.replace(before, after, 1)
            compile(changed, str(target), "exec")
            target.write_text(changed)
            try:
                result = run_tests(folder)
                if result.returncode == 1 and " failed" in result.stdout and "ERROR" not in result.stdout:
                    caught += 1
                    print("Caught: " + name)
                elif result.returncode == 0:
                    print("MISSED: " + name)
                else:
                    raise RuntimeError("Unexpected test failure:\n" + result.stdout + result.stderr)
            finally:
                target.write_text(original)
        print(f"\n{caught}/{len(MUTATIONS)} deliberate business-rule regressions caught.")
        return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
