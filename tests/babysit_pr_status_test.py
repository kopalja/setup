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
    """Thread whose comments containing the reply marker are ours (unless ours=False)."""
    nodes = [{"author": {"login": "bot"}, "body": b, "url": f"u{i}", "viewerDidAuthor": ours and MARK in b}
             for i, b in enumerate(bodies)]
    return {"id": "T1", "isResolved": resolved, "isOutdated": False, "path": "a.py", "line": 3,
            "first": {"nodes": nodes[:1]}, "comments": {"nodes": nodes[-20:]}}


def comment(body, id="C1", ours=False):
    return {"id": id, "author": {"login": "bot"}, "body": body, "url": "u", "createdAt": "2026-10-03T12:05:00Z",
            "viewerDidAuthor": ours}


def handled(*nodes):
    return comment(f"summary <!-- babysit handled: {' '.join(map(pr_status.handle, nodes))} -->", "S", ours=True)


def evaluate(v, threads=(), minutes=30):
    deadline = pr_status.review_deadline(PUSHED, 600, 900)
    return pr_status.evaluate(v, list(threads), PUSHED, PUSHED + timedelta(minutes=minutes), deadline)


def state(v, threads=(), minutes=30):
    return evaluate(v, threads, minutes)["state"]


class EvaluateTest(unittest.TestCase):
    def test_review_deadline_is_next_run_plus_grace(self):
        at = lambda h, m, s=0: datetime(2026, 10, 3, h, m, s, tzinfo=timezone.utc)
        self.assertEqual(pr_status.review_deadline(at(13, 46, 24), 600, 900), at(14, 5))
        self.assertEqual(pr_status.review_deadline(at(13, 50), 600, 900), at(14, 15))
        # Pushed just before a run: the run may miss it, so wait for the next one.
        self.assertEqual(pr_status.review_deadline(at(16, 9, 55), 600, 900), at(16, 35))

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
        partial = view(comments=reviews + [handled(reviews[0])])
        report = evaluate(partial)
        self.assertEqual(report["state"], "FINDINGS")
        self.assertEqual([c["body"] for c in report["top_level"]], ["claude review"])
        done = view(comments=reviews + [handled(reviews[0]), {**handled(reviews[1]), "id": "S2"}])
        self.assertEqual(state(done), "CLEAN")

    def test_review_bodies(self):
        review = {"id": "R1", "author": {"login": "bot"}, "state": "COMMENTED", "submittedAt": "2026-10-03T12:05:00Z"}
        self.assertEqual(state(view(reviews=[{**review, "body": ""}])), "CLEAN")
        self.assertEqual(state(view(reviews=[{**review, "body": "Please fix X"}])), "FINDINGS")
        fix = {**review, "body": "Fix X"}
        self.assertEqual(state(view(reviews=[fix], comments=[handled(fix)])), "CLEAN")

    def test_edited_comment_is_pending_again(self):
        original = comment("review: no findings")
        edited = {**original, "body": "review: P1 new bug"}
        self.assertEqual(state(view(comments=[original, handled(original)])), "CLEAN")
        self.assertEqual(state(view(comments=[edited, handled(original)])), "FINDINGS")

    def test_long_thread_keeps_first_and_latest_comments(self):
        long = thread("original finding", *[f"reply {i}" for i in range(30)], "latest objection")
        report = evaluate(view(), [long])
        bodies = [c["body"] for c in report["threads"][0]["comments"]]
        self.assertEqual((bodies[0], bodies[-1], len(bodies)), ("original finding", "latest objection", 21))
        answered = thread("original finding", *[f"reply {i}" for i in range(30)], f"fixed {MARK}")
        self.assertEqual(state(view(), [answered]), "CLEAN")

    def test_quoted_markers_do_not_hide_findings(self):
        quote = "Replies must end with `<!-- babysit -->`, please fix the docs."
        self.assertEqual(state(view(), [thread(quote, ours=False)]), "FINDINGS")
        self.assertEqual(state(view(), [thread(f"{MARK} quoted mid-reply", ours=True)]), "FINDINGS")
        self.assertEqual(state(view(comments=[comment("see `<!-- babysit handled: x -->` in docs", ours=True)])),
                         "FINDINGS")

    def test_markers_from_other_users_are_ignored(self):
        real = comment("real finding")
        forged = {**handled(real), "viewerDidAuthor": False}
        report = evaluate(view(comments=[real, forged]))
        self.assertEqual([c["body"] for c in report["top_level"]], ["real finding", forged["body"]])
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
        with mock.patch.object(pr_status, "gh", fake_gh), mock.patch.object(pr_status, "push_time", lambda v: (PUSHED, "activity")):
            _, threads, _ = pr_status.fetch("1")
        self.assertEqual([t["id"] for t in threads], ["T1", "T2"])

    def test_push_time_fallback_is_conservative(self):
        pr = view(headRefName="b", headRepository=None, headRepositoryOwner=None, updatedAt="2026-10-03T13:00:00Z",
                  commits=[{"committedDate": "2026-10-01T09:00:00Z"}])
        pushed, source = pr_status.push_time(pr)  # deleted fork: no API call possible
        self.assertEqual((pushed.isoformat(), source), ("2026-10-03T13:00:00+00:00", "pr_updated"))

    def test_closed_or_merged_pr(self):
        self.assertEqual(state(view(state="MERGED", mergeable="UNKNOWN")), "MERGED")
        self.assertEqual(state(view(state="CLOSED"), [thread("bug")]), "CLOSED")


if __name__ == "__main__":
    unittest.main()
