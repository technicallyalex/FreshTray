# Third-party notices and licensing

Reviewed against main at `b7f2e44f76bec9af32062b2f19e3c501697c3b8f` on 2026-10-31.

## Application code

The application code is [MIT licensed](../LICENSE), with the existing notice "Copyright (c) 2026 FreshTray contributors". Copies or substantial portions must retain that copyright and permission notice, including the license's warranty/liability terms. Third-party components retain their own licenses.

## Components and assets

| Component | Use and attribution | License / notice |
| --- | --- | --- |
| IBM Plex Sans Regular, Medium, SemiBold and Bold | Bundled in `src/assets/fonts/` and the portable runtime's `assets/fonts/`. Copyright 2017 IBM Corp.; reserved font name "Plex". | [SIL Open Font License 1.1](../src/assets/fonts/OFL-IBM-Plex.txt). Retain the font copyright/license; respect the reserved-name and font redistribution conditions, including for modified fonts. These files are not MIT licensed. |
| Python and its standard runtime | Source mode uses Python with Tcl/Tk. The inspected v0.1 portable release includes `python314.dll`. | [Python distribution license and incorporated notices](licenses/Python.txt); see also [Python's license documentation](https://docs.python.org/3/license.html). Incorporated components have their own terms. |
| Tcl/Tk | Tkinter UI and bundled `tcl86t.dll` / `tk86t.dll`. | Tcl and Tk notices appear in Python.txt; the inspected release also includes `_internal/_tk_data/license.terms`. Retain these notices when distributing the runtime. |
| Other native runtime libraries | The v0.1 ZIP contains OpenSSL (`libssl-3.dll`, `libcrypto-3.dll`), libffi, zlib and Microsoft runtime files. | Python.txt includes incorporated notices and Windows redistribution conditions. Check the exact supplied versions and their complete notice requirements; the application MIT license does not replace them. A complete version-to-notice mapping, including zlib, is not established here. |
| PyInstaller | Build tool; the portable app embeds its bootloader and related runtime files. DEVELOPMENT.md specifies 6.21.0 for future builds. | [Bundled COPYING text](licenses/PyInstaller-COPYING.txt) describes GPL-2.0-or-later with the bootloader exception, Apache-2.0 runtime hooks and other file-specific terms. The exception permits combined executables without applying GPL to application code merely because of the bootloader. Dependency terms still apply. See [upstream explanation](https://pyinstaller.org/en/stable/license.html). |
| Clock icon | `src/assets/freshtray.ico`; `scripts/make-icon.py` provides a geometric drawing implementation without external image dependencies. | The script documents how the icon can be produced. No separate icon license or imported artwork attribution is recorded. This does not prove an exhaustive design provenance. |
| FreshBooks | External API/service and trademark, not a bundled library. | Independent community application, not affiliated with or endorsed by FreshBooks. No FreshBooks logo/font files appear in the tracked asset inventory. The MIT license grants no FreshBooks account, API access, service or trademark rights. |

Source imports use the standard library and local project modules; no third-party Python runtime package is declared. That does not mean the portable executable is free of third-party runtime components. Build tools, Windows APIs, service access and dependencies retain their own terms.

## Release verification and limits

The v0.1 portable ZIP was inspected without running it, and its SHA-256 matched the published checksum. It contains the root MIT license, this notice's prior version, Python.txt, PyInstaller-COPYING.txt, the font OFL text and Tk's license. Those root license/documentation texts match the reviewed repository revision after line-ending normalization. The portable ZIP contains the app, documentation and launchers; it does not contain the repository's src/, tests/ or scripts/ trees. Source is available separately in the repository.

This inventory does not establish the precise versions/provenance of every bundled native library or a reproducible correspondence between source and executable. Verify the exact runtime's notices, including zlib and Microsoft redistribution requirements, and retain a versioned component inventory when preparing releases. Preserve the existing license texts and include updated notices with the next package; editing repository documentation does not modify already-published ZIPs.

For security, accessibility, FreshBooks write behavior and environment-specific limits, see [SECURITY.md](SECURITY.md). AI assistance is described in the [README](../README.md#ai-disclosure); it neither relicenses dependencies nor establishes copyright ownership.
