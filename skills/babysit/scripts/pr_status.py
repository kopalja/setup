#!/usr/bin/env python3
"""Report what a GitHub PR still needs before it can merge; optionally wait for reviews.

Stateless: everything is derived from GitHub, so it is safe to rerun at any time.
A review thread is handled when its last comment is ours and ends with REPLY_MARKER. A top-level
comment or review is handled when its id is listed in a comment of ours that ends with
`<!-- babysit handled: <id> <id> -->`. "Ours" means written by the authenticated gh user.
"""
import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import time
from urllib.parse import quote

REPLY_MARKER = "<!-- babysit -->"
HANDLED = re.compile(r"<!-- babysit handled:([^>]*)-->\s*$")
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING = {"PENDING", "EXPECTED", None}
THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line
          comments(first: 20) { nodes { author { login } body url } }
          latest: comments(last: 1) { nodes { body viewerDidAuthor } }
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
              "commits,mergeable,mergeStateStatus,statusCheckRollup,comments,reviews")
    view = json.loads(gh("pr", "view", *([pr] if pr else []), "--json", fields))
    owner, repo = view["url"].split("/")[3:5]
    threads, after = [], None
    while True:
        args = ["-f", f"query={THREADS_QUERY}", "-f", f"owner={owner}", "-f", f"repo={repo}",
                "-F", f"number={view['number']}", *(["-f", f"after={after}"] if after else [])]
        page = json.loads(gh("api", "graphql", *args))["data"]["repository"]["pullRequest"]["reviewThreads"]
        threads += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return view, threads, push_time(view)
        after = page["pageInfo"]["endCursor"]


def handled_ids(body):
    match = HANDLED.search(body.rstrip())
    return match.group(1).split() if match else None


def is_answered(thread):
    latest = thread["latest"]["nodes"]
    return bool(latest) and latest[0].get("viewerDidAuthor") and latest[0]["body"].rstrip().endswith(REPLY_MARKER)


def evaluate(view, threads, pushed, now, window):
    summaries = [c for c in view["comments"] if c.get("viewerDidAuthor") and handled_ids(c["body"]) is not None]
    summary_ids = {c["id"] for c in summaries}
    handled = {i for c in summaries for i in handled_ids(c["body"])}
    top_level = [
        {"id": c["id"], "kind": "comment", "author": login(c), "body": c["body"], "url": c.get("url"),
         "at": c["createdAt"]}
        for c in view["comments"] if c["id"] not in summary_ids | handled
    ] + [
        {"id": r["id"], "kind": "review", "author": login(r), "state": r["state"], "body": r["body"],
         "at": r.get("submittedAt")}
        for r in view["reviews"] if r["body"].strip() and r["id"] not in handled
    ]
    pending_threads = [
        {"thread_id": t["id"], "path": t["path"], "line": t["line"], "outdated": t["isOutdated"],
         "comments": [{"author": login(c), "body": c["body"], "url": c["url"]} for c in t["comments"]["nodes"]]}
        for t in threads if not t["isResolved"] and not is_answered(t)
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
    elif window_left or pending or view["mergeable"] != "MERGEABLE" or view["mergeStateStatus"] == "UNKNOWN":
        state = "WAITING"
    elif view["mergeStateStatus"] == "BEHIND":
        state = "BEHIND"
    elif view["mergeStateStatus"] in ("BLOCKED", "DRAFT", "DIRTY"):
        state = "BLOCKED"
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
        "merge_state": view["mergeStateStatus"],
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
