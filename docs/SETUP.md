# Set up FreshTray

## 1. Open the app

Download the Windows x64 ZIP from Releases and extract it completely. Open **Run FreshTray.cmd**. If nothing opens, look for the green clock under the hidden-icons arrow beside the Windows clock: only one copy can run at a time.

To try the interface without connecting, use **Preview.cmd**. The preview uses fictional sample data and sends no FreshBooks requests.

## 2. Create your FreshBooks developer app

1. Sign in to FreshBooks in your browser.
2. Open the developer area from the [FreshBooks API introduction](https://www.freshbooks.com/api/start) and create an application for your own account.
3. Add this exact Redirect URI:

   `https://localhost:8765/callback`

4. Add these permissions/scopes and save the developer app:

   - `user:profile:read`
   - `user:clients:read`
   - `user:projects:read`
   - `user:billable_items:read`
   - `user:time_entries:read`
   - `user:time_entries:write`

5. Keep its Client ID and Client Secret available. Do not post them in issues or send them to anyone.

## 3. Connect inside FreshTray

1. Open **Settings** and expand **Show connection setup** if necessary.
2. Paste the developer app's **Client ID** and **Client secret** into the matching fields.
3. Leave **Registered redirect URI** as `https://localhost:8765/callback`.
4. Click **Open browser sign-in**, sign in and approve the connection.
5. The browser redirects to localhost and reports that it cannot connect. **This is expected.** FreshTray does not run a local web server. Do not change HTTPS to HTTP or bypass certificate warnings.
6. Copy the **whole address bar**, including the `code` and `state` query values. Paste it into **Return URL** in FreshTray, then click **Finish connection** within five minutes.
7. Clear the clipboard. The return address is sensitive, is masked in the app, and is not saved.
8. Open **Log time**, choose your business, and wait for clients/projects/services to load.

If the attempt expires, start again with Open browser sign-in. If your provider rejects this redirect URI, do not substitute an unrelated third-party URL; review your developer app configuration and the official [OAuth guide](https://www.freshbooks.com/api/authentication).

## 4. Log a day

Select the client, choose a date with the calendar icon, enter `8:00` or `7.5` hours, add a note and click **Log time**. Check the result in FreshBooks. Alternatively select a day in **Monthly hours** and use its built-in form. Future dates are not accepted.

## 5. Make it convenient

In Settings, choose your reminder time and AM/PM, optionally enable weekdays only and startup, then Save settings. Test notification checks whether Windows allows notifications.

Docked mode opens a panel beside the taskbar and hides it when you click elsewhere. Your draft stays in memory until you quit. X hides to tray by default; turn off Close button hides to tray if you prefer X to quit.

## Troubleshooting

- **Already running:** open the tray's hidden-icons menu and click the clock; quit the old copy before running another.
- **No clients / access denied:** check the scopes above and your FreshBooks role. Some roles/plans cannot access the required client list.
- **Connection failed or expired:** reconnect from Settings. Never paste credentials or callback URLs into an issue.
- **Save interrupted:** use Check pending save before trying again. The app does not retry writes automatically, to avoid duplicates.
- **No notification:** check Windows notification permissions and Do Not Disturb. The app must be running and the computer awake.
- **Moving computers:** encrypted credentials belong to the original Windows profile. Reconnect on the new computer rather than copying the vault.
- **Updating:** quit from the tray, extract the new release into a permanent folder, then run it. Settings live separately in your Windows profile. Re-enable startup from the new location if you moved the app.

To uninstall, disable startup, disconnect or revoke access in FreshBooks, quit, and remove the extracted folder. Optional local-data removal is described in SECURITY.md.
