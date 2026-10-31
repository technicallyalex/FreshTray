# FreshTray 0.2 — a complete overhaul

FreshTray has been rebuilt around a new UI framework, with a more polished design and a richer reminder experience.

## Rebuilt with Qt Quick

The interface now uses PySide6 and Qt Quick, with display-aware layouts, reusable controls and animated panel resizing. Panels stay loaded between visits, and cached data avoids unnecessary requests while navigating.

## A cleaner interface

Folder-style tabs, consistent spacing, rounded controls and coordinated light/dark themes bring the app together. Monthly hours combines the calendar and entry form, with entry indicators, distinct weekly totals and edit/delete actions beside saved entries.

## Enhanced reminders

A dedicated popup opens independently of Windows notification banners. It includes an animated punchcard, a clock showing the time it opened, remembered draggable placement, and a configurable Remind me timer. Choose separate daily/follow-up sounds from nine original options and adjust their volume.

## Also included

- Single portable Windows x64 executable.
- Offline additions, edits and deletions with encrypted local storage and automatic reconnection sync.
- Remembered business/client choices and alphabetical or recently used sorting.
- Settings that apply automatically.

## Updating

Finish syncing pending changes, quit the previous tray copy, then run **FreshTray-0.2.exe**. Your profile stays in `%LOCALAPPDATA%/FreshTray`. If the EXE moved, update the startup option from its new location. Do not downgrade while local changes are waiting to sync.

This PR prepares 0.2 for review; it does not publish the release or replace the existing 0.1 download.

# FreshTray 0.1

Initial Windows tray time logger with FreshBooks connection, monthly hours and configurable reminders.
