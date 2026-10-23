"""SessionStart hook: print a short digest of HANDOFF.md and the working log so a new or reset context can resume.

Registered in .claude/settings.json for startup, compact and clear. Standard library only; never raises.

Claude Code shows only the first ~2 KB of hook output in context (the rest goes to a file), so this prints:
  1. the HANDOFF.md title and section 2 (status, sessions, next steps), verbatim
  2. the header lines of the newest Work_Done.txt entries (not the indented detail lines)
  3. a pointer to the full files, which CLAUDE.md tells the session to read
"""
import os
import re
import sys

WORK_LOG = os.path.join("Simulation", "Work_Done.txt")
LOG_HEADERS = 3          # newest dated entries to list
HEADER_CHARS = 110       # log header lines are long; cut each one
SECTION2_WARN = 1800     # warn when section 2 alone would push the digest past the preview


def repo_root():
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root and os.path.isdir(root):
        return root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def section2(text):
    """Title line plus '## 2. ...' up to the next '## ' heading."""
    lines = text.splitlines()
    title = lines[0] if lines and lines[0].startswith("#") else ""
    m = re.search(r"^## 2\..*?(?=^## |\Z)", text, flags=re.S | re.M)
    return title, (m.group(0).rstrip() if m else None)


def log_headers(text):
    """Non-indented, non-empty lines = dated entry headers ('October 22nd: ...')."""
    heads = [l.rstrip() for l in text.splitlines() if re.match(r"^\S", l)]
    out = []
    for h in heads[-LOG_HEADERS:]:
        out.append(h if len(h) <= HEADER_CHARS else h[:HEADER_CHARS].rstrip() + "...")
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    root = repo_root()
    print("Session started or context was reset. Digest below; READ the full HANDOFF.md "
          "before continuing; grep README.md / Work_Done.txt only as needed (see CLAUDE.md).")

    try:
        path = os.path.join(root, "HANDOFF.md")
        if os.path.exists(path):
            title, s2 = section2(read(path))
            if title:
                print(title)
            if s2:
                print(s2)
                if len(s2) > SECTION2_WARN:
                    print(f"[hook] HANDOFF section 2 is {len(s2)} chars; trim it to ~1,500 at the next /handoff.")
            else:
                print("[hook] HANDOFF.md has no '## 2.' section; read the whole file.")
        else:
            print(f"[hook] HANDOFF.md is missing (looked in {root}).")
    except Exception as e:
        print(f"[hook] HANDOFF.md could not be read: {e}")

    try:
        path = os.path.join(root, WORK_LOG)
        if os.path.exists(path):
            print("Newest Work_Done.txt entries (headers only):")
            for h in log_headers(read(path)):
                print("- " + h)
        else:
            print(f"[hook] Working log is missing (looked for {path}).")
    except Exception as e:
        print(f"[hook] Working log could not be read: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"restore_context.py failed: {e}")
    sys.exit(0)
