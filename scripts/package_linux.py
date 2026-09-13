#!/usr/bin/env python3
"""Assemble the Linux release tarball around the binary ux produced.

ux only emits a bare executable on Linux (`--format app` is macOS-only), so
the desktop integration — icon, .desktop entry, per-user installer — is added
here. Usage:

    python scripts/package_linux.py dist/marimo-desktop 0.3.0
"""

from __future__ import annotations

import argparse
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "linux"

README = """marimo desktop {version}
=========================

Self-contained marimo notebooks: this ships its own Python, so there is
nothing to pip install.

Install (per user, no root):

    ./install.sh

That puts the binary in ~/.local/bin and adds an entry to your application
menu. Then look for "marimo desktop", or run `marimo-desktop`.

Prefer not to install? Just run ./marimo-desktop from this folder.

First launch downloads a Python interpreter and marimo (about 200 MB) into
~/.cache/ux/ and can take a few minutes. Later launches are instant.

To remove it again:

    ./uninstall.sh            # or --purge to drop the cache and settings too

Your notebooks live in ~/"marimo notebooks" and are never touched by either
script.

{url}
"""

URL = "https://github.com/jfCoronel/marimo-desktop"


def build(binary: Path, version: str, out_dir: Path) -> Path:
    stage_name = f"marimo-desktop-{version}-linux-x86_64"
    stage = out_dir / stage_name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    shutil.copy2(binary, stage / "marimo-desktop")
    (stage / "marimo-desktop").chmod(0o755)
    shutil.copy2(ROOT / "assets" / "icon.png", stage / "icon.png")
    shutil.copy2(PACKAGING / "marimo-desktop.desktop", stage / "marimo-desktop.desktop")
    for script in ("install.sh", "uninstall.sh"):
        shutil.copy2(PACKAGING / script, stage / script)
        (stage / script).chmod(0o755)
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
    (stage / "README.txt").write_text(README.format(version=version, url=URL), encoding="utf-8")

    tarball = out_dir / f"{stage_name}.tar.gz"
    tarball.unlink(missing_ok=True)
    # Keep the top-level directory so it doesn't explode into the user's cwd.
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(stage, arcname=stage_name)
    shutil.rmtree(stage)
    return tarball


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="The executable ux built")
    parser.add_argument("version", help="Release version, e.g. 0.3.0")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    if not args.binary.is_file():
        print(f"not found: {args.binary}")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    tarball = build(args.binary, args.version, args.out)
    print(f"{tarball}  ({tarball.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
