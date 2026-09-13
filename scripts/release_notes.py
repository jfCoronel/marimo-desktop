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
| macOS 11+ (Intel and Apple Silicon) | `marimo-desktop-{version}-macos-universal.dmg` |
| Windows 10/11 (64-bit) | `marimo-desktop-{version}-windows-x64-setup.exe` |
| Linux (x86_64) | `marimo-desktop-{version}-linux-x86_64.tar.gz` |

The macOS build carries Python and marimo inside it, so it is larger to
download but starts straight away. **On Windows and Linux the first launch
downloads a Python interpreter and marimo (~200 MB) and can take a few
minutes** — once only; later launches are instant, and the download goes to
`%LOCALAPPDATA%\\ux\\` or `~/.cache/ux/`.

## These builds are not signed

This is a hobby project without an Apple Developer account ($99/year) or a
Windows code-signing certificate, so both systems will refuse the download
until you tell them otherwise. Only run software from a source you trust —
this one included.

### macOS

The app is signed, but not *notarised* — that needs a paid Apple Developer
account. So the first launch is refused:

1. Open the `.dmg` and drag **marimo desktop** to Applications.
2. Launch it. macOS says it cannot verify the developer. Click **Done**.
3. Open **System Settings → Privacy & Security**, scroll to the bottom, and
   click **Open Anyway** next to the message about marimo desktop.

From then on it opens normally. If you prefer one line in Terminal instead:

```sh
xattr -dr com.apple.quarantine "/Applications/marimo desktop.app"
```

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
