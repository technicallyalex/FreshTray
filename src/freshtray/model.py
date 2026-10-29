"""Input validation, local-date conversion and reminder decisions."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re


def display_reminder_time(stored):
    """Return (h:mm, AM/PM) without changing existing saved schedules."""
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", stored):
        raise ValueError("Invalid saved reminder time.")
    hour, minute = map(int, stored.split(":"))
    return f"{hour % 12 or 12}:{minute:02}", "PM" if hour >= 12 else "AM"


def parse_reminder_time(clock, period):
    """Validate 12-hour input and convert noon/midnight correctly for scheduling."""
    if not re.fullmatch(r"(?:0?[1-9]|1[0-2]):[0-5]\d", clock.strip()) or period not in ("AM", "PM"):
        raise ValueError("Enter a time such as 5:00 and choose AM or PM.")
    hour, minute = map(int, clock.strip().split(":"))
    return f"{hour % 12 + (12 if period == 'PM' else 0):02}:{minute:02}"


def duration_seconds(value):
    value = value.strip()
    try:
        if re.fullmatch(r"\d{1,2}:\d{2}", value):
            hours, minutes = map(int, value.split(":"))
            if minutes >= 60:
                raise ValueError()
            seconds = hours * 3600 + minutes * 60
        elif re.fullmatch(r"\d{1,2}(?:\.\d{1,4})?", value):
            seconds = int((Decimal(value) * 3600).quantize(Decimal("1")))
        else:
            raise ValueError()
    except (ValueError, InvalidOperation):
        raise ValueError("Enter hours as H:MM (8:00) or decimal hours (7.5).") from None
    if not 0 < seconds <= 86400:
        raise ValueError("Hours must be greater than zero and no more than 24.")
    return seconds


def utc_day_bounds(day):
    # astimezone() on each naive date asks Windows for that date's DST offset.
    start = datetime.combine(day, time.min).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min).astimezone(timezone.utc)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def entry_payload(client, day, hours, note, billable, identity, project=None, service=None):
    try:
        selected = date.fromisoformat(day)
    except ValueError:
        raise ValueError("Enter a valid date as YYYY-MM-DD.") from None
    if selected > date.today():
        raise ValueError("Choose today or an earlier entry date.")
    # A date-only entry is anchored at local noon so the date survives UTC conversion.
    started = datetime.combine(selected, time(12)).astimezone(timezone.utc)
    result = {"client_id": int(client), "identity_id": int(identity),
              "duration": duration_seconds(hours), "note": note.strip(),
              "billable": bool(billable), "billed": False, "internal": False,
              "is_logged": True, "started_at": started.isoformat().replace("+00:00", "Z")}
    if project:
        result["project_id"] = int(project)
    if service:
        result["service_id"] = int(service)
    return {"time_entry": result}


def reminder_due(settings, now):
    if not settings["reminders"] or settings["last_reminded"] == now.date().isoformat():
        return False
    if settings["weekdays_only"] and now.weekday() >= 5:
        return False
    try:
        scheduled = time.fromisoformat(settings["time"])
    except ValueError:
        return False
    return now.time() >= scheduled


def matching_entry(expected, actual):
    for key in ("client_id", "identity_id", "project_id", "service_id"):
        if str(expected.get(key) or "") != str(actual.get(key) or ""):
            return False
    try:
        same_time = datetime.fromisoformat(expected["started_at"].replace("Z", "+00:00")) == datetime.fromisoformat(actual["started_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    return (same_time and actual.get("active", True)
            and expected["duration"] == actual.get("duration")
            and expected["note"] == (actual.get("note") or "")
            and expected["billable"] == actual.get("billable"))
