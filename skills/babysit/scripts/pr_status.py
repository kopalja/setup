#!/usr/bin/env python3
"""Report what a GitHub PR still needs before it can merge; optionally wait for reviews.

Stateless: everything is derived from GitHub, so it is safe to rerun at any time.
A review thread is handled when its last comment contains MARKER. A top-level comment or
review is handled when its id is listed in a `<!-- babysit handled: <id> <id> -->` comment.
"""
import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import time
from urllib.parse import quote

MARKER = "<!-- babysit"
HANDLED = re.compile(r"<!-- babysit handled:([^>]*)-->")
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING = {"PENDING", "EXPECTED", None}
THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          id isResolved isOutdated path line
          comments(first: 50) { nodes { author { login } body url createdAt } }
        }
      }
    }
  }
}"""


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def login(node):
    return (node.get("author") or {}).get("login", "ghost")


def push_time(view):
    """When the head commit was pushed; falls back to its commit date."""
    owner = view["headRepositoryOwner"]["login"]
    repo = view["headRepository"]["name"]
    ref = quote(f"refs/heads/{view['headRefName']}", safe="")
    try:
        for activity in json.loads(gh("api", f"repos/{owner}/{repo}/activity?ref={ref}&per_page=20")):
            if activity.get("after") == view["headRefOid"]:
                return parse_time(activity["timestamp"])
    except (subprocess.CalledProcessError, ValueError, KeyError):
        pass
    return parse_time(view["commits"][-1]["committedDate"])


def fetch(pr):
    fields = ("number,url,state,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,"
              "commits,mergeable,statusCheckRollup,comments,reviews")
    view = json.loads(gh("pr", "view", *([pr] if pr else []), "--json", fields))
    owner, repo = view["url"].split("/")[3:5]
    data = json.loads(gh("api", "graphql", "-f", f"query={THREADS_QUERY}", "-f", f"owner={owner}",
                         "-f", f"repo={repo}", "-F", f"number={view['number']}"))
    threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    return view, threads, push_time(view)


def evaluate(view, threads, pushed, now, window):
    handled = {i for c in view["comments"] for m in HANDLED.findall(c["body"]) for i in m.split()}
    top_level = [
        {"id": c["id"], "kind": "comment", "author": login(c), "body": c["body"], "url": c.get("url"),
         "at": c["createdAt"]}
        for c in view["comments"] if MARKER not in c["body"] and c["id"] not in handled
    ] + [
        {"id": r["id"], "kind": "review", "author": login(r), "state": r["state"], "body": r["body"],
         "at": r.get("submittedAt")}
        for r in view["reviews"] if r["body"].strip() and MARKER not in r["body"] and r["id"] not in handled
    ]
    pending_threads = [
        {"thread_id": t["id"], "path": t["path"], "line": t["line"], "outdated": t["isOutdated"],
         "comments": [{"author": login(c), "body": c["body"], "url": c["url"]} for c in t["comments"]["nodes"]]}
        for t in threads
        if not t["isResolved"] and t["comments"]["nodes"] and MARKER not in t["comments"]["nodes"][-1]["body"]
    ]

    failed, pending = [], []
    for check in view["statusCheckRollup"] or []:
        name = check.get("name") or check.get("context")
        result = check.get("conclusion") or check.get("state")
        if check.get("status") not in (None, "COMPLETED") or result in PENDING:
            pending.append(name)
        elif result in FAILED:
            failed.append({"name": name, "url": check.get("detailsUrl") or check.get("targetUrl")})

    window_left = max(0, int(window - (now - pushed).total_seconds()))
    if view["state"] != "OPEN":
        state = view["state"]
    elif pending_threads or top_level:
        state = "FINDINGS"
    elif view["mergeable"] == "CONFLICTING":
        state = "CONFLICT"
    elif failed:
        state = "CHECKS_FAILED"
    elif window_left or pending or view["mergeable"] != "MERGEABLE":
        state = "WAITING"
    else:
        state = "CLEAN"

    return {
        "state": state,
        "pr": view["url"],
        "base": view["baseRefName"],
        "head": view["headRefOid"],
        "pushed_at": pushed.isoformat(),
        "review_window_left_s": window_left,
        "mergeable": view["mergeable"],
        "checks_pending": pending,
        "checks_failed": failed,
        "threads": pending_threads,
        "top_level": top_level,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pr", nargs="?", help="PR number, URL or branch (default: current branch)")
    parser.add_argument("--wait", action="store_true", help="poll while the state is WAITING")
    parser.add_argument("--window", type=int, default=900, help="review window after a push, seconds")
    parser.add_argument("--max-wait", type=int, default=540, help="stop polling after this many seconds")
    parser.add_argument("--interval", type=int, default=60, help="seconds between polls")
    args = parser.parse_args()

    start = time.monotonic()
    while True:
        report = evaluate(*fetch(args.pr), now=datetime.now(timezone.utc), window=args.window)
        if not args.wait or report["state"] != "WAITING":
            break
        if time.monotonic() - start + args.interval > args.max_wait:
            break
        time.sleep(args.interval)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
