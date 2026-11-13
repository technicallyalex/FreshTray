# Testing the 0.3 timer

**0.3 RC3 is intended for testing and issue reporting. Use [0.2](https://github.com/technicallyalex/FreshTray/releases/tag/v0.2) for everyday time logging.** The RC uses the same Windows-profile data as the stable app. Back it up before switching builds, finish syncing entries, and run only one copy at a time.

## Track time

Open **Timer**, choose the business and client, then **Start timer**. Pause and resume as needed. **Stop & review** retains the duration and lets you adjust it as HH:MM:SS. **Log time** queues the reviewed entry for FreshBooks. Starting or pausing a timer does not submit an entry.

The stopwatch runs locally. It does **not** synchronize a running timer with FreshBooks' website. A running timer continues across quitting and restarting FreshTray, including time while the app is closed. Pause it before quitting if you do not want that time counted.

Timer state and drafts are saved in the Windows-encrypted vault. Entries preserve the actual start timestamp, have a maximum duration of 24 hours, and are not automatically split at midnight. Review long sessions before logging.

## Popout and faces

Open the popout even when no timer is active. Drag its handle to move it; the whole window stays inside the monitor's usable area. The pin keeps it above other windows. Condense it to the face alone and click the face to reveal controls again. Closing the popout leaves the timer unchanged.

Select a face in the Timer panel: **Digital stopwatch**, **Station flip**, **Classic stopwatch**, or **Station stopwatch**. Every face shows the same elapsed hours, minutes and seconds. Faces stop moving when the timer is paused, stopped or inactive. Analog faces have a seconds hand and minute/hour subdials. The opacity slider changes the popout's visibility; hovering restores full visibility for interaction.

## What to test

- Start, pause, resume, review and log a short session; check the resulting client, duration, note and start time in FreshBooks.
- Restart with a running or paused timer and check the restored duration.
- Save offline, reconnect and check that the entry appears once. If sync needs review, resolve it before manually adding another copy.
- Try every face, condensed mode, opacity, pinning and dragging near each edge of your displays.
- Switch panels and themes, including at different Windows scaling settings.

[Report issues](https://github.com/technicallyalex/FreshTray/issues) with **0.3.0-rc.1**, reproduction steps and display settings. Remove credentials, private client names and work notes from attachments.
