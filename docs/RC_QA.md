# 0.3 RC1 verification

This release candidate is for timer testing and issue reports. [0.2 remains the recommended stable release](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2).

## Scope and results

- 140 automated core, offline, update, screen-boundary and timer recovery tests passed.
- The Qt lifecycle smoke test passed entry creation/editing, cached navigation, failed-load recovery, date selection, reminders and panel/theme layouts.
- The actual timer adapter was tested through the encrypted offline queue and a fake FreshBooks transport: reviewed duration is retained, reconnection submits one entry, and a visible calendar refreshes after a popout save.
- Native Windows timer checks passed pause/resume, restart recovery, exact reviewed seconds, all four faces, idle popout, condensed mode, opacity, screen containment, frozen idle rendering, and hover-hint placement/fading.
- 72 layout cases passed across light/dark themes, normal/compact work areas and 100%/150% scaling. These include the Timer panel and connection/recovery settings.
- Update UI tests passed notes, dismissal, download progress, installation guards and handoff using fake releases. Version tests confirm stable 0.3 can replace this RC and stable clients ignore prereleases.
- The single-file executable is checked separately for startup with an isolated synthetic profile. Release archives use an explicit file allowlist and contain no account profile, vault, cache, logs or model assets.

## Issues corrected

- A timer no longer starts if its first encrypted checkpoint fails.
- Timer request IDs and durable local receipts prevent duplicate queueing after an interruption; an interruption before queueing retains reviewed time for retry.
- Invalid reviewed duration blocks submission rather than silently logging the previous duration.
- Timer drafts are debounced for persistence and retained across quit/restart. Optional malformed timer preferences fall back safely.
- Popout saves refresh an open monthly view, and adding/removing entries no longer changes the calendar allocation.
- RC version parsing and resource metadata are consistent with the prerelease tag.

## Limits

No live customer time entries were created during verification. Provider acceptance, billing effects and account permissions need tester confirmation with intentional entries. Extended unattended operation and physical mixed-DPI multi-monitor combinations are not established by this QA pass.

The stopwatch is local, not a synchronized FreshBooks web timer. Running sessions include time while FreshTray is closed. Entries are limited to 24 hours, retain their actual start timestamp, and are not automatically split at midnight. See [TIMER.md](TIMER.md).
