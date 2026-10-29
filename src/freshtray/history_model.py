"""Calendar grouping and safe editing of existing logged time."""
import calendar
from datetime import date, datetime, time, timezone
from decimal import Decimal

from .model import entry_payload, utc_day_bounds


def month_after(month, offset=1):
    year, index = divmod(month.year * 12 + month.month - 1 + offset, 12)
    return date(year, index + 1, 1)


def month_bounds(month):
    first = month.replace(day=1)
    return utc_day_bounds(first)[0], utc_day_bounds(month_after(first))[0]


def entry_datetime(entry):
    parsed = datetime.fromisoformat(entry["started_at"].replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def entry_date(entry):
    return entry_datetime(entry).astimezone().date()


def month_entries(entries, month, identity_id):
    result = []
    for entry in entries:
        if not entry.get("active", True) or not entry.get("is_logged", True):
            continue
        if (entry.get("timer") or {}).get("is_running"):
            continue
        if str(entry.get("identity_id", identity_id)) != str(identity_id):
            continue
        try:
            day = entry_date(entry)
            duration = int(entry.get("duration") or 0)
        except (ValueError, KeyError, TypeError):
            raise ValueError("A FreshBooks entry has an unreadable date or duration. Refresh before editing.") from None
        if (day.year, day.month) == (month.year, month.month) and duration >= 0:
            result.append(entry)
    return sorted(result, key=lambda e: (entry_datetime(e), str(e["id"])))


def day_totals(entries):
    totals = {}
    for entry in entries:
        day = entry_date(entry)
        totals[day] = totals.get(day, 0) + int(entry.get("duration") or 0)
    return totals


def format_duration(seconds):
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02}" + (f":{seconds:02}" if seconds else "")


def hours_input(seconds):
    seconds = int(seconds or 0)
    if seconds % 60 == 0:
        return format_duration(seconds)
    return format((Decimal(seconds) / 3600).quantize(Decimal("0.0001")), "f").rstrip("0").rstrip(".")


def edit_restriction(entry):
    if not entry.get("active", True):
        return "This entry was deleted or archived. Refresh the calendar."
    if not entry.get("is_logged", True) or (entry.get("timer") or {}).get("is_running"):
        return "Finish this running timer in FreshBooks before editing it here."
    if entry.get("internal") or not entry.get("client_id"):
        return "This entry has no client. Edit internal time directly in FreshBooks."
    return ""


def entry_signature(entry):
    """Compare editable state plus billing/timer state, independent of JSON ID types."""
    return (tuple(str(entry.get(k) or "") for k in ("client_id", "project_id", "service_id", "identity_id")),
            entry_datetime(entry), int(entry.get("duration") or 0), entry.get("note") or "",
            bool(entry.get("billable")), bool(entry.get("billed")), bool(entry.get("internal")),
            bool(entry.get("active", True)), bool(entry.get("is_logged", True)),
            bool((entry.get("timer") or {}).get("is_running")))


def edit_payload(original, client, day, hours, note, billable, identity, project=None, service=None):
    result = entry_payload(client, day, hours, note, billable, identity, project, service)
    fields = result["time_entry"]
    fields["note"] = note  # Preserve existing note whitespace during hour-only edits.
    # Never rewrite billing/internal state as a side effect of a note/duration edit.
    fields.pop("billed")
    fields.pop("internal")
    local = entry_datetime(original).astimezone()
    chosen = date.fromisoformat(day)
    if chosen == local.date():
        started = entry_datetime(original)
    else:
        started = datetime.combine(chosen, local.time().replace(tzinfo=None)).astimezone(timezone.utc)
    fields["started_at"] = started.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    # Explicit nulls allow clearing an optional assignment on PUT.
    fields["project_id"] = int(project) if project else None
    fields["service_id"] = int(service) if service else None
    return result
