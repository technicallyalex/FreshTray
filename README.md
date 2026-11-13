# FreshTray

FreshTray is a portable Windows app for logging time with your FreshBooks account. Record your work, review your hours in a monthly calendar, and get a reminder when it is time to log your day.

**[Download FreshTray 0.2](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2)** · [Setup guide](docs/SETUP.md) · [Usage guide](docs/USAGE.md)

![FreshTray monthly calendar and entry form](docs/images/monthly-hours.png)

## Features

- **Time logging:** choose your business, client, date and hours, add a note, and optionally select a project, service and billable status.
- **Monthly calendar:** browse months, see daily, weekly and monthly hours, and add, edit or delete entries for a selected day.
- **Reminders:** choose a daily reminder time, use a reminder popup or Windows notification, and select a sound and volume. The popup has a **Remind me** button for another reminder later.
- **Offline work:** use previously downloaded lists and months, make changes without internet, and sync when you reconnect. Conflicts and uncertain submissions are kept for review.
- **Personal preferences:** light and dark themes, remembered business/client choices, alphabetical or recently used dropdown sorting, startup, always-on-top and taskbar docking options.

> **Optional testing:** [FreshTray 0.3 RC3](https://github.com/technicallyalex/FreshTray/releases/tag/v0.3.0-rc.3) adds a timer panel and stopwatch popout. It is a **testing prerelease**; use **0.2** for everyday work unless you want to test the timer and [report issues](https://github.com/technicallyalex/FreshTray/issues). [Timer testing guide](docs/TIMER.md).

## Getting started

1. Download the **.exe** from the [FreshTray 0.2 release](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2). The ZIP also includes documentation and license notices.
2. Keep it in a permanent folder and double-click it. **FreshTray is a portable app that doesn't require installation.**
3. Open **Settings > FreshBooks connection** and follow the [setup guide](docs/SETUP.md). You need a FreshBooks account and your own FreshBooks developer application; the guide explains where to create it and which settings to use.
4. In **Log time**, choose your business and client, enter your hours and note, then select **Log time**.

Requires Windows 10/11 x64. The executable is unsigned, so Windows may show a publisher warning.

## Everyday use

Use **Log time** for a new entry and **Monthly hours** to review or change a particular day. Settings apply automatically. Reminder popups work independently of Windows notification banners; FreshTray must be running and the desktop available for them to appear.

Before working offline, connect and open the months you need. FreshTray keeps downloaded account data and pending changes on your PC, then syncs when the connection returns. Review any sync warnings before making the same change again.

Settings are kept in your Windows profile. Credentials, tokens and cached account data are encrypted for your Windows account; they are not embedded in the executable or included in downloads. See [privacy and security](docs/SECURITY.md) for details.

## Updating

Download the version you want, finish syncing pending entries, and quit the old copy before opening the new one. Existing settings and account data are reused. If you move the executable, update **Start with Windows** from its new location. Keep a backup of your data before trying a prerelease.

## Help and development

[Report an issue](https://github.com/technicallyalex/FreshTray/issues) with your version, the steps to reproduce it, and any relevant Windows display settings. Remove account details and credentials from screenshots and reports.

See [development instructions](docs/DEVELOPING.md) to edit or build the app. App code is [MIT licensed](LICENSE); fonts, Qt and other dependencies retain the terms in [third-party notices](docs/THIRD_PARTY_NOTICES.md). FreshTray is an independent community app, not affiliated with or endorsed by FreshBooks. Documentation screenshots use fictional data.

## AI assistance

FreshTray was created with AI assistance, including ChatGPT and OpenAI Codex, for code, UI design, debugging, testing and documentation. AI assistance does not change the project's license or the terms of third-party components.
