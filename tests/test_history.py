from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import time
import unittest
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError
import _paths  # Make src imports independent of the working directory.
from freshtray.api import Transport

from freshtray.api import ApiError, FreshBooks
from freshtray.history_model import (month_after, month_bounds, entry_date, month_entries,
    day_totals, format_duration, hours_input, edit_payload, entry_signature)
from freshtray.model import duration_seconds, matching_entry
from test_core import MemoryVault, pair


def record(ident=1, day=date(2026, 9, 1), **changes):
    from freshtray.model import entry_payload
    value = entry_payload(1, day.isoformat(), "8:00", "Original", True, 42, 2, 3)["time_entry"]
    return dict(value, id=ident, active=True, **changes)


class CalendarModelTests(unittest.TestCase):
    def test_month_year_and_leap_navigation(self):
        self.assertEqual(month_after(date(2025, 12, 1)), date(2026, 1, 1))
        self.assertEqual(month_after(date(2026, 1, 1), -1), date(2025, 12, 1))
        a, b = month_bounds(date(2024, 2, 20))
        self.assertEqual(datetime.fromisoformat(a).astimezone().date(), date(2024, 2, 1))
        self.assertEqual(datetime.fromisoformat(b).astimezone().date(), date(2024, 3, 1))

    def test_local_month_filtering_and_daily_sum(self):
        a = record(1)
        b = record(2)
        b["duration"] = 5400
        wrong_user = dict(a, id=5, identity_id=99)
        candidates = [a, b, dict(a, id=3, active=False), dict(a, id=4, is_logged=False), wrong_user,
                      record(6, date(2026, 8, 31)), record(7, date(2026, 10, 1))]
        included = month_entries(candidates, date(2026, 9, 1), 42)
        self.assertEqual([e["id"] for e in included], [1, 2])
        self.assertEqual(day_totals(included), {date(2026, 9, 1): 34200})
        self.assertEqual(format_duration(34200), "9:30")

    def test_utc_rollover_uses_windows_local_date(self):
        if datetime(2026, 9, 1).astimezone().utcoffset() != timedelta(hours=-4):
            self.skipTest("Eastern local timezone required")
        value = record()
        value["started_at"] = "2026-10-01T02:00:00Z"
        self.assertEqual(entry_date(value), date(2026, 9, 30))
        self.assertEqual(len(month_entries([value], date(2026, 9, 1), 42)), 1)
        value["started_at"] = "2026-09-01T02:00:00Z"
        self.assertEqual(month_entries([value], date(2026, 9, 1), 42), [])

    def test_edit_hours_preserve_seconds(self):
        for seconds in (1, 59, 60, 3599, 3600, 28801, 86399, 86400):
            self.assertEqual(duration_seconds(hours_input(seconds)), seconds)
        self.assertEqual(format_duration(28801), "8:00:01")
        self.assertEqual(format_duration(100 * 3600), "100:00")

    def test_edit_preserves_start_time_and_can_clear_assignments(self):
        original = record()
        original["started_at"] = "2026-09-01T13:17:23Z"
        payload = edit_payload(original, 1, "2026-09-01", "7:30", "Updated", False, 42)
        value = payload["time_entry"]
        self.assertEqual(value["started_at"], original["started_at"])
        self.assertEqual(value["duration"], 27000)
        self.assertIsNone(value["project_id"])
        self.assertIsNone(value["service_id"])
        self.assertNotIn("billed", value)
        self.assertNotIn("internal", value)

    def test_moving_date_preserves_local_clock_across_dst(self):
        original = record(day=date(2026, 3, 7))
        original["started_at"] = datetime(2026, 3, 7, 9, 30).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        changed = edit_payload(original, 1, "2026-03-08", "8", "Updated", True, 42)["time_entry"]
        local = datetime.fromisoformat(changed["started_at"]).astimezone()
        self.assertEqual((local.date(), local.hour, local.minute), (date(2026, 3, 8), 9, 30))


class HistoryApiTests(unittest.TestCase):
    def test_read_validation_error_does_not_blame_entry_fields(self):
        class RejectedRead:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 422, "Unprocessable Entity", {}, None)
        transport = Transport()
        transport.opener = RejectedRead()
        with self.assertRaisesRegex(ApiError, "filters or date range"):
            transport("GET", "/timetracking/business/7/time_entries", token="test-token")
        with self.assertRaisesRegex(ApiError, "client/project/service"):
            transport("POST", "/timetracking/business/7/time_entries", {}, "test-token")

    def test_month_read_uses_current_user_default_and_dates_with_pagination(self):
        calls = []
        def transport(method, path, body=None, token=None):
            self.assertEqual(method, "GET")
            query = parse_qs(urlsplit(path).query)
            self.assertNotIn("identity_id", query)
            self.assertNotIn("team", query)
            self.assertEqual(query["include_unlogged"], ["false"])
            self.assertEqual(query["include_deleted"], ["false"])
            self.assertEqual(query["started_from"], [month_bounds(date(2026, 9, 1))[0]])
            page = int(query["page"][0])
            calls.append(page)
            # Defensive filtering must still exclude another identity if returned.
            other = record(page + 100)
            other["identity_id"] = 99
            return {"time_entries": [record(page), other], "meta": {"pages": 2}}
        entries = FreshBooks(MemoryVault(tokens=pair()), transport).entries_for_month(7, date(2026, 9, 1), 42)
        self.assertEqual(len(entries), 2)
        self.assertEqual(calls, [1, 2])

    def test_update_targets_existing_id_and_journals_before_put(self):
        original, calls = record(10), []
        payload = edit_payload(original, 1, "2026-09-01", "7", "Changed", True, 42, 2, 3)
        vault = MemoryVault(tokens=pair())
        def transport(method, path, body=None, token=None):
            calls.append((method, path))
            self.assertEqual(path, "/timetracking/business/7/time_entries/10")
            if method == "GET":
                return {"time_entry": original}
            self.assertEqual(method, "PUT")
            self.assertEqual(vault.get("pending")["operation"], "update")
            self.assertEqual(vault.get("pending")["entry_id"], 10)
            return {"time_entry": dict(original, **payload["time_entry"])}
        result = FreshBooks(vault, transport).update_entry(7, 10, payload, original)
        self.assertEqual(result["id"], 10)
        self.assertEqual([method for method, path in calls], ["GET", "PUT"])
        self.assertIsNone(vault.get("pending"))

    def test_billed_update_preserves_status_without_rewriting_billing(self):
        original = record(10, billed=True)
        payload = edit_payload(original, 1, "2026-09-01", "7", "Correction", True, 42, 2, 3)
        calls = []
        def transport(method, path, body=None, token=None):
            calls.append(method)
            if method == "GET":
                return {"time_entry": original}
            self.assertNotIn("billed", body["time_entry"])
            self.assertNotIn("internal", body["time_entry"])
            return {"time_entry": dict(original, **body["time_entry"])}
        result = FreshBooks(MemoryVault(tokens=pair()), transport).update_entry(7, 10, payload, original)
        self.assertTrue(result["billed"])
        self.assertEqual(result["duration"], 25200)
        self.assertEqual(calls, ["GET", "PUT"])

    def test_billing_state_changed_since_opening_rejects_update(self):
        original = record(10, billed=False)
        calls = []
        def transport(method, *args):
            calls.append(method)
            return {"time_entry": dict(original, billed=True)}
        with self.assertRaisesRegex(ApiError, "changed in FreshBooks"):
            FreshBooks(MemoryVault(tokens=pair()), transport).update_entry(7, 10,
                edit_payload(original, 1, "2026-09-01", "7", "Correction", True, 42), original)
        self.assertEqual(calls, ["GET"])

    def test_external_change_prevents_overwrite(self):
        original, calls = record(), []
        def transport(method, *args):
            calls.append(method)
            return {"time_entry": dict(original, note="Changed elsewhere")}
        with self.assertRaisesRegex(ApiError, "changed in FreshBooks"):
            FreshBooks(MemoryVault(tokens=pair()), transport).update_entry(7, 1,
                edit_payload(original, 1, "2026-09-01", "8", "My edit", True, 42), original)
        self.assertEqual(calls, ["GET"])

    def test_read_only_and_wrong_identity_entries_never_put(self):
        for field in ({"internal": True}, {"identity_id": 99}, {"is_logged": False}, {"active": False}):
            original = record()
            original.update(field)
            methods = []
            def transport(method, *args):
                methods.append(method)
                return {"time_entry": original}
            with self.assertRaises(ApiError):
                FreshBooks(MemoryVault(tokens=pair()), transport).update_entry(7, 1,
                    edit_payload(original, 1, "2026-09-01", "8", "Changed", True, 42), original)
            self.assertEqual(methods, ["GET"])

    def test_uncertain_update_requires_readback_and_never_retries(self):
        original = record(10)
        payload = edit_payload(original, 1, "2026-09-01", "6", "Changed", False, 42, 2, 3)
        vault = MemoryVault(tokens=pair())
        state = {"entry": deepcopy(original), "puts": 0}
        def transport(method, path, body=None, token=None):
            if method == "GET":
                return {"time_entry": deepcopy(state["entry"])}
            state["puts"] += 1
            state["entry"].update(body["time_entry"])
            raise ApiError("Timed out", uncertain=True)
        api = FreshBooks(vault, transport)
        with self.assertRaises(ApiError):
            api.update_entry(7, 10, payload, original)
        self.assertIsNotNone(vault.get("pending"))
        with self.assertRaises(ApiError):
            api.submit(7, payload)
        self.assertEqual(api.check_pending()["id"], 10)
        self.assertIsNone(vault.get("pending"))
        self.assertEqual(state["puts"], 1)

    def test_unconfirmed_update_is_kept_pending(self):
        original = record(10)
        payload = edit_payload(original, 1, "2026-09-01", "6", "Changed", False, 42)
        vault = MemoryVault(tokens=pair(), pending={"operation": "update", "entry_id": 10, "business_id": 7, "payload": payload})
        api = FreshBooks(vault, lambda *args: {"time_entry": original})
        self.assertTrue(api.check_pending()["unresolved"])
        self.assertIsNotNone(vault.get("pending"))

    def test_rejected_update_releases_guard_without_retry(self):
        original = record()
        vault = MemoryVault(tokens=pair())
        def transport(method, *args):
            if method == "GET":
                return {"time_entry": original}
            raise ApiError("Rejected", 422, False)
        with self.assertRaises(ApiError):
            FreshBooks(vault, transport).update_entry(7, 1,
                edit_payload(original, 1, "2026-09-01", "6", "Changed", False, 42), original)
        self.assertIsNone(vault.get("pending"))


if __name__ == "__main__":
    unittest.main()
