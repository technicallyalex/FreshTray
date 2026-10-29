# Development

Run commands below from the project root. Source mode requires Windows and Python 3.11+ with Tcl/Tk. No third-party runtime packages are needed.

## Run editable source

```powershell
python src/main.pyw
python src/main.pyw --demo
```

Or use `./scripts/run-source.ps1 --demo`. Normal and demo modes use separate local profiles.
Icons and private fonts live in `src/assets/`; Python modules live in `src/freshtray/`.

## Test

```powershell
./scripts/test.ps1
./scripts/test.ps1 -Ui
python tests/smoke_launch_calendar.py --scaling 2.0
```

Core checks also run with `python -m unittest discover -s tests -v`.
Tests import the `src` tree via `tests/_paths.py`, create temporary offline profiles, and do not make FreshBooks requests.

## Build the Windows app

```powershell
python -m pip install pyinstaller==6.21.0
./scripts/build.ps1
```

Quit the app before replacing its runtime. The maintained specification is `scripts/FreshTray.spec`.
The default output is `app/FreshTray/`; intermediate output goes into `.build/pyinstaller/`.
To build separately while the app runs: `./scripts/build.ps1 -OutputDirectory .build/review`.
The build accepts paths with spaces and can be invoked from another working directory.

## Verify and package

```powershell
./scripts/check-packaged.ps1
python scripts/package-release.py
```

The packaged check launches and closes only its own offline preview, storing its temporary profile in `.build/`.
The release ZIP contains the ready-built app, source, tests, docs, scripts and root launchers. It excludes `.build/`, `archive/`, caches and local profiles.

## Source map

| File under `src/` | Purpose |
| --- | --- |
| `main.pyw` | Entry point, DPI handling and single-instance guard |
| `freshtray/ui.py`, `layout.py` | App controller, navigation, entry form and docked Settings |
| `freshtray/history.py`, `monthly_editor.py`, `history_model.py` | Monthly calendar, inline add/edit draft, totals and safe edit payloads |
| `freshtray/appearance.py`, `fonts.py` | Shared palettes, fonts and theme updates |
| `freshtray/components.py`, `viewport.py`, `scrollbars.py`, `sizing.py` | Layout, scrolling and launch sizing |
| `freshtray/widgets.py` | Date picker and AM/PM reminder control |
| `freshtray/api.py` | OAuth, FreshBooks reads, submissions and reconciliation |
| `freshtray/storage.py` | DPAPI storage and atomic writes |
| `freshtray/windows.py` | Native tray, notifications and startup |
| `freshtray/model.py` | Validation, date conversion and reminder decisions |
| `freshtray/demo.py` | Isolated offline sample backend |

Historical build scripts and snapshots under `archive/development-history/` retain their old paths for reference. Use the maintained tools under `scripts/` for current work.
