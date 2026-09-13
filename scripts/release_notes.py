#!/usr/bin/env python3
"""Print the GitHub release notes for a given version.

Kept as code rather than pasted into the workflow so the install instructions
— the part users actually depend on — can be reviewed and tested.

    python scripts/release_notes.py 0.3.0
"""

from __future__ import annotations

import sys

TEMPLATE = """\
Self-contained marimo notebooks: each download ships its own Python
interpreter, so there is nothing to `pip install` and no venv to manage.

| Platform | Download |
|---|---|
| macOS (Apple Silicon) | `marimo-desktop-{version}-macos-arm64.dmg` |
| Windows 10/11 (64-bit) | `marimo-desktop-{version}-windows-x64-setup.exe` |
| Linux (x86_64) | `marimo-desktop-{version}-linux-x86_64.tar.gz` |

On an **Intel Mac** there is no download yet — the build tool produces an
Apple Silicon binary even when asked for x86_64, so shipping one would mean
shipping something that cannot run. Until that is sorted out, install from
source: `uv tool install marimo` and run `uvx marimo edit`.

**First launch downloads a Python interpreter and marimo (~200 MB) and can
take a few minutes.** It happens once; later launches are instant. The
download goes to `~/Library/Caches/ux/` (macOS), `%LOCALAPPDATA%\\ux\\`
(Windows) or `~/.cache/ux/` (Linux).

## These builds are not signed

This is a hobby project without an Apple Developer account ($99/year) or a
Windows code-signing certificate, so both systems will refuse the download
until you tell them otherwise. Only run software from a source you trust —
this one included.

### macOS

macOS will say **"marimo-desktop is damaged and can't be opened"**. It is not
damaged: the packaging tool leaves the app with a signature macOS considers
invalid, and for that particular verdict there is no override anywhere in
System Settings. Don't go looking in Privacy & Security — nothing about
marimo-desktop appears there.

Clearing the download flag fixes it. After dragging the app to Applications,
run this once in Terminal:

```sh
xattr -dr com.apple.quarantine /Applications/marimo-desktop.app
```

Then open it normally. You only ever do this once, and you can check what the
command does first: it removes the "downloaded from the internet" attribute
that makes macOS refuse the app.

Sorry for the Terminal detour — a proper fix needs either a paid Apple
Developer account or a different packaging tool, and both are on the list.

### Windows

Run the installer. SmartScreen shows *"Windows protected your PC"* — click
**More info**, then **Run anyway**. It installs per user, so there is no
administrator prompt.

### Linux

```sh
tar xzf marimo-desktop-{version}-linux-x86_64.tar.gz
cd marimo-desktop-{version}-linux-x86_64
./install.sh          # per user, into ~/.local — no root needed
```

Adds "marimo desktop" to your application menu. `./uninstall.sh` removes it;
or skip installing and just run `./marimo-desktop`.

## What you get

A small control window: pick a notebooks folder, start the marimo server,
and open it in your own browser (the link is clickable, or copy it and paste
it wherever you like). Closing the window stops the server. Your notebooks
live in `~/marimo notebooks`, seeded with a sample on first run.

Every build in this release was launched by CI on its own platform and
checked to serve marimo before being published.
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    print(TEMPLATE.format(version=argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
