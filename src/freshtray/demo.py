"""An explicit offline preview with editable sample calendar data; no network."""
from copy import deepcopy
from datetime import date, datetime, time, timezone
import calendar

from .api import ApiError
from .history_model import month_after, month_entries, entry_signature, edit_restriction


class Demo:
    connected = True

    def __init__(self):
        self.entries = {}
        self.next_id = 1000
        today = date.today()
        for month in (today.replace(day=1), month_after(today.replace(day=1), -1)):
            for number in range(1, calendar.monthrange(month.year, month.month)[1] + 1):
                day = month.replace(day=number)
                if day > today or day.weekday() >= 5:
                    continue
                started = datetime.combine(day, time(9)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                self.submit(1, {"time_entry": {"client_id": 1, "identity_id": 42, "project_id": 1,
                    "service_id": 1, "duration": (7 + number % 3) * 3600, "note": "Video editing and thumbnails",
                    "started_at": started, "billable": True, "billed": False, "is_logged": True, "internal": False}})

    def profile(self):
        return {"id": 42, "first_name": "Jamie", "last_name": "Sample",
                "business_memberships": [{"role": "owner", "business": {
                    "id": 1, "account_id": "demo", "name": "Preview business"}}]}

    def catalog(self, business):
        return ([{"id": 1, "organization": "Example Studio"}],
                [{"id": 1, "client_id": 1, "title": "Video production", "services": [{"id": 1, "name": "Editing"}]}],
                [{"id": 1, "name": "Editing"}, {"id": 2, "name": "Thumbnail design"}], [])

    def submit(self, business, payload):
        self.next_id += 1
        entry = {"id": self.next_id, "active": True, **deepcopy(payload["time_entry"])}
        self.entries[entry["id"]] = entry
        return deepcopy(entry)

    def entries_for_month(self, business, month, identity):
        return deepcopy(month_entries(list(self.entries.values()), month, identity))

    def get_entry(self, business, entry_id):
        return deepcopy(self.entries[int(entry_id)])

    def update_entry(self, business, entry_id, payload, original):
        current = self.get_entry(business, entry_id)
        if entry_signature(current) != entry_signature(original):
            raise ApiError("This entry changed elsewhere. Reload it before editing.")
        if edit_restriction(current):
            raise ApiError(edit_restriction(current))
        self.entries[int(entry_id)].update(deepcopy(payload["time_entry"]))
        return self.get_entry(business, entry_id)

    def check_pending(self):
        return None

    def disconnect(self):
        raise ApiError("Preview mode has no FreshBooks connection to disconnect.")
