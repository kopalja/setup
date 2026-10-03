"""Check the babysit skill's PR state evaluation."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True  # keep __pycache__ out of the deployed skill
SCRIPT = Path(__file__).resolve().parents[1] / "skills/babysit/scripts/pr_status.py"
spec = importlib.util.spec_from_file_location("pr_status", SCRIPT)
pr_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr_status)

PUSHED = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
MARK = pr_status.MARKER


def view(**overrides):
    return {"url": "https://github.com/o/r/pull/1", "state": "OPEN", "baseRefName": "main", "headRefOid": "abc",
            "mergeable": "MERGEABLE", "statusCheckRollup": [], "comments": [], "reviews": [], **overrides}


def thread(*bodies, resolved=False):
    return {"id": "T1", "isResolved": resolved, "isOutdated": False, "path": "a.py", "line": 3,
            "comments": {"nodes": [{"author": {"login": "bot"}, "body": b, "url": "u"} for b in bodies]}}


def comment(body, id="C1"):
    return {"id": id, "author": {"login": "bot"}, "body": body, "url": "u", "createdAt": "2026-10-03T12:05:00Z"}


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
        partial = view(comments=reviews + [comment("summary <!-- babysit handled: C1 -->", "C3")])
        report = pr_status.evaluate(partial, [], PUSHED, PUSHED + timedelta(minutes=20), 900)
        self.assertEqual(report["state"], "FINDINGS")
        self.assertEqual([c["body"] for c in report["top_level"]], ["claude review"])
        done = view(comments=partial["comments"] + [comment("<!-- babysit handled: C2 -->", "C4")])
        self.assertEqual(state(done), "CLEAN")

    def test_review_bodies(self):
        review = {"id": "R1", "author": {"login": "bot"}, "state": "COMMENTED", "submittedAt": "2026-10-03T12:05:00Z"}
        self.assertEqual(state(view(reviews=[{**review, "body": ""}])), "CLEAN")
        self.assertEqual(state(view(reviews=[{**review, "body": "Please fix X"}])), "FINDINGS")
        handled = [comment("<!-- babysit handled: R1 -->")]
        self.assertEqual(state(view(reviews=[{**review, "body": "Fix X"}], comments=handled)), "CLEAN")

    def test_closed_or_merged_pr(self):
        self.assertEqual(state(view(state="MERGED", mergeable="UNKNOWN")), "MERGED")
        self.assertEqual(state(view(state="CLOSED"), [thread("bug")]), "CLOSED")


if __name__ == "__main__":
    unittest.main()
