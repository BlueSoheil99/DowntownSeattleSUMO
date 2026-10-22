"""SessionStart hook: print HANDOFF.md and the tail of the working log so a new or reset context can resume.

Registered in .claude/settings.json for startup, compact and clear. Standard library only; never raises.
"""
import os
import sys

LOG_TAIL_LINES = 40
LOG_TAIL_CHARS = 6000   # log lines are long (up to ~900 chars); keep the injected text small
WORK_LOG = os.path.join("Simulation", "Work_Done.txt")


def repo_root():
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root and os.path.isdir(root):
        return root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("Session started or context was reset (new session, compaction, or /clear). "
          "Current handoff and recent log follow.")
    root = repo_root()

    print("\n===== HANDOFF.md =====")
    try:
        path = os.path.join(root, "HANDOFF.md")
        if os.path.exists(path):
            print(read(path).rstrip())
        else:
            print(f"HANDOFF.md is missing (looked in {root}).")
    except Exception as e:
        print(f"HANDOFF.md could not be read: {e}")

    print(f"\n===== {WORK_LOG.replace(os.sep, '/')} (last lines, up to {LOG_TAIL_LINES} lines / "
          f"{LOG_TAIL_CHARS} characters) =====")
    try:
        path = os.path.join(root, WORK_LOG)
        if os.path.exists(path):
            lines = read(path).splitlines()[-LOG_TAIL_LINES:]
            while len(lines) > 1 and len("\n".join(lines)) > LOG_TAIL_CHARS:
                lines.pop(0)
            print("\n".join(lines))
        else:
            print(f"Working log is missing (looked for {path}).")
    except Exception as e:
        print(f"Working log could not be read: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"restore_context.py failed: {e}")
    sys.exit(0)
