# FreshTray 0.3 RC3 — popup entry testing prerelease

**For testing and reporting issues. Most users should stay on [0.2](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2). This is not the stable 0.3 release.**

- **Log hours** in the reminder now turns the popup into a one-use entry form instead of opening the main window. Choose business/client, optional project/service, date, hours, note and billable status.
- A successful encrypted local save shows a brief confirmation, starts background sync and closes only the popup. Offline entries remain queued for reconnection. Validation and local-storage failures keep the form open.
- The reminder draft is separate from the main-window draft. Cancel closes without saving. Date picking and duplicate confirmations stay in the popup.
- Closing the popup cancels a pending duplicate confirmation. Log hours waits for any current operation to finish before opening the form.

Includes RC2's immediate sync and repeating reminder sounds, plus RC1's timer panel and stopwatch popout. See [USAGE.md](USAGE.md), [TIMER.md](TIMER.md) and [RC_QA.md](RC_QA.md).

---

# FreshTray 0.3 RC2 — timer testing prerelease

**For testing and reporting issues. Most users should stay on [0.2](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2). This is not the stable 0.3 release.**

- Entry additions, edits, deletions and timer saves now start background sync immediately after their encrypted local save, rather than waiting for the periodic check.
- Removed routine save/sync confirmations. Connection failures show a notice that changes are saved locally and will sync once connected. Repeated retries do not repeat the same notice; conflicts and uncertain submissions still require review.
- Added **Repeat** in Sound options for both main and follow-up reminder popups. Closing the popup, choosing Remind me or opening Log hours stops playback. Sound previews play once.
- Renamed the reminder's Later button to **Dismiss** and moved the timer popout drag handle to the upper-right corner.

Includes RC1's timer panel, four elapsed-time faces, independent stopwatch popout, and encrypted timer recovery. The timer runs locally, not in sync with a running FreshBooks website timer. See [TIMER.md](TIMER.md) and [RC_QA.md](RC_QA.md).

---

# FreshTray 0.3 RC1 — timer testing prerelease

**Intended for testing and reporting issues. Most users should stay on [0.2](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2). This is not the stable 0.3 release.**

- Added a dedicated Timer panel with start, pause/resume, reviewed duration and logging through the existing offline-safe save flow.
- Added an independent stopwatch popout, four elapsed-time faces, animated face previews, condensed mode, opacity and pinning.
- Added durable timer recovery and local request receipts to prevent duplicate timer saves after interruptions.
- Fixed popout screen bounds, hover-hint placement, control alignment and changing calendar height as entries are added.
- Included opt-out update checks with notes, verified downloads and an explicit install/restart step. Prereleases stay off the stable update channel.

The timer runs locally; it does not synchronize a running timer with FreshBooks' website. Entries are limited to 24 hours and are not split automatically at midnight. See the [timer testing guide](TIMER.md).

## Earlier development build: 0.2.1

- Added in-app update checks, patch notes, download progress, dismissal and an explicit install/restart step.
- Added optional daily startup checks, verified downloads and a portable replacement helper with startup acknowledgement and rollback.
- Account settings and offline changes remain in the existing Windows profile. This build is local only; no release has been published.

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

Download the portable executable and documentation bundle from the [0.2 release](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2).

# FreshTray 0.1

Initial Windows tray time logger with FreshBooks connection, monthly hours and configurable reminders.
