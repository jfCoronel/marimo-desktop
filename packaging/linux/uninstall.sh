#!/bin/sh
# Removes what install.sh put in place. The downloaded interpreter cache in
# ~/.cache/ux/ is left alone unless you pass --purge.
set -eu

bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"

rm -f "$bin_dir/marimo-desktop"
rm -f "$data_dir/applications/marimo-desktop.desktop"
rm -f "$data_dir/icons/hicolor/512x512/apps/marimo-desktop.png"
echo "Removed marimo desktop."

if [ "${1:-}" = "--purge" ]; then
    rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/ux"
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/marimo-desktop"
    echo "Also removed the interpreter cache and your marimo-desktop settings."
    echo "Your notebooks in ~/'marimo notebooks' were NOT touched."
fi
