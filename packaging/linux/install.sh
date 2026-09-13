#!/bin/sh
# Per-user install: no root, no package manager. Everything lands under
# ~/.local, which is where the XDG spec says user software goes.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icon_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"

mkdir -p "$bin_dir" "$apps_dir" "$icon_dir"

install -m 755 "$here/marimo-desktop" "$bin_dir/marimo-desktop"
install -m 644 "$here/icon.png" "$icon_dir/marimo-desktop.png"
sed "s|__EXEC__|$bin_dir/marimo-desktop|" "$here/marimo-desktop.desktop" \
    > "$apps_dir/marimo-desktop.desktop"
chmod 644 "$apps_dir/marimo-desktop.desktop"

# Best effort: some desktops need a nudge to notice the new entry.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" \
        >/dev/null 2>&1 || true
fi

echo "Installed:"
echo "  $bin_dir/marimo-desktop"
echo "  $apps_dir/marimo-desktop.desktop"
echo
echo "Look for 'marimo desktop' in your application menu, or run: marimo-desktop"
case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) echo
       echo "Note: $bin_dir is not on your PATH; the menu entry works regardless." ;;
esac
echo
echo "First launch downloads a Python interpreter and marimo (~200 MB) into"
echo "~/.cache/ux/. It is only done once; later launches are instant."
