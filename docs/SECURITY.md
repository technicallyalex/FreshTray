# Privacy, security and release limits

FreshTray talks directly to FreshBooks over HTTPS. It has no analytics, hosted token service or application telemetry. No customer account, credentials or time history is bundled.

Client secrets, tokens and pending-save recovery records are encrypted with Windows DPAPI CurrentUser in `%LOCALAPPDATA%/FreshTray/vault.dpapi`. Ordinary preferences are stored beside it in `settings.json`. Preview mode has a separate FreshTray-Preview profile. The encrypted vault is tied to your Windows profile; another process running as you can still access your data.

The app requests only the profile, client, project, service and time-entry scopes listed in SETUP.md. Pasted callback URLs are not saved. Network response bodies and credentials are not logged. In-memory forms disappear on quit.

Interrupted saves retain an encrypted pending record. Use Check pending before resubmitting. Updates check the current record before writing, but this is not an atomic provider-side lock. No automatic write retry is performed. Billed status is retained; related invoice records are not edited by this app.

Each user supplies their own developer app credentials. This is not a hosted multi-user OAuth integration. Do not distribute a shared client secret.

## Known limits

- Unsigned portable Windows x64 build; no installer or automatic updates.
- Live FreshBooks write acceptance, billing effects and account-specific permissions require user verification.
- Historical native runtime crashes prompted window-handling changes; short regression tests cannot establish crash-free long-running operation.
- Custom icon controls support keyboard activation/tooltips but have limited screen-reader semantics.
- Physical mixed-DPI multi-monitor testing and notification delivery depend on the user's environment.

Disconnect revokes the refresh token before removing local credentials. If it fails, retry or revoke the integration in FreshBooks. To erase local data, quit first, then remove the FreshTray folder in LOCALAPPDATA. This also removes encrypted recovery records; resolve pending saves first.

For a security concern, do not post secrets, private notes, customer identifiers or callback URLs in public issues. Use GitHub's private vulnerability reporting if enabled, or describe only non-sensitive reproduction steps.
