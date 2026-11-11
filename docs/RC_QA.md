# 0.3 RC2 verification

This release candidate is for testing and issue reports. [0.2 remains the recommended stable release](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2).

## Scope and results

- 141 automated tests passed, covering core behavior, encrypted offline queue, updates, reminder audio, timer recovery and screen bounds.
- Native Windows timer checks passed pause/resume, restart recovery, exact reviewed duration, four faces, independent idle popout, compact mode, opacity, screen containment and hover hints.
- 72 layout cases passed at 100%/150% scaling across light/dark themes and normal/compact work areas.
- Synthetic offline UI checks passed add/edit/delete, timer saves, reconnection and conflict review. An online save reached the fake provider with the periodic sync timer stopped; successful save/sync produced no notice. Offline saves showed a retained-change notice without repeated retry spam.
- Reminder checks passed scheduled, test and follow-up delivery despite suppressed/failed system toasts. Repeating playback is opt-in, stops when the popup hides, and previews remain one-shot.
- Update UI checks passed notes, dismissal, progress, safety guards and handoff with fake releases.

- The packaged executable opened and loaded its synthetic catalog in 3.05 seconds with Python absent from PATH.
- Release ZIP integrity, SHA-256 checksums and the executable contents passed the file allowlist check; no private profile files were found.

## Issue corrected during QA

The repeat-sound control could crowd the volume slider into the appearance panel. Sound controls now share one row, both reminder cards respect their content height, and compact padding preserves the footer. Layout QA now checks sound-control containment and overlap with the next panel.

## Limits

No live customer time entries were created. Provider acceptance, account permissions and billing effects need intentional tester confirmation. Extended unattended operation and physical mixed-DPI monitor combinations are not established by this pass. System mute and device volume still apply to audio. Popups require FreshTray to be running on an available desktop.

The stopwatch runs locally and includes time while FreshTray is closed. Entries are limited to 24 hours and are not split at midnight. Conflicts and uncertain submissions require review rather than blind retries. See [TIMER.md](TIMER.md).
