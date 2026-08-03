#!/usr/bin/env python3
"""Regression tests for the pure logic in this skill's scripts.

These cover the parts that decide grades: lateness math, penalty math,
late-day budgets, roster matching, and CSV parsing. Everything here is pure --
no network, no Canvas account, no fixtures on disk.

    python3 -m unittest discover -s tests      # this file plus the HTTP suite
    python3 tests/test_grading_logic.py        # just this file

canvas.py's HTTP layer is covered separately in test_canvas_http.py, which
drives it against a local mock Canvas. Between them: everything that could
silently give a student the wrong grade, and everything that could silently
drop half a roster.
"""

import importlib.util
import os
import sys
import unittest
from datetime import timedelta

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


def load(name):
    """Import a script by path (they're CLIs, not an installed package)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# canvas_common is imported normally, not through load(): the scripts reach it
# through sys.path, and load() would build a *second* module object whose
# functions are different objects from the ones they actually call. The
# de-duplication assertions below compare function identity, so this has to be
# the same module the scripts got.
sys.path.insert(0, SCRIPTS)
import canvas_common  # noqa: E402

mark_late = load("mark_late")
late_penalties = load("late_penalties")
sync_grades = load("sync_grades")

DAY = 86400


# --------------------------------------------------------------------------- #
# mark_late: datetime parsing
# --------------------------------------------------------------------------- #

class TestParseDatetime(unittest.TestCase):
    def test_explicit_offset_forms(self):
        a = mark_late.parse_dt("2026-07-24T23:59:00-04:00", "-04:00")
        b = mark_late.parse_dt("2026-07-24 23:59:00 -0400", "-04:00")
        self.assertEqual(a, b)

    def test_z_suffix_is_utc(self):
        d = mark_late.parse_dt("2026-07-25T03:59:00Z", "-04:00")
        self.assertEqual(d.utcoffset(), timedelta(0))

    def test_naive_uses_default_tz(self):
        naive = mark_late.parse_dt("2026-07-24 23:59:00", "-04:00")
        explicit = mark_late.parse_dt("2026-07-24T23:59:00-04:00", "-04:00")
        self.assertEqual(naive, explicit)

    def test_twelve_hour_clock(self):
        d = mark_late.parse_dt("2026-07-24 11:59:00 PM -0400", "-04:00")
        self.assertEqual(d, mark_late.parse_dt("2026-07-24T23:59:00-04:00", "-04:00"))

    def test_unparseable_returns_none(self):
        self.assertIsNone(mark_late.parse_dt("not a date", "-04:00"))
        self.assertIsNone(mark_late.parse_dt("", "-04:00"))
        self.assertIsNone(mark_late.parse_dt(None, "-04:00"))

    def test_submission_after_due_is_positive_delta(self):
        due = mark_late.parse_dt("2026-07-24T23:59:00-04:00", "-04:00")
        sub = mark_late.parse_dt("2026-07-25 00:30:00 -0400", "-04:00")
        self.assertEqual(int((sub - due).total_seconds()), 31 * 60)


class TestTimezoneHandling(unittest.TestCase):
    """The default must not be one region's offset (it used to be -04:00)."""

    def test_system_offset_is_wellformed(self):
        off = mark_late.system_utc_offset()
        self.assertRegex(off, r"^[+-]\d{2}:\d{2}$")

    def test_iana_zone_is_dst_aware(self):
        winter = mark_late.parse_dt("2026-01-15 12:00:00", "America/New_York")
        summer = mark_late.parse_dt("2026-07-15 12:00:00", "America/New_York")
        self.assertEqual(winter.utcoffset(), timedelta(hours=-5))
        self.assertEqual(summer.utcoffset(), timedelta(hours=-4))

    def test_fixed_offset_is_not_dst_aware(self):
        winter = mark_late.parse_dt("2026-01-15 12:00:00", "-04:00")
        summer = mark_late.parse_dt("2026-07-15 12:00:00", "-04:00")
        self.assertEqual(winter.utcoffset(), summer.utcoffset())

    def test_non_us_zones(self):
        self.assertEqual(
            mark_late.parse_dt("2026-07-15 12:00:00", "Asia/Kolkata").utcoffset(),
            timedelta(hours=5, minutes=30))
        self.assertEqual(
            mark_late.parse_dt("2026-01-15 12:00:00", "Europe/London").utcoffset(),
            timedelta(0))

    def test_none_and_z_default_to_utc(self):
        self.assertEqual(mark_late.parse_offset(None).utcoffset(None), timedelta(0))
        self.assertEqual(mark_late.parse_offset("Z").utcoffset(None), timedelta(0))


class TestParseHMS(unittest.TestCase):
    def test_hours_minutes_seconds(self):
        self.assertEqual(mark_late.parse_hms("26:30:00"), 26 * 3600 + 30 * 60)

    def test_zero_forms(self):
        self.assertEqual(mark_late.parse_hms("00:00:00"), 0)
        self.assertEqual(mark_late.parse_hms("0:00:00"), 0)

    def test_blank_is_none(self):
        self.assertIsNone(mark_late.parse_hms(""))
        self.assertIsNone(mark_late.parse_hms(None))

    def test_garbage_is_none(self):
        self.assertIsNone(mark_late.parse_hms("yesterday"))


# --------------------------------------------------------------------------- #
# mark_late: lateness classification
# --------------------------------------------------------------------------- #

class TestLateDays(unittest.TestCase):
    def test_part_day_rounds_up(self):
        self.assertEqual(mark_late.late_days(1, 0), 1)
        self.assertEqual(mark_late.late_days(12 * 3600, 0), 1)

    def test_exact_day_boundary(self):
        self.assertEqual(mark_late.late_days(DAY, 0), 1)
        self.assertEqual(mark_late.late_days(DAY + 1, 0), 2)

    def test_grace_window(self):
        self.assertEqual(mark_late.late_days(9 * 60, 10 * 60), 0)
        self.assertEqual(mark_late.late_days(11 * 60, 10 * 60), 1)

    def test_on_time(self):
        self.assertEqual(mark_late.late_days(0, 0), 0)
        self.assertEqual(mark_late.late_days(None, 0), 0)


class TestClassify(unittest.TestCase):
    """The decision table. Getting these wrong changes real grades."""

    def kind(self, seconds, accommodated=False, exempt=False, grace=0,
             max_days=2, after_max="zero"):
        return mark_late.classify(seconds, accommodated, exempt, grace,
                                  max_days, after_max)["kind"]

    def test_on_time(self):
        self.assertEqual(self.kind(0), "on_time")

    def test_late_within_cap_is_marked(self):
        self.assertEqual(self.kind(DAY), "mark_late")
        self.assertEqual(self.kind(2 * DAY), "mark_late")

    def test_over_cap_respects_after_max(self):
        self.assertEqual(self.kind(3 * DAY, after_max="zero"), "zero")
        self.assertEqual(self.kind(3 * DAY, after_max="accept"), "accept")
        self.assertEqual(self.kind(3 * DAY, after_max="flag"), "needs_review")

    def test_no_cap_never_zeroes(self):
        self.assertEqual(self.kind(9 * DAY, max_days=0), "mark_late")

    # --- the accommodation guarantees --------------------------------------
    def test_accommodated_on_time_is_not_penalized(self):
        self.assertEqual(self.kind(0, accommodated=True), "accommodated")

    def test_accommodated_late_goes_to_review_never_penalty(self):
        for after_max in ("zero", "accept", "flag"):
            self.assertEqual(self.kind(3 * DAY, accommodated=True, after_max=after_max),
                             "needs_review",
                             f"accommodated student penalized with after_max={after_max}")

    def test_exempt_always_reviews_regardless_of_lateness(self):
        self.assertEqual(self.kind(0, exempt=True), "needs_review")
        self.assertEqual(self.kind(99 * DAY, exempt=True), "needs_review")

    def test_exempt_wins_over_everything(self):
        action = mark_late.classify(99 * DAY, True, True, 0, 2, "zero")
        self.assertEqual(action["reason"], "exempt")

    def test_over_by_is_reported_for_zeroed(self):
        action = mark_late.classify(5 * DAY, False, False, 0, 2, "zero")
        self.assertEqual(action["days_late"], 5)
        self.assertEqual(action["over_by"], 3)


class TestEffectiveDue(unittest.TestCase):
    def setUp(self):
        self.base = mark_late.parse_dt("2026-07-24T23:59:00-04:00", "-04:00")

    def test_base_only(self):
        due, src, ext, exempt = mark_late.effective_due(self.base, None, None, "-04:00")
        self.assertEqual((due, src, ext, exempt), (self.base, "base", False, False))

    def test_canvas_override_wins_when_later(self):
        later = mark_late.parse_dt("2026-07-26T23:59:00-04:00", "-04:00")
        due, src, ext, _ = mark_late.effective_due(self.base, later, None, "-04:00")
        self.assertEqual((due, src, ext), (later, "canvas_override", True))

    def test_earlier_override_does_not_shorten_deadline(self):
        earlier = mark_late.parse_dt("2026-07-20T23:59:00-04:00", "-04:00")
        due, src, _, _ = mark_late.effective_due(self.base, earlier, None, "-04:00")
        self.assertEqual((due, src), (self.base, "base"))

    def test_extra_days_accommodation(self):
        accom = {"type": "extra_days", "days": 2}
        due, src, ext, _ = mark_late.effective_due(self.base, self.base, accom, "-04:00")
        self.assertEqual(due, self.base + timedelta(days=2))
        self.assertEqual((src, ext), ("accommodation_file", True))

    def test_explicit_extension_accommodation(self):
        accom = {"type": "extension", "due_at": "2026-08-01T23:59:00-04:00"}
        due, src, ext, _ = mark_late.effective_due(self.base, self.base, accom, "-04:00")
        self.assertEqual(due.isoformat(), "2026-08-01T23:59:00-04:00")
        self.assertEqual((src, ext), ("accommodation_file", True))

    def test_exempt_flag(self):
        _, _, _, exempt = mark_late.effective_due(self.base, None, {"type": "exempt"}, "-04:00")
        self.assertTrue(exempt)

    def test_latest_wins_between_override_and_file(self):
        override = mark_late.parse_dt("2026-07-26T23:59:00-04:00", "-04:00")
        accom = {"type": "extension", "due_at": "2026-07-25T23:59:00-04:00"}
        due, src, _, _ = mark_late.effective_due(self.base, override, accom, "-04:00")
        self.assertEqual((due, src), (override, "canvas_override"))


# --------------------------------------------------------------------------- #
# late_penalties: penalty and budget math
# --------------------------------------------------------------------------- #

class TestPenalizedScore(unittest.TestCase):
    def test_percent_of_full_marks_not_of_score(self):
        # 10%/day on a 50-point assignment is -5 pts/day, even from a 40 score.
        new, off = late_penalties.penalized_score(40, 50, 1, 10, 0)
        self.assertEqual((new, off), (35, 5))

    def test_multiple_days(self):
        new, off = late_penalties.penalized_score(50, 50, 3, 10, 0)
        self.assertEqual((new, off), (35, 15))

    def test_floor_is_respected(self):
        new, off = late_penalties.penalized_score(10, 50, 5, 10, 0)
        self.assertEqual(new, 0)
        self.assertEqual(off, 10)

    def test_custom_floor(self):
        new, _ = late_penalties.penalized_score(50, 50, 10, 10, 25)
        self.assertEqual(new, 25)

    def test_zero_days_is_untouched(self):
        self.assertEqual(late_penalties.penalized_score(47, 50, 0, 10, 0), (47, 0.0))

    def test_none_score_is_untouched(self):
        self.assertEqual(late_penalties.penalized_score(None, 50, 3, 10, 0), (None, 0.0))


class TestDaysLate(unittest.TestCase):
    """Both args are seconds, matching mark_late.late_days."""

    def test_grace_seconds(self):
        self.assertEqual(late_penalties.days_late(9 * 60, 10 * 60), 0)
        self.assertEqual(late_penalties.days_late(11 * 60, 10 * 60), 1)

    def test_rounds_up(self):
        self.assertEqual(late_penalties.days_late(DAY + 1, 0), 2)

    def test_agrees_with_mark_late_across_the_board(self):
        """The two implementations must not drift apart."""
        for seconds in (0, 1, 60, 3600, DAY - 1, DAY, DAY + 1, 3 * DAY, 10 * DAY):
            for grace in (0, 600, 3600):
                self.assertEqual(
                    late_penalties.days_late(seconds, grace),
                    mark_late.late_days(seconds, grace),
                    f"drift at seconds={seconds} grace={grace}")


class TestBudgetLedger(unittest.TestCase):
    def sub(self, aid, seconds_late, score=50):
        return {"assignment_id": aid, "name": f"A{aid}", "score": score,
                "points_possible": 50, "seconds_late": seconds_late}

    def test_budget_absorbs_early_lateness(self):
        subs = [self.sub(1, 2 * DAY), self.sub(2, 2 * DAY)]
        ledger = late_penalties.budget_ledger(subs, 3, 10, 0, 0)
        self.assertEqual(ledger[0]["budget_used"], 2)
        self.assertEqual(ledger[0]["penalized_days"], 0)
        # Second assignment: only 1 day of budget left, so 1 day is charged.
        self.assertEqual(ledger[1]["budget_used"], 1)
        self.assertEqual(ledger[1]["penalized_days"], 1)
        self.assertEqual(ledger[1]["new_score"], 45)

    def test_budget_exhausted_charges_full(self):
        subs = [self.sub(1, 5 * DAY)]
        ledger = late_penalties.budget_ledger(subs, 0, 10, 0, 0)
        self.assertEqual(ledger[0]["penalized_days"], 5)
        self.assertEqual(ledger[0]["new_score"], 25)

    def test_on_time_spends_nothing(self):
        subs = [self.sub(1, 0), self.sub(2, DAY)]
        ledger = late_penalties.budget_ledger(subs, 3, 10, 0, 0)
        self.assertEqual(ledger[0]["budget_used"], 0)
        self.assertEqual(ledger[1]["budget_remaining"], 2)

    def test_remaining_never_goes_negative(self):
        subs = [self.sub(1, 9 * DAY)]
        ledger = late_penalties.budget_ledger(subs, 2, 10, 0, 0)
        self.assertEqual(ledger[0]["budget_remaining"], 0)


class TestBudgetSpendsOnlyOnPenalizableWork(unittest.TestCase):
    """The budget bug, and the shape of submission that caused it.

    budget_ledger used to compute days-late from `seconds_late` for every row it
    was handed, and only consult gradeable() much later, when deciding what to
    WRITE. So an ungraded, excused, or never-submitted row spent the student's
    late days and then took no penalty itself -- the days were simply gone, and
    the next real submission paid for them. The old suite never caught it
    because every submission it fed the ledger was graded and submitted.

    Each test here is one such row followed by a graded submission one day late
    with a full three-day budget available: the graded one must come out
    untouched at 50.
    """

    def graded(self, aid=2, seconds_late=DAY, score=50):
        return {"assignment_id": aid, "name": f"A{aid}", "score": score,
                "points_possible": 50, "seconds_late": seconds_late,
                "late": True, "excused": False, "workflow_state": "graded",
                "submitted_at": "2026-07-20T12:00:00Z"}

    def assert_untouched(self, ledger, budget_used=1):
        """The graded submission is ledger[1]; it should have paid nothing."""
        self.assertEqual(ledger[0]["budget_used"], 0)
        self.assertFalse(ledger[0]["spends_budget"])
        self.assertEqual(ledger[1]["budget_used"], budget_used)
        self.assertEqual(ledger[1]["penalized_days"], 0)
        self.assertEqual(ledger[1]["new_score"], 50)
        self.assertEqual(ledger[1]["deducted"], 0.0)

    def test_ungraded_does_not_drain_the_budget(self):
        # The exact reproduction: budget 3, an ungraded submission 3 days late,
        # then a graded one 1 day late. Before the fix the ungraded row ate all
        # three days and the graded one was charged 50 -> 45.
        ungraded = {"assignment_id": 1, "name": "A1", "score": None,
                    "points_possible": 50, "seconds_late": 3 * DAY,
                    "late": True, "excused": False, "workflow_state": "submitted",
                    "submitted_at": "2026-07-10T12:00:00Z"}
        ledger = late_penalties.budget_ledger([ungraded, self.graded()], 3, 10, 0, 0)
        self.assert_untouched(ledger)
        self.assertEqual(ledger[0]["excluded_reason"], "ungraded")
        self.assertEqual(ledger[1]["budget_remaining"], 2)

    def test_ungraded_with_a_graded_workflow_state_is_still_ungraded(self):
        """No entered score means nothing to deduct from, whatever Canvas's
        workflow_state says."""
        no_score = {"assignment_id": 1, "name": "A1", "score": None,
                    "points_possible": 50, "seconds_late": 3 * DAY,
                    "late": True, "excused": False, "workflow_state": "graded",
                    "submitted_at": "2026-07-10T12:00:00Z"}
        ledger = late_penalties.budget_ledger([no_score, self.graded()], 3, 10, 0, 0)
        self.assert_untouched(ledger)
        self.assertEqual(ledger[0]["excluded_reason"], "ungraded")

    def test_excused_does_not_drain_the_budget(self):
        """Excused work is out of the grading system entirely; it cannot spend
        days it will never be penalized for."""
        excused = {"assignment_id": 1, "name": "A1", "score": 40,
                   "points_possible": 50, "seconds_late": 3 * DAY,
                   "late": True, "excused": True, "workflow_state": "graded",
                   "submitted_at": "2026-07-10T12:00:00Z"}
        ledger = late_penalties.budget_ledger([excused, self.graded()], 3, 10, 0, 0)
        self.assert_untouched(ledger)
        self.assertEqual(ledger[0]["excluded_reason"], "excused")
        self.assertEqual(ledger[0]["new_score"], 40)   # left exactly as found
        self.assertEqual(ledger[0]["deducted"], 0.0)

    def test_never_submitted_does_not_drain_the_budget(self):
        """No submission time means nothing was handed in late. Canvas still
        reports a seconds_late for these; it does not describe a student being
        late, so it must not be charged."""
        never = {"assignment_id": 1, "name": "A1", "score": 0,
                 "points_possible": 50, "seconds_late": 3 * DAY,
                 "late": True, "excused": False, "workflow_state": "graded",
                 "submitted_at": ""}
        ledger = late_penalties.budget_ledger([never, self.graded()], 3, 10, 0, 0)
        self.assert_untouched(ledger)
        self.assertEqual(ledger[0]["excluded_reason"], "not_submitted")

    def test_not_marked_late_does_not_drain_the_budget(self):
        """An instructor who cleared late_policy_status has already ruled on
        this one; a stale seconds_late must not overrule them."""
        cleared = {"assignment_id": 1, "name": "A1", "score": 45,
                   "points_possible": 50, "seconds_late": 3 * DAY,
                   "late": False, "excused": False, "workflow_state": "graded",
                   "submitted_at": "2026-07-10T12:00:00Z"}
        ledger = late_penalties.budget_ledger([cleared, self.graded()], 3, 10, 0, 0)
        self.assert_untouched(ledger)
        self.assertEqual(ledger[0]["excluded_reason"], "not_marked_late")

    def test_days_late_is_still_reported_for_an_excluded_row(self):
        """Excluding a row from the budget must not hide that it was late --
        that is a thing a human may still want to look at."""
        excused = {"assignment_id": 1, "name": "A1", "score": 40,
                   "points_possible": 50, "seconds_late": 3 * DAY,
                   "excused": True, "workflow_state": "graded", "late": True,
                   "submitted_at": "2026-07-10T12:00:00Z"}
        ledger = late_penalties.budget_ledger([excused], 3, 10, 0, 0)
        self.assertEqual(ledger[0]["days_late"], 3)
        self.assertEqual(ledger[0]["budget_used"], 0)
        self.assertEqual(ledger[0]["budget_remaining"], 3)

    def test_penalizable_work_still_spends_and_is_charged(self):
        """The fix must not make the budget stop working: a real graded late
        submission past the budget is charged exactly as before."""
        first = self.graded(aid=1, seconds_late=2 * DAY)
        second = self.graded(aid=2, seconds_late=2 * DAY)
        ledger = late_penalties.budget_ledger([first, second], 3, 10, 0, 0)
        self.assertTrue(ledger[0]["spends_budget"])
        self.assertEqual(ledger[0]["budget_used"], 2)
        self.assertEqual(ledger[1]["budget_used"], 1)
        self.assertEqual(ledger[1]["penalized_days"], 1)
        self.assertEqual(ledger[1]["new_score"], 45)

    def test_exclusion_leaves_no_grade_change_to_write(self):
        """penalized_days 0 is what stops the write loop in cmd_budget, so an
        excluded row must never come out with one."""
        for sub in (
            {"score": None, "workflow_state": "submitted"},
            {"score": 40, "excused": True},
            {"score": 0, "submitted_at": ""},
            {"score": 45, "late": False},
        ):
            row = {"assignment_id": 1, "name": "A1", "points_possible": 50,
                   "seconds_late": 9 * DAY, **sub}
            ledger = late_penalties.budget_ledger([row], 0, 10, 0, 0)
            self.assertEqual(ledger[0]["penalized_days"], 0, sub)
            self.assertEqual(ledger[0]["deducted"], 0.0, sub)
            self.assertEqual(ledger[0]["new_score"], sub["score"], sub)


class TestChronologicalOrdering(unittest.TestCase):
    """Budget spend order is chronological, and a blank submitted_at must not
    jump the queue.

    `sort(key=lambda s: s["submitted_at"])` put the empty string first, so a
    never-submitted row was the very first thing to spend the budget. Both the
    exclusion rule and this ordering fix are needed: the ordering also decides
    which real submission gets the last day of a partly-spent budget.
    """

    def key(self, submitted_at):
        return late_penalties.submitted_key({"submitted_at": submitted_at})

    def test_blank_sorts_after_a_real_timestamp(self):
        self.assertGreater(self.key(""), self.key("2026-07-10T12:00:00Z"))

    def test_missing_key_sorts_after_a_real_timestamp(self):
        self.assertGreater(late_penalties.submitted_key({}),
                           self.key("2026-07-10T12:00:00Z"))

    def test_none_sorts_after_a_real_timestamp(self):
        self.assertGreater(self.key(None), self.key("2026-07-10T12:00:00Z"))

    def test_real_timestamps_stay_chronological(self):
        subs = [{"assignment_id": 3, "submitted_at": "2026-09-01T00:00:00Z"},
                {"assignment_id": 9, "submitted_at": ""},
                {"assignment_id": 1, "submitted_at": "2026-07-01T00:00:00Z"},
                {"assignment_id": 2, "submitted_at": "2026-08-01T00:00:00Z"}]
        subs.sort(key=late_penalties.submitted_key)
        self.assertEqual([s["assignment_id"] for s in subs], [1, 2, 3, 9])


# --------------------------------------------------------------------------- #
# sync_grades: roster matching and the grade plan
# --------------------------------------------------------------------------- #

ROSTER = [
    {"id": 1, "name": "Ada Lovelace", "email": "ada@example.edu", "sis_user_id": "1001",
     "login_id": "ada@example.edu"},
    {"id": 2, "name": "Alan Turing", "email": "alan@example.edu", "sis_user_id": "1002",
     "login_id": "alan@example.edu"},
    {"id": 3, "name": "Twin One", "email": "dup@example.edu", "sis_user_id": "1003",
     "login_id": "dup1@example.edu"},
    {"id": 4, "name": "Twin Two", "email": "dup@example.edu", "sis_user_id": "1004",
     "login_id": "dup2@example.edu"},
]
COLS = {"score": "Total Score", "email": "Email", "sid": "SID", "status": "Status"}


class TestRosterMatching(unittest.TestCase):
    def setUp(self):
        self.maps = sync_grades.build_roster_maps(ROSTER)

    def test_match_by_email(self):
        uid, how = sync_grades.match_row({"Email": "ada@example.edu"}, COLS, self.maps)
        self.assertEqual((uid, how), (1, "email"))

    def test_email_is_case_insensitive(self):
        uid, _ = sync_grades.match_row({"Email": "ADA@Example.EDU"}, COLS, self.maps)
        self.assertEqual(uid, 1)

    def test_falls_back_to_sid(self):
        uid, how = sync_grades.match_row({"Email": "", "SID": "1002"}, COLS, self.maps)
        self.assertEqual((uid, how), (2, "sis"))

    def test_ambiguous_email_is_never_guessed(self):
        uid, how = sync_grades.match_row({"Email": "dup@example.edu"}, COLS, self.maps)
        self.assertIsNone(uid)
        self.assertEqual(how, "ambiguous_email")

    def test_ambiguous_email_falls_back_to_a_unique_sid(self):
        """A shared email must not block a row whose SID identifies one person."""
        row = {"Email": "dup@example.edu", "SID": "1003"}
        uid, how = sync_grades.match_row(row, COLS, self.maps)
        self.assertEqual((uid, how), (3, "sis"))

    def test_ambiguous_email_with_no_usable_sid_is_still_unmatched(self):
        row = {"Email": "dup@example.edu", "SID": ""}
        uid, how = sync_grades.match_row(row, COLS, self.maps)
        self.assertEqual((uid, how), (None, "ambiguous_email"))

    def test_ambiguous_sid_is_never_guessed(self):
        """The SID is now a deciding key, so it needs its own duplicate guard."""
        roster = [
            {"id": 10, "name": "A", "email": "a@example.edu", "sis_user_id": "SHARED"},
            {"id": 11, "name": "B", "email": "b@example.edu", "sis_user_id": "SHARED"},
        ]
        maps = sync_grades.build_roster_maps(roster)
        uid, how = sync_grades.match_row({"Email": "", "SID": "SHARED"}, COLS, maps)
        self.assertIsNone(uid)
        self.assertEqual(how, "ambiguous_sid")

    def test_both_keys_ambiguous_names_both(self):
        roster = [
            {"id": 10, "name": "A", "email": "dup@example.edu", "sis_user_id": "SHARED"},
            {"id": 11, "name": "B", "email": "dup@example.edu", "sis_user_id": "SHARED"},
        ]
        maps = sync_grades.build_roster_maps(roster)
        uid, how = sync_grades.match_row(
            {"Email": "dup@example.edu", "SID": "SHARED"}, COLS, maps)
        self.assertIsNone(uid)
        self.assertEqual(how, "ambiguous_email_and_sid")

    def test_unambiguous_email_still_wins_over_sid(self):
        """Precedence is unchanged: email first when it resolves cleanly."""
        row = {"Email": "ada@example.edu", "SID": "1002"}  # SID belongs to Alan
        uid, how = sync_grades.match_row(row, COLS, self.maps)
        self.assertEqual((uid, how), (1, "email"))

    def test_unknown_is_reported(self):
        uid, how = sync_grades.match_row({"Email": "nobody@example.edu"}, COLS, self.maps)
        self.assertIsNone(uid)
        self.assertEqual(how, "no_match")


class TestMatchingParity(unittest.TestCase):
    """mark_late and sync_grades read the same CSV; they must agree on identity.

    They used to agree because two copies of the matcher were kept in step by
    hand, and this test compared their answers case by case. There is now one
    copy, in canvas_common, and both scripts import it -- so comparing outputs
    would compare a function to itself. What is worth policing instead is the
    thing that would bring the drift back: either script quietly growing a
    private matcher again. So this asserts the *identity* of the function
    objects, and then exercises the shared one over the old cases to prove it
    still behaves.
    """

    def setUp(self):
        self.maps = canvas_common.build_roster_maps(ROSTER)

    def test_both_scripts_use_the_one_shared_matcher(self):
        self.assertIs(sync_grades.match_row, canvas_common.match_row)
        self.assertIs(mark_late.match_row, canvas_common.match_row)
        self.assertIs(mark_late.match_identity, canvas_common.match_row)
        self.assertIs(sync_grades.build_roster_maps, canvas_common.build_roster_maps)
        self.assertIs(mark_late.build_roster_maps, canvas_common.build_roster_maps)

        expected = {
            ("ada@example.edu", "1001"): (1, "email"),
            ("ada@example.edu", ""): (1, "email"),
            ("", "1002"): (2, "sis"),
            ("dup@example.edu", "1003"): (3, "sis"),      # ambiguous email, unique sid
            ("dup@example.edu", ""): (None, "ambiguous_email"),
            ("nobody@example.edu", "9999"): (None, "no_match"),
            ("", ""): (None, "no_match"),
            ("ADA@EXAMPLE.EDU", ""): (1, "email"),
        }
        for (email, sid), want in expected.items():
            row = {"Email": email, "SID": sid}
            self.assertEqual(sync_grades.match_row(row, COLS, self.maps), want,
                             f"wrong identity for email={email!r} sid={sid!r}")


class TestParseScore(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(sync_grades.parse_score("45"), 45.0)
        self.assertEqual(sync_grades.parse_score("45.5"), 45.5)
        self.assertEqual(sync_grades.parse_score(0), 0.0)

    def test_blank_is_none(self):
        self.assertIsNone(sync_grades.parse_score(""))
        self.assertIsNone(sync_grades.parse_score("   "))
        self.assertIsNone(sync_grades.parse_score(None))

    def test_non_numeric_is_none(self):
        self.assertIsNone(sync_grades.parse_score("Missing"))


class TestGradePlan(unittest.TestCase):
    def setUp(self):
        self.maps = sync_grades.build_roster_maps(ROSTER)

    def rows(self):
        return [
            {"Email": "ada@example.edu", "SID": "1001", "Total Score": "48", "Status": "Graded"},
            {"Email": "alan@example.edu", "SID": "1002", "Total Score": "", "Status": "Missing"},
            {"Email": "ghost@example.edu", "SID": "9999", "Total Score": "30", "Status": "Graded"},
        ]

    def test_blank_score_is_skipped_by_default(self):
        grade_data, matched, skipped, unmatched = sync_grades.build_grade_plan(
            self.rows(), COLS, self.maps, missing_zero=False)
        self.assertEqual(list(grade_data), ["1"])
        self.assertEqual(len(matched), 1)
        self.assertEqual(skipped[0]["reason"], "empty_score")
        self.assertEqual(len(unmatched), 1)

    def test_missing_zero_posts_zero(self):
        grade_data, matched, skipped, _ = sync_grades.build_grade_plan(
            self.rows(), COLS, self.maps, missing_zero=True)
        self.assertEqual(grade_data["2"]["posted_grade"], "0")
        self.assertEqual(len(skipped), 0)

    def test_unmatched_rows_are_never_posted(self):
        grade_data, _, _, unmatched = sync_grades.build_grade_plan(
            self.rows(), COLS, self.maps, missing_zero=True)
        self.assertNotIn("9999", grade_data)
        self.assertEqual(unmatched[0]["csv_identity"], "ghost@example.edu")

    def test_duplicate_row_is_flagged(self):
        rows = [
            {"Email": "ada@example.edu", "SID": "1001", "Total Score": "10", "Status": ""},
            {"Email": "ada@example.edu", "SID": "1001", "Total Score": "20", "Status": ""},
        ]
        grade_data, _, skipped, _ = sync_grades.build_grade_plan(
            rows, COLS, self.maps, missing_zero=False)
        self.assertEqual(grade_data["1"]["posted_grade"], "20")  # last wins
        self.assertTrue(any(s["reason"] == "duplicate_row_overwrote_earlier" for s in skipped))


class TestScoreFormatting(unittest.TestCase):
    """Was two private _fmt copies; is now canvas_common.fmt_score, reached
    through each script's namespace so a script that stops importing it fails
    here rather than in a gradebook."""

    def test_whole_numbers_have_no_decimal(self):
        self.assertEqual(sync_grades.fmt_score(45.0), "45")
        self.assertEqual(late_penalties.fmt_score(45.0), "45")

    def test_fractions_are_preserved(self):
        self.assertEqual(sync_grades.fmt_score(45.5), "45.5")


if __name__ == "__main__":
    unittest.main(verbosity=2)
