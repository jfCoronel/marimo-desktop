"""The release artifacts: desktop entry, Linux tarball, release notes.

These are what a downloader actually touches, and nothing else checks them —
a typo in the .desktop file or a stale filename in the notes only shows up
when someone tries to install.
"""

from __future__ import annotations

import configparser
import importlib.util
import stat
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
LINUX_PACKAGING = ROOT / "packaging" / "linux"
VERSION = "9.9.9"  # deliberately not the real one: catches hard-coded versions


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# -- .desktop entry -------------------------------------------------------


@pytest.fixture(scope="module")
def desktop_entry() -> configparser.SectionProxy:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(LINUX_PACKAGING / "marimo-desktop.desktop", encoding="utf-8")
    return parser["Desktop Entry"]


def test_desktop_entry_has_the_required_keys(desktop_entry: configparser.SectionProxy) -> None:
    assert desktop_entry["Type"] == "Application"
    assert desktop_entry["Name"] == "marimo desktop"
    assert desktop_entry["Icon"] == "marimo-desktop"
    assert desktop_entry["Terminal"] == "false"


def test_desktop_categories_are_registered_ones(
    desktop_entry: configparser.SectionProxy,
) -> None:
    """Invented categories make an entry vanish from some application menus."""
    known = {"Development", "Science", "IDE", "Education", "Utility"}
    categories = [c for c in desktop_entry["Categories"].split(";") if c]
    assert categories
    assert set(categories) <= known


def test_installer_substitutes_the_exec_placeholder(
    desktop_entry: configparser.SectionProxy,
) -> None:
    """Exec must be rewritten to an absolute path: a desktop launcher does not
    necessarily have ~/.local/bin on its PATH."""
    assert desktop_entry["Exec"] == "__EXEC__"
    assert "__EXEC__" in (LINUX_PACKAGING / "install.sh").read_text(encoding="utf-8")


def test_uninstall_removes_what_install_creates() -> None:
    install = (LINUX_PACKAGING / "install.sh").read_text(encoding="utf-8")
    uninstall = (LINUX_PACKAGING / "uninstall.sh").read_text(encoding="utf-8")

    for artifact in ("marimo-desktop.desktop", "marimo-desktop.png", "bin/marimo-desktop"):
        target = artifact.rsplit("/", 1)[-1]
        assert target in install
        assert target in uninstall


# -- Linux tarball --------------------------------------------------------


@pytest.fixture(scope="module")
def tarball(tmp_path_factory: pytest.TempPathFactory) -> tarfile.TarFile:
    package_linux = _load("package_linux")
    out = tmp_path_factory.mktemp("dist")
    fake_binary = out / "marimo-desktop"
    fake_binary.write_bytes(b"#!/bin/sh\necho fake\n")
    fake_binary.chmod(0o755)

    built = package_linux.build(fake_binary, VERSION, out)
    return tarfile.open(built)


def test_tarball_unpacks_into_one_directory(tarball: tarfile.TarFile) -> None:
    """Never explode into the user's cwd."""
    tops = {name.split("/")[0] for name in tarball.getnames()}
    assert tops == {f"marimo-desktop-{VERSION}-linux-x86_64"}


def test_tarball_ships_everything_install_needs(tarball: tarfile.TarFile) -> None:
    names = {Path(n).name for n in tarball.getnames()}
    assert {
        "marimo-desktop",
        "marimo-desktop.desktop",
        "icon.png",
        "install.sh",
        "uninstall.sh",
        "LICENSE",
        "README.txt",
    } <= names


def test_tarball_sets_modes_regardless_of_the_build_machine(
    tarball: tarfile.TarFile,
) -> None:
    """chmod is a no-op on Windows, so the modes are stamped into the archive
    rather than read off the filesystem — otherwise install.sh arrives
    unrunnable whenever the release is built anywhere but Linux."""
    runnable = {"marimo-desktop", "install.sh", "uninstall.sh"}
    for member in tarball.getmembers():
        if member.isdir():
            continue
        executable = bool(member.mode & stat.S_IXUSR)
        assert executable == (Path(member.name).name in runnable), (
            f"{member.name} has mode {member.mode:o}"
        )


# -- release notes --------------------------------------------------------


@pytest.fixture(scope="module")
def notes() -> str:
    return _load("release_notes").TEMPLATE.format(version=VERSION)


def test_notes_name_every_published_artifact(notes: str) -> None:
    for suffix in (
        "macos-arm64.dmg",
        "windows-x64-setup.exe",
        "linux-x86_64.tar.gz",
    ):
        assert f"marimo-desktop-{VERSION}-{suffix}" in notes


def test_notes_explain_how_to_open_an_unsigned_build(notes: str) -> None:
    """Without this the download is simply unusable for most people."""
    assert "com.apple.quarantine" in notes
    assert "Run anyway" in notes  # Windows SmartScreen


def test_notes_describe_the_message_macos_actually_shows(notes: str) -> None:
    """ux leaves an unverifiable signature, so macOS says "damaged" — and gives
    no override button. Telling people to look for "Open Anyway" sends them
    hunting through Settings for something that isn't there."""
    assert "damaged" in notes
    assert "Open Anyway" not in notes


def test_notes_warn_about_the_first_launch_download(notes: str) -> None:
    assert "200 MB" in notes


def test_notes_do_not_promise_an_intel_build(notes: str) -> None:
    """Nothing in the release builds an x86_64 Mac binary — don't imply one."""
    assert "macos-x86_64" not in notes
    assert "Intel Mac" in notes
