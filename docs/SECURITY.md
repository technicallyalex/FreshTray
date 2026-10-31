# Privacy, security and release limits

FreshTray talks directly to FreshBooks over HTTPS. It has no analytics, hosted token service or application telemetry. No customer account, credentials or time history is bundled.

Client secrets, tokens and pending-save recovery records are encrypted with Windows DPAPI CurrentUser in `%LOCALAPPDATA%/FreshTray/vault.dpapi`. Downloaded account lists, time-entry snapshots and queued offline changes are encrypted separately in `%LOCALAPPDATA%/FreshTray/offline.dpapi`. Ordinary preferences are stored beside it in `settings.json`. Preview mode has a separate FreshTray-Preview profile. The encrypted vault is tied to your Windows profile; another process running as you can still access your data.

The app requests only the profile, client, project, service and time-entry scopes listed in SETUP.md. Pasted callback URLs are not saved. Network response bodies and credentials are not logged. In-memory forms disappear on quit.

Offline changes persist before the app reports a local save. Interrupted network writes retain an encrypted pending record; ambiguous creates pause for explicit review rather than automatic resubmission. Updates check the current record before writing, but this is not an atomic provider-side lock. Changes that have not been sent sync automatically after connectivity returns. Ambiguous creates are never automatically retried. Conflicting edits/deletions are retained for review. Account identity is verified before synchronization, and disconnect is blocked while local changes remain. Billed status is retained; related invoice records are not edited by this app.

Each user supplies their own developer app credentials. This is not a hosted multi-user OAuth integration. Do not distribute a shared client secret.

## Known limits

- Unsigned portable Windows x64 build; no installer or automatic updates.
- Live FreshBooks write acceptance, billing effects and account-specific permissions require user verification.
- Historical native runtime crashes prompted window-handling changes; short regression tests cannot establish crash-free long-running operation.
- Custom icon controls support keyboard activation/tooltips but have limited screen-reader semantics.
- Physical mixed-DPI multi-monitor testing remains environment-specific. The app-owned reminder window is independent of Windows banner permissions and Do Not Disturb, but needs a running app and available desktop; it cannot wake a sleeping computer or appear above the secure desktop.

Disconnect revokes the refresh token before removing local credentials. If it fails, retry or revoke the integration in FreshBooks. To erase local data, quit first, then remove the FreshTray folder in LOCALAPPDATA. This also removes encrypted recovery records; sync or resolve all queued changes first. Deleting offline.dpapi removes unsynced time entries; do not downgrade while changes are pending.

For a security concern, do not post secrets, private notes, customer identifiers or callback URLs in public issues. Use GitHub's private vulnerability reporting if enabled, or describe only non-sensitive reproduction steps.
