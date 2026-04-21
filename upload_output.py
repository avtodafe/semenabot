#!/usr/bin/env python3
"""Upload /tmp/run_out.txt to GitHub repo via API."""
import base64
import json
import os
import subprocess
import sys
from datetime import datetime

TOKEN = os.environ.get("GH_PAT", "")
BRANCH = "claude/seed-parser-bot-qO5Mo"
API = "https://api.github.com/repos/avtodafe/semenabot/contents/roseltorg_run_output.txt"

if not TOKEN:
    print("ERROR: GH_PAT not set")
    sys.exit(1)

src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/run_out.txt"
with open(src, "rb") as f:
    content = base64.b64encode(f.read()).decode()

r = subprocess.run(
    ["curl", "-sf", "-H", f"Authorization: token {TOKEN}", f"{API}?ref={BRANCH}"],
    capture_output=True, text=True,
)
try:
    sha = json.loads(r.stdout).get("sha", "")
except Exception:
    sha = ""

body: dict = {
    "message": f"auto: roseltorg run {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "content": content,
    "branch": BRANCH,
}
if sha:
    body["sha"] = sha

r = subprocess.run(
    ["curl", "-s", "-X", "PUT",
     "-H", f"Authorization: token {TOKEN}",
     "-H", "Content-Type: application/json",
     API, "-d", json.dumps(body)],
    capture_output=True, text=True,
)
try:
    d = json.loads(r.stdout)
    commit_sha = d.get("commit", {}).get("sha", "")
    if commit_sha:
        print("Upload OK:", commit_sha[:12])
    else:
        print("Upload ERR:", d.get("message", "no commit sha"))
        print("Response:", r.stdout[:400])
except Exception as e:
    print("Parse error:", e)
    print("Response:", r.stdout[:400])
