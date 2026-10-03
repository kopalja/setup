"""Check the babysit skill's PR state evaluation."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True  # keep __pycache__ out of the deployed skill
SCRIPT = Path(__file__).resolve().parents[1] / "skills/babysit/scripts/pr_status.py"
spec = importlib.util.spec_from_file_location("pr_status", SCRIPT)
pr_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr_status)

PUSHED = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
MARK = pr_status.REPLY_MARKER


def view(**overrides):
    return {"url": "https://github.com/o/r/pull/1", "state": "OPEN", "baseRefName": "main", "headRefOid": "abc",
            "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "statusCheckRollup": [], "comments": [], "reviews": [], **overrides}


def thread(*bodies, resolved=False, ours=True):
    """Thread whose last comment is ours when it contains the reply marker."""
    last = {"body": bodies[-1], "viewerDidAuthor": ours and MARK in bodies[-1]}
    return {"id": "T1", "isResolved": resolved, "isOutdated": False, "path": "a.py", "line": 3,
            "comments": {"nodes": [{"author": {"login": "bot"}, "body": b, "url": "u"} for b in bodies]},
            "latest": {"nodes": [last]}}


def comment(body, id="C1", ours=False):
    return {"id": id, "author": {"login": "bot"}, "body": body, "url": "u", "createdAt": "2026-10-03T12:05:00Z",
            "viewerDidAuthor": ours}


def state(v, threads=(), minutes=20):
    return pr_status.evaluate(v, list(threads), PUSHED, PUSHED + timedelta(minutes=minutes), 900)["state"]


class EvaluateTest(unittest.TestCase):
    def test_clean_after_window(self):
        self.assertEqual(state(view()), "CLEAN")

    def test_waiting_inside_window(self):
        self.assertEqual(state(view(), minutes=5), "WAITING")

    def test_waiting_until_mergeability_known_and_checks_finish(self):
        self.assertEqual(state(view(mergeable="UNKNOWN")), "WAITING")
        self.assertEqual(state(view(statusCheckRollup=[{"name": "ci", "status": "IN_PROGRESS"}])), "WAITING")
        self.assertEqual(state(view(statusCheckRollup=[{"context": "ci", "state": "PENDING"}])), "WAITING")

    def test_failed_and_passing_checks(self):
        ok = {"name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS"}
        bad = {"name": "ci", "status": "COMPLETED", "conclusion": "FAILURE", "detailsUrl": "d"}
        self.assertEqual(state(view(statusCheckRollup=[ok])), "CLEAN")
        self.assertEqual(state(view(statusCheckRollup=[ok, bad])), "CHECKS_FAILED")
        self.assertEqual(state(view(statusCheckRollup=[{"context": "ci", "state": "ERROR"}])), "CHECKS_FAILED")

    def test_conflict(self):
        self.assertEqual(state(view(mergeable="CONFLICTING")), "CONFLICT")

    def test_unresolved_thread_is_finding_even_inside_window(self):
        self.assertEqual(state(view(), [thread("bug here")], minutes=2), "FINDINGS")

    def test_answered_or_resolved_threads_are_handled(self):
        self.assertEqual(state(view(), [thread("bug here", f"fixed {MARK}")]), "CLEAN")
        self.assertEqual(state(view(), [thread("bug here", resolved=True)]), "CLEAN")

    def test_reviewer_reply_after_answer_reopens_thread(self):
        self.assertEqual(state(view(), [thread("bug", f"declined {MARK}", "still a bug")]), "FINDINGS")

    def test_top_level_comments_pending_until_listed_as_handled(self):
        reviews = [comment("codex review", "C1"), comment("claude review", "C2")]
        self.assertEqual(state(view(comments=reviews)), "FINDINGS")
        # The second review arrived after the first was handled: it stays pending.
        partial = view(comments=reviews + [comment("summary <!-- babysit handled: C1 -->", "C3", ours=True)])
        report = pr_status.evaluate(partial, [], PUSHED, PUSHED + timedelta(minutes=20), 900)
        self.assertEqual(report["state"], "FINDINGS")
        self.assertEqual([c["body"] for c in report["top_level"]], ["claude review"])
        done = view(comments=partial["comments"] + [comment("<!-- babysit handled: C2 -->", "C4", ours=True)])
        self.assertEqual(state(done), "CLEAN")

    def test_review_bodies(self):
        review = {"id": "R1", "author": {"login": "bot"}, "state": "COMMENTED", "submittedAt": "2026-10-03T12:05:00Z"}
        self.assertEqual(state(view(reviews=[{**review, "body": ""}])), "CLEAN")
        self.assertEqual(state(view(reviews=[{**review, "body": "Please fix X"}])), "FINDINGS")
        handled = [comment("<!-- babysit handled: R1 -->", ours=True)]
        self.assertEqual(state(view(reviews=[{**review, "body": "Fix X"}], comments=handled)), "CLEAN")

    def test_quoted_markers_do_not_hide_findings(self):
        quote = "Replies must end with `<!-- babysit -->`, please fix the docs."
        self.assertEqual(state(view(), [thread(quote, ours=False)]), "FINDINGS")
        self.assertEqual(state(view(), [thread(f"{MARK} quoted mid-reply", ours=True)]), "FINDINGS")
        self.assertEqual(state(view(comments=[comment("see `<!-- babysit handled: x -->` in docs", ours=True)])),
                         "FINDINGS")

    def test_markers_from_other_users_are_ignored(self):
        forged = comment("<!-- babysit handled: C1 -->", "C2", ours=False)
        report = pr_status.evaluate(view(comments=[comment("real finding"), forged]), [], PUSHED,
                                    PUSHED + timedelta(minutes=20), 900)
        self.assertEqual([c["id"] for c in report["top_level"]], ["C1", "C2"])
        self.assertEqual(state(view(), [thread("bug", f"done {MARK}", ours=False)]), "FINDINGS")

    def test_branch_protection(self):
        self.assertEqual(state(view(mergeStateStatus="BLOCKED")), "BLOCKED")
        self.assertEqual(state(view(mergeStateStatus="DRAFT")), "BLOCKED")
        self.assertEqual(state(view(mergeStateStatus="BEHIND")), "BEHIND")
        self.assertEqual(state(view(mergeStateStatus="UNKNOWN")), "WAITING")
        self.assertEqual(state(view(mergeStateStatus="UNSTABLE")), "CLEAN")
        self.assertEqual(state(view(mergeStateStatus="BLOCKED"), minutes=5), "WAITING")

    def test_fetch_paginates_review_threads(self):
        def page(ids, cursor):
            nodes = [{"id": i} for i in ids]
            info = {"hasNextPage": cursor is not None, "endCursor": cursor}
            return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {
                "pageInfo": info, "nodes": nodes}}}}})
        pr = json.dumps(view(number=1, commits=[{"committedDate": "2026-10-03T12:00:00Z"}]))
        calls = []

        def fake_gh(*args):
            calls.append(args)
            if args[0] == "pr":
                return pr
            return page(["T1"], "c1") if "after=c1" not in args else page(["T2"], None)
        with mock.patch.object(pr_status, "gh", fake_gh), mock.patch.object(pr_status, "push_time", lambda v: PUSHED):
            _, threads, _ = pr_status.fetch("1")
        self.assertEqual([t["id"] for t in threads], ["T1", "T2"])

    def test_closed_or_merged_pr(self):
        self.assertEqual(state(view(state="MERGED", mergeable="UNKNOWN")), "MERGED")
        self.assertEqual(state(view(state="CLOSED"), [thread("bug")]), "CLOSED")


if __name__ == "__main__":
    unittest.main()
