import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit, urlencode
from urllib.error import HTTPError

import _paths  # Make src imports independent of the working directory.
from freshtray.api import FreshBooks, OAuthAttempt, ApiError, Transport, NoRedirect, DEFAULT_REDIRECT
from freshtray.model import duration_seconds, entry_payload, reminder_due, matching_entry, utc_day_bounds
from freshtray.storage import Vault, Preferences
from freshtray.model import display_reminder_time, parse_reminder_time


class MemoryVault:
    def __init__(self, **data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, **values):
        self.data.update(values)


CREDS = {"client_id": "test-app", "client_secret": "test-secret", "redirect_uri": DEFAULT_REDIRECT}


def pair(expiry=3600):
    return {"access_token": "access", "refresh_token": "one-use-refresh", "expires_at": time.time() + expiry}


def payload():
    return entry_payload(123, date.today().isoformat(), "8:00", "Work", True, 99)


class Inputs(unittest.TestCase):
    def test_hours(self):
        for value, seconds in [("8:00", 28800), ("7.5", 27000), ("0:01", 60), ("24:00", 86400), (" 1.25 ", 4500)]:
            self.assertEqual(duration_seconds(value), seconds)

    def test_bad_hours(self):
        for value in ["0", "0:00", "8:60", "-1", "25", "24:01", "1e2", "NaN", "inf", "8,5", "8:5", "", "1:999"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                duration_seconds(value)

    def test_payload_optional_fields_and_seconds(self):
        e = payload()["time_entry"]
        self.assertEqual(e["duration"], 28800)
        self.assertNotIn("service_id", e)
        self.assertNotIn("project_id", e)
        local = datetime.fromisoformat(e["started_at"].replace("Z", "+00:00")).astimezone()
        self.assertEqual(local.date(), date.today())
        self.assertEqual(local.hour, 12)
        self.assertTrue(e["billable"])
        e = entry_payload(1, "2026-01-01", "1", " note ", False, 2, 3, 4)["time_entry"]
        self.assertEqual((e["note"], e["project_id"], e["service_id"]), ("note", 3, 4))
        self.assertFalse(e["billable"])

    def test_invalid_date(self):
        for value in ["2026-02-30", "10/28/2026", (date.today() + timedelta(days=1)).isoformat()]:
            with self.assertRaises(ValueError):
                entry_payload(1, value, "8", "", True, 2)

    def test_dst_day_lengths_windows_eastern(self):
        # This workstation uses Eastern time; test transitions only on that zone.
        if datetime(2026, 1, 1).astimezone().utcoffset() != timedelta(hours=-5):
            self.skipTest("Eastern local timezone required")
        for day, hours in [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)]:
            a, b = utc_day_bounds(day)
            self.assertEqual((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds(), hours * 3600)

    def test_matching_normalizes_ids_and_dates(self):
        expected = payload()["time_entry"]
        actual = dict(expected, client_id="123", id=7, started_at=expected["started_at"].replace("Z", "+00:00"))
        self.assertTrue(matching_entry(expected, actual))
        for changed in [dict(actual, active=False), dict(actual, duration=1), dict(actual, identity_id=4), dict(actual, note="other"), dict(actual, billable=False)]:
            self.assertFalse(matching_entry(expected, changed))

    def test_reminder_time_preserves_all_existing_minutes(self):
        for minute in range(24 * 60):
            stored = f"{minute // 60:02}:{minute % 60:02}"
            clock, period = display_reminder_time(stored)
            self.assertEqual(parse_reminder_time(clock, period), stored)
        self.assertEqual(display_reminder_time("00:00"), ("12:00", "AM"))
        self.assertEqual(display_reminder_time("12:00"), ("12:00", "PM"))
        self.assertEqual(display_reminder_time("17:00"), ("5:00", "PM"))

    def test_invalid_reminder_clock_is_rejected(self):
        for clock, period in [("0:00", "AM"), ("13:00", "PM"), ("5:60", "AM"),
                              ("5", "PM"), ("5:00", ""), ("5:00", "XX"), ("5:0", "AM")]:
            with self.subTest(clock=clock, period=period), self.assertRaises(ValueError):
                parse_reminder_time(clock, period)

    def test_reminder_catches_up_once_per_day(self):
        config = {"reminders": True, "time": "17:00", "weekdays_only": True, "last_reminded": ""}
        self.assertFalse(reminder_due(config, datetime(2026, 10, 28, 16, 59)))
        self.assertTrue(reminder_due(config, datetime(2026, 10, 28, 18)))
        self.assertFalse(reminder_due(dict(config, last_reminded="2026-10-28"), datetime(2026, 10, 28, 19)))
        self.assertFalse(reminder_due(config, datetime(2026, 10, 31, 18)))
        self.assertTrue(reminder_due(dict(config, weekdays_only=False), datetime(2026, 10, 31, 18)))
        self.assertFalse(reminder_due(dict(config, reminders=False), datetime(2026, 10, 28, 18)))


class OAuthTests(unittest.TestCase):
    def returned(self, attempt, **kwargs):
        return DEFAULT_REDIRECT + "?" + urlencode(dict(state=attempt.state, code="one-use-code", **kwargs))

    def test_url_and_single_use(self):
        a = OAuthAttempt(CREDS)
        query = parse_qs(urlsplit(a.url()).query)
        self.assertEqual(query["redirect_uri"], [DEFAULT_REDIRECT])
        self.assertIn("user:time_entries:write", query["scope"][0])
        self.assertNotIn(CREDS["client_secret"], a.url())
        self.assertEqual(a.consume(self.returned(a)), "one-use-code")
        with self.assertRaises(ValueError):
            a.consume(self.returned(a))

    def test_invalid_returns(self):
        a = OAuthAttempt(CREDS)
        values = ["one-use-code", self.returned(a).replace("localhost", "evil.invalid"),
                  DEFAULT_REDIRECT + "?code=x&state=wrong", self.returned(a) + "&state=extra",
                  self.returned(a) + "&code=extra", self.returned(a) + "#fragment",
                  self.returned(a).replace("https:", "http:")]
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.consume(value)

    def test_expiry(self):
        a = OAuthAttempt(CREDS)
        a.created -= 301
        with self.assertRaises(ValueError):
            a.consume(self.returned(a))

    def test_invalid_redirect(self):
        for value in ["http://localhost/cb", "https://localhost/cb?q=1", "https://user@localhost/cb", "https://localhost/cb#x"]:
            with self.assertRaises(ValueError):
                OAuthAttempt(dict(CREDS, redirect_uri=value))

    def test_exchange_and_storage(self):
        a, calls = OAuthAttempt(CREDS), []
        def transport(*args):
            calls.append(args)
            return dict(access_token="new-a", refresh_token="new-r", expires_in=400)
        vault = MemoryVault()
        FreshBooks(vault, transport).connect(a, self.returned(a))
        self.assertEqual(calls[0][2]["grant_type"], "authorization_code")
        self.assertEqual(vault.get("tokens")["refresh_token"], "new-r")
        self.assertFalse(vault.get("refresh_inflight"))


class ApiTests(unittest.TestCase):
    def test_rotates_refresh_once_under_concurrency(self):
        vault = MemoryVault(tokens=pair(-1), credentials=CREDS)
        calls = []
        def transport(method, path, body=None, token=None):
            calls.append(path)
            if path.endswith("/token"):
                time.sleep(0.02)
                return dict(access_token="rotated", refresh_token="rotated-r", expires_in=3600)
            self.assertEqual(token, "rotated")
            return {}
        api = FreshBooks(vault, transport)
        threads = [threading.Thread(target=api.request, args=("GET", "/test")) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(calls.count("/auth/oauth/token"), 1)
        self.assertEqual(vault.get("tokens")["refresh_token"], "rotated-r")

    def test_uncertain_refresh_is_never_retried(self):
        vault, calls = MemoryVault(tokens=pair(-1), credentials=CREDS), []
        def failed(*args):
            calls.append(args)
            raise ApiError("Timeout", uncertain=True)
        api = FreshBooks(vault, failed)
        for _ in range(2):
            with self.assertRaises(ApiError):
                api.request("GET", "/test")
        self.assertEqual(len(calls), 1)
        self.assertTrue(vault.get("refresh_inflight"))

    def test_post_journal_before_network_and_success(self):
        vault = MemoryVault(tokens=pair())
        def transport(method, path, body=None, token=None):
            self.assertEqual(vault.get("pending")["payload"], body)
            self.assertEqual(path, "/timetracking/business/7/time_entries")
            return {"time_entry": {"id": 10}}
        result = FreshBooks(vault, transport).submit(7, payload())
        self.assertEqual(result["id"], 10)
        self.assertIsNone(vault.get("pending"))
        self.assertEqual(vault.get("last_success")["id"], 10)

    def test_error_pending_policy(self):
        for status, uncertain in [(400, False), (401, False), (403, False), (422, False), (429, False), (302, True), (500, True), (408, True), (None, True)]:
            with self.subTest(status=status):
                vault, calls = MemoryVault(tokens=pair()), []
                def failed(*args):
                    calls.append(args)
                    raise ApiError("Sanitized error", status, uncertain)
                api = FreshBooks(vault, failed)
                with self.assertRaises(ApiError):
                    api.submit(7, payload())
                self.assertEqual(bool(vault.get("pending")), uncertain)
                self.assertEqual(len(calls), 1)
                if uncertain:
                    with self.assertRaises(ApiError):
                        api.submit(7, payload())
                    self.assertEqual(len(calls), 1)

    def test_pending_recovery(self):
        pending = {"business_id": 7, "payload": payload()}
        vault = MemoryVault(tokens=pair(), pending=pending)
        expected = dict(payload()["time_entry"], id=800)
        def transport(method, path, body=None, token=None):
            self.assertEqual(method, "GET")
            return {"time_entries": [expected], "meta": {"pages": 1}}
        found = FreshBooks(vault, transport).check_pending()
        self.assertEqual(found["id"], 800)
        self.assertIsNone(vault.get("pending"))

    def test_pending_no_match_or_multiple_preserved(self):
        for entries in [[], [dict(payload()["time_entry"], id=1), dict(payload()["time_entry"], id=2)]]:
            vault = MemoryVault(tokens=pair(), pending={"business_id": 7, "payload": payload()})
            api = FreshBooks(vault, lambda *args: {"time_entries": entries})
            self.assertTrue(api.check_pending()["unresolved"])
            self.assertIsNotNone(vault.get("pending"))

    def test_pending_can_reconnect_after_expired_refresh(self):
        a = OAuthAttempt(CREDS)
        vault = MemoryVault(pending={"business_id": 7, "payload": payload()}, refresh_inflight=True)
        api = FreshBooks(vault, lambda *args: dict(access_token="a", refresh_token="r", expires_in=99))
        api.connect(a, DEFAULT_REDIRECT + "?" + urlencode({"state": a.state, "code": "code"}))
        self.assertIsNotNone(vault.get("pending"))
        self.assertTrue(api.connected)

    def test_pagination_both_envelopes(self):
        for accounting in [True, False]:
            pages = []
            def transport(method, path, body=None, token=None):
                n = int(parse_qs(urlsplit(path).query)["page"][0])
                pages.append(n)
                root = {"items": [{"id": n}], "pages": 2} if accounting else {"items": [{"id": n}], "meta": {"pages": 2}}
                return {"response": {"result": root}} if accounting else root
            result = FreshBooks(MemoryVault(tokens=pair()), transport).pages("/list", "items", accounting)
            self.assertEqual([r["id"] for r in result], [1, 2])
            self.assertEqual(pages, [1, 2])

    def test_revoke_failure_keeps_credentials(self):
        vault = MemoryVault(tokens=pair(), credentials=CREDS)
        def failed(*args):
            raise ApiError("Offline")
        with self.assertRaises(ApiError):
            FreshBooks(vault, failed).disconnect()
        self.assertIsNotNone(vault.get("tokens"))

    def test_revoke_success_erases_credentials(self):
        vault = MemoryVault(tokens=pair(), credentials=CREDS)
        FreshBooks(vault, lambda *args: {}).disconnect()
        self.assertIsNone(vault.get("tokens"))
        self.assertIsNone(vault.get("credentials"))

    def test_transport_no_redirects_and_no_content_type_on_get(self):
        transport = Transport()
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size):
                return b'{}'
        class Opener:
            def open(self, request, timeout):
                self.request = request
                return Response()
        opener = Opener()
        transport.opener = opener
        transport("GET", "/test", token="private")
        self.assertFalse(opener.request.has_header("Content-type"))
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer private")
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))


@unittest.skipUnless(os.name == "nt", "Windows DPAPI")
class StorageTests(unittest.TestCase):
    def test_encryption_roundtrip_and_no_plaintext(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "vault.dpapi"
            vault = Vault(path)
            vault.update(tokens=pair(), credentials=CREDS, pending={"note": "PRIVATE-NOTE"})
            raw = path.read_bytes()
            for value in [b"one-use-refresh", b"test-secret", b"PRIVATE-NOTE"]:
                self.assertNotIn(value, raw)
            self.assertEqual(Vault(path).get("credentials"), CREDS)
            self.assertFalse(path.with_suffix(".dpapi.tmp").exists())

    def test_corrupt_vault_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "vault.dpapi"
            path.write_bytes(b"not-encrypted")
            with self.assertRaises(OSError):
                Vault(path)

    def test_preferences_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            Preferences(path).save(time="18:15", weekdays_only=False)
            p = Preferences(path)
            self.assertEqual(p.data["time"], "18:15")
            self.assertFalse(p.data["weekdays_only"])


if __name__ == "__main__":
    unittest.main()
