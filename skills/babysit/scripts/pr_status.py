#!/usr/bin/env python3
"""Report what a GitHub PR still needs before it can merge; optionally wait for reviews.

Stateless: everything is derived from GitHub, so it is safe to rerun at any time.
A review thread is handled when its last comment is ours and ends with REPLY_MARKER. A top-level
comment or review is handled when its `handle` (id@body-hash, so edits reopen it) is listed in a
comment of ours that ends with `<!-- babysit handled: <handle> <handle> -->`. "Ours" means written
by the authenticated gh user.

Only the user, repo owners, members and collaborators (plus --trust logins) count as reviewers.
Other authors are listed under `untrusted` and never block or drive the loop.

Reviews of the head commit are top-level comments or reviews that mention its sha (for example
"Commit: `<sha>`"). Once the expected number has arrived, there is no need to wait for the deadline.
"""
import argparse
import hashlib
from datetime import datetime, timedelta, timezone
import json
import re
import subprocess
import time
from urllib.parse import quote

REPLY_MARKER = "<!-- babysit -->"
HANDLED = re.compile(r"<!-- babysit handled:([^>]*)-->\s*$")
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING = {"PENDING", "EXPECTED", None}
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line
          first: comments(first: 1) { nodes { author { login } authorAssociation body url viewerDidAuthor } }
          comments(last: 20) { nodes { author { login } authorAssociation body url viewerDidAuthor } }
        }
      }
    }
  }
}"""


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, timeout=60).stdout


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def login(node):
    return (node.get("author") or {}).get("login", "ghost")


def push_time(view):
    """When the head commit was pushed, and where that time came from.

    Without the activity API, fall back conservatively to the latest PR update: a push of an old
    commit still updates the PR, so the review window cannot have closed before the push.
    """
    try:
        owner = view["headRepositoryOwner"]["login"]
        repo = view["headRepository"]["name"]
        ref = quote(f"refs/heads/{view['headRefName']}", safe="")
        for activity in json.loads(gh("api", f"repos/{owner}/{repo}/activity?ref={ref}&per_page=20")):
            if activity.get("after") == view["headRefOid"]:
                return parse_time(activity["timestamp"]), "activity"
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError):
        pass
    return max(parse_time(view["commits"][-1]["committedDate"]), parse_time(view["updatedAt"])), "pr_updated"


def fetch(pr):
    fields = ("number,url,state,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,"
              "commits,updatedAt,mergeable,mergeStateStatus,statusCheckRollup,comments,reviews")
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


def handle(node):
    return f'{node["id"]}@{hashlib.sha256(node["body"].encode()).hexdigest()[:12]}'


def thread_comments(thread):
    first, last = thread["first"]["nodes"], thread["comments"]["nodes"]
    return first + [c for c in last if c["url"] not in {f["url"] for f in first}]


def is_trusted(node, trust):
    return node.get("viewerDidAuthor") or node.get("authorAssociation") in TRUSTED or login(node) in trust


def is_answer(node):
    return node.get("viewerDidAuthor") and node["body"].rstrip().endswith(REPLY_MARKER)


def thread_pending(thread, trust):
    """Unanswered trusted feedback; a reply after our answer counts even if the thread was resolved."""
    relevant = [c for c in thread_comments(thread) if is_trusted(c, trust)]
    if not relevant or is_answer(relevant[-1]):
        return False
    return not thread["isResolved"] or any(map(is_answer, relevant))


def review_deadline(pushed, every, grace, margin=60):
    """Reviews run every `every` seconds on the clock (14:00, 14:10, ...) and post within `grace`.

    A push less than `margin` seconds before a run may miss it, so it counts toward the next one.
    """
    epoch = pushed.timestamp() + margin
    run = (int(epoch) // every + 1) * every
    return datetime.fromtimestamp(run, timezone.utc) + timedelta(seconds=grace)


def evaluate(view, threads, pushed, now, deadline, source="activity", expected_reviews=2, trust=()):
    summaries = [c for c in view["comments"] if c.get("viewerDidAuthor") and handled_ids(c["body"]) is not None]
    summary_ids = {c["id"] for c in summaries}
    handled = {i for c in summaries for i in handled_ids(c["body"])}
    items = [
        {"handle": handle(c), "kind": "comment", "author": login(c), "body": c["body"], "url": c.get("url"),
         "at": c["createdAt"]}
        for c in view["comments"] if c["id"] not in summary_ids and handle(c) not in handled
    ] + [
        {"handle": handle(r), "kind": "review", "author": login(r), "state": r["state"], "body": r["body"],
         "at": r.get("submittedAt")}
        for r in view["reviews"] if r["body"].strip() and handle(r) not in handled
    ]
    nodes = {handle(n): n for n in view["comments"] + view["reviews"]}
    top_level = [i for i in items if is_trusted(nodes[i["handle"]], trust)]
    untrusted = [i for i in items if i not in top_level]
    head = view["headRefOid"][:7]
    head_reviews = sum(head in n["body"] for n in view["comments"] + view["reviews"]
                       if n["id"] not in summary_ids and is_trusted(n, trust))
    pending_threads = [
        {"thread_id": t["id"], "path": t["path"], "line": t["line"], "outdated": t["isOutdated"],
         "comments": [{"author": login(c), "trusted": bool(is_trusted(c, trust)), "body": c["body"], "url": c["url"]}
                      for c in thread_comments(t)]}
        for t in threads if thread_pending(t, trust)
    ]

    failed, pending = [], []
    for check in view["statusCheckRollup"] or []:
        name = check.get("name") or check.get("context")
        result = check.get("conclusion") or check.get("state")
        if check.get("status") not in (None, "COMPLETED") or result in PENDING:
            pending.append(name)
        elif result in FAILED:
            failed.append({"name": name, "url": check.get("detailsUrl") or check.get("targetUrl")})

    window_left = 0 if head_reviews >= expected_reviews else max(0, int((deadline - now).total_seconds()))
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
        "pushed_at_source": source,
        "review_deadline": deadline.isoformat(),
        "review_window_left_s": window_left,
        "head_reviews": head_reviews,
        "mergeable": view["mergeable"],
        "merge_state": view["mergeStateStatus"],
        "checks_pending": pending,
        "checks_failed": failed,
        "threads": pending_threads,
        "top_level": top_level,
        "untrusted": untrusted,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pr", nargs="?", help="PR number, URL or branch (default: current branch)")
    parser.add_argument("--wait", action="store_true", help="poll while the state is WAITING")
    parser.add_argument("--every", type=int, default=600, help="reviews run every N seconds on the clock")
    parser.add_argument("--grace", type=int, default=900, help="seconds a review may take to post after its run")
    parser.add_argument("--reviews", type=int, default=2, help="reviews expected per push; stop waiting once all arrived")
    parser.add_argument("--trust", default="", help="comma-separated extra reviewer logins, e.g. review bots")
    parser.add_argument("--max-wait", type=int, default=480, help="stop polling after this many seconds")
    parser.add_argument("--interval", type=int, default=60, help="seconds between polls")
    args = parser.parse_args()

    start, report = time.monotonic(), None
    while True:
        try:
            view, threads, (pushed, source) = fetch(args.pr)
            deadline = review_deadline(pushed, args.every, args.grace)
            report = evaluate(view, threads, pushed, datetime.now(timezone.utc), deadline, source, args.reviews,
                              set(filter(None, args.trust.split(","))))
            if not args.wait or report["state"] != "WAITING":
                break
        except subprocess.TimeoutExpired:
            if not args.wait:
                raise
            report = None  # gh hung: retry on the next poll
        if time.monotonic() - start + args.interval > args.max_wait:
            break
        time.sleep(args.interval)
    if report is None:
        raise SystemExit("gh timed out; rerun the script")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
