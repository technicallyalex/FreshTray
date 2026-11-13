# 0.3 RC3 verification

This release candidate is for testing and issue reports. [0.2 remains the recommended stable release](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2).

## Scope and results

- 141 automated tests passed, covering core behavior, encrypted offline queue, updates, audio, timer recovery and screen bounds.
- Native Windows timer checks passed pause/resume, restart recovery, exact reviewed duration, four faces, independent idle popout, compact mode, opacity, screen containment and hover hints.
- Native popup-entry checks passed isolated drafts, validation, local-storage failure recovery, online/offline saves, confirmation, auto-close, cancel, date picking and duplicate review. No main window is opened by the reminder form.
- 72 layout cases passed at 100%/150% scaling across light/dark themes and normal/compact work areas. The popup form was also reviewed in light mode and in a short dark window; overflow remains scrollable on small desktops.
- Synthetic offline UI checks passed add/edit/delete, timer saves, immediate online sync, reconnection, conflict review and quiet success with deduplicated issue notices.
- Reminder checks passed scheduled, test and follow-up delivery with suppressed/failed Windows toasts; repeat sound stops when the popup hides.
- Update UI checks passed notes, dismissal, progress, safety guards and handoff with fake releases.

- The packaged executable loaded its synthetic catalog in 3.18 seconds with Python absent from PATH.
- Release archive integrity, checksums and file allowlists are verified separately; no private profile files are included.

## Issues corrected during QA

Closing the popup now rejects any pending duplicate-entry confirmation so its action cannot be submitted after the form is closed. Log hours is disabled while another operation is busy.

## Limits

No live customer time entries were created. Real provider acceptance, permissions and billing effects need intentional tester confirmation. Extended unattended operation and physical mixed-DPI monitor combinations are not established by this pass. System mute and volume still apply to audio; reminders require FreshTray to be running on an available desktop.

The stopwatch is local, includes time while FreshTray is closed, allows entries up to 24 hours and does not split at midnight. Conflicts and uncertain submissions require review rather than blind retries. The popup closes after durable local storage, not after guaranteed server acceptance. See [TIMER.md](TIMER.md).
