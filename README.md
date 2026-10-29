# FreshTray

A Windows system-tray app for logging time to FreshBooks. Add time, review a monthly calendar, edit entries, and set an end-of-day reminder. Supports light/dark themes, a taskbar-style docked panel, and encrypted local credentials.

Independent community app; not affiliated with or endorsed by FreshBooks.

## Download and run

1. Open [Releases](https://github.com/technicallyalex/FreshTray/releases/latest).
2. Download **FreshTray-0.1-Windows-x64.zip** under Assets. You do not need GitHub's Source code downloads.
3. Right-click the ZIP and choose **Extract All**. Keep the extracted folder somewhere permanent.
4. Open the folder and double-click **Run FreshTray.cmd**. Python is not required. Do not move FreshTray.exe away from its `_internal` folder.
5. For a preview without an account, double-click **Preview.cmd**.

Requires Windows 10/11 x64. This portable release is unsigned; Windows may show a publisher warning. Only run a download you trust. Do not disable Windows security protections.

## Connect FreshBooks

You need a FreshBooks account and your **own FreshBooks developer application**. The download contains no shared API credentials. Setup takes a few steps; follow the [step-by-step setup guide](docs/SETUP.md).

The browser will show a localhost connection error during sign-in. This is expected: copy its complete address into the app to finish connecting. The guide explains exactly where.

## Daily use

- **Log time:** choose a business/client, hours, date and note; optionally choose project/service and Billable.
- **Monthly hours:** select a day to add time directly. Select a row and choose Edit to update it. Use Refresh to see changes made outside the app; tab switching reuses loaded data.
- **Settings:** set the reminder time, startup, theme, Always on top, Docked mode, and whether X hides to tray or quits. Click Save settings.
- Click the tray clock to reopen. To fully exit, right-click it and choose Quit FreshTray.

Credentials and tokens are encrypted for your Windows account. See [privacy/security and limitations](docs/SECURITY.md).

## Source and development

See [development instructions](docs/DEVELOPING.md). Source is in `src/`; tests in `tests/`; build tools in `scripts/`. Release binaries are attached to Releases rather than committed to Git.

MIT licensed. Third-party fonts retain their own [license](src/assets/fonts/OFL-IBM-Plex.txt).
