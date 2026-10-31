# Development

FreshTray 0.2 uses PySide6 / Qt Quick (QML). Release publication is a separate manual step after PR approval.

## Run source

Windows 10/11 x64, Python 3.11-3.14. From the project root:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./scripts/run-source.ps1 --demo
```

Quit the previous tray process before running normal mode: `./scripts/run-source.ps1`. Existing account data is reused from `%LOCALAPPDATA%/FreshTray`. Demo mode uses a separate profile and never sends network requests. Its optional launcher lives under `scripts/Preview.cmd`; it is retained for safe UI tests, not normal daily use. `--background` starts hidden.

Use this isolated environment: dependencies and build tools are pinned. Only Qt Essentials is needed, without a browser engine.

## Verify and build

```powershell
./scripts/test.ps1 -Ui
./scripts/build.ps1 -OutputDirectory .build/review-qt
./scripts/check-packaged.ps1 -ExecutablePath .build/review-qt/FreshTray.exe
```

The core suite checks validation, OAuth, rotation, reconciliation, editing and caching. The UI suite also runs 128 layout cases at 100%, 125%, 150% and 200% Qt scale factors, plus independent popup checks with suppressed/failing banner delivery. `tests/smoke_qt.py` checks the actual QML forms, add/edit/conflict handling, billed edits, cached navigation, skeletons/failure recovery, date picker, background reminder and logical screen/theme layouts. Set `QT_SCALE_FACTOR=1.5` before running it to exercise Qt display scaling. Other Tk smoke scripts are retained as legacy references.

The build produces a single portable executable: `app/FreshTray.exe`. Copy it alone to run elsewhere without Python. Bundled Qt libraries, fonts, sounds and notices unpack into a temporary runtime folder while running. Initial startup includes extraction. Settings and encrypted credentials stay in `%LOCALAPPDATA%/FreshTray`; they are not carried inside the executable. Credentials are tied to the Windows account. The root launcher prefers app/FreshTray-0.2.exe, then app/FreshTray.exe. Quit the old tray copy before launching the new build. The packaged test closes only its own offline preview. The build spec excludes an incompatible Poppler ICU sometimes found on developer PATH: Qt uses Windows' native ICU. Do not download replacement DLLs from unrelated sites. No script automatically publishes updates.

## Layout and performance

Qt handles per-monitor DPI with device-independent coordinates. There are no screen-resolution multipliers or manually rasterized widget sets. Layouts adjust available logical width and height; small spaces use tighter spacing and shorter note areas. Desktop panels fit without page scrollbars at tested work areas down to 960 x 520 logical pixels. The monthly calendar and editor share one row at desktop widths. Extremely small screens still have physical limits; roughly 780 x 490 logical pixels are needed for the complete monthly layout. Long notes and dropdowns can scroll internally, and days with many entries use pagination.

Panels stay instantiated. Resize transitions last 180 ms, honor Windows reduced motion, and cover partial layouts. Network synchronization runs on one background worker; a separate serialized worker handles local queue writes and cached reads so background networking cannot block local saves. The GUI receives queued results. A 140 ms delay prevents skeleton flashes for fast/cache hits.

The normal app uses `offline.py`: profile/catalog snapshots and up to 24 unpinned months persist in a separate DPAPI CurrentUser encrypted `offline.dpapi`. Months with pending entries remain pinned. The outbox is capped at 500 operations. Calendar reads overlay local changes on server snapshots; uncached offline months are explicitly incomplete. Credentials remain in `vault.dpapi` with the provider's existing uncertain-write journal.

A network-only HEAD probe to the FreshBooks API precedes token use, so known offline conditions do not consume a one-use refresh token. Queue synchronization verifies identity, preflights update/delete conflicts, and preserves the provider journal before any network write. Interrupted POSTs pause for explicit review; no idempotency key is assumed. Atomic provider journal acknowledgements support crash recovery between provider success and local acknowledgement. Sync merges refreshed snapshots into the latest outbox, preserving concurrent local saves. The visible month and downloaded catalogs refresh at most every five minutes when no writes require attention; offline reconnection checks back off to one minute. No timer submits writes from demo mode.

`tests/test_offline.py` runs the actual FreshBooks adapter against fake HTTP, including lost responses, conflicts, disk failures, restart and concurrency. `tests/smoke_offline_qt.py` exercises the real offline adapter through QML forms in both themes without contacting FreshBooks.

## Source map

- `src/main.pyw`: Qt launcher, fonts and single-instance guard.
- `src/freshtray/qt_app.py`: Qt adapter, drafts, API worker, tray and reminders.
- `src/freshtray/qml/`: window, responsive panels and shared styled controls.
- `api.py`, `offline.py`, `storage.py`: provider logic, persistent offline cache/outbox and encrypted storage. `read_cache.py` remains for the developer sandbox.
- `model.py`, `history_model.py`: shared validation, reminder rules and safe edits.
- `src/main_legacy.pyw` and previous Tk modules: preserved for local rollback.

App code stays MIT. Qt/PySide retains its own license; see THIRD_PARTY_NOTICES.md.

Dropdown history and last selections are encrypted in the vault and scoped by account/business. The sorting preference is stored in settings.json. `tests/smoke_choices_qt.py` verifies restoration using a new controller and vault instance.

## Documentation screenshots

Run `./.venv/Scripts/python.exe scripts/capture-screenshots.py` to regenerate `docs/images/`. The script creates an isolated temporary profile and fictional account/calendar data, never reads a normal user profile, and makes no provider calls. Inspect all five images before committing them.

## Prepare a distribution

Build and verify the EXE first, then run `./.venv/Scripts/python.exe scripts/package-release.py`. This writes the versioned standalone EXE, a ZIP with documentation and licenses, and SHA-256 checksums under ignored `releases/`. It includes no user profile, credential vault or developer environment. Source is distributed through this repository. Packaging does not push, tag, upload or create a GitHub release.

For a native Windows popup pass, set `QT_QPA_PLATFORM=windows` and run `tests/smoke_popup_qt.py` in the project environment. It tests test/scheduled/follow-up popups with a notification adapter that silently suppresses or rejects banners. It does not change the user's Windows notification settings.

See [third-party notices and provenance limits](THIRD_PARTY_NOTICES.md) before preparing a distribution. Retain the application license, font license, and exact runtime component notices.
