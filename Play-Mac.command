#!/bin/bash
# Hellcat Sandbox - macOS launcher. Double-click this one file (or run it in Terminal).
# First start: downloads the game (about 80 MB) into ~/HellcatSandbox, then starts it.

REPO="Prokopiy8247/Opus55-Dodge-Challenger-3DModel"
GAME_DIR="$HOME/HellcatSandbox"
APP="$GAME_DIR/HellcatSandbox.app"

# a build made from the source next to this file wins
HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
if [ -n "$HERE" ] && [ -d "$HERE/Builds/HellcatSandbox_Mac/HellcatSandbox.app" ]; then
  APP="$HERE/Builds/HellcatSandbox_Mac/HellcatSandbox.app"
fi

if [ ! -d "$APP" ]; then
  echo
  echo " HELLCAT SANDBOX - first start"
  echo " Downloading the game (about 80 MB). Please wait, this happens only once..."
  echo
  mkdir -p "$GAME_DIR"
  TMP="$(mktemp -t hellcat).tar.gz"
  if ! curl -fL --progress-bar "https://github.com/$REPO/releases/latest/download/HellcatSandbox-macOS.tar.gz" -o "$TMP"; then
    echo
    echo " Download failed. Check your internet connection and run this file again."
    read -r -p " Press Enter to close..." _
    exit 1
  fi
  tar -xzf "$TMP" -C "$GAME_DIR" && rm -f "$TMP"
fi

# the game is not signed by Apple: allow it to run (nothing leaves your Mac)
xattr -dr com.apple.quarantine "$APP" 2>/dev/null
chmod -R u+x "$APP/Contents/MacOS" 2>/dev/null
# Apple Silicon only runs code that carries at least an ad-hoc signature
codesign --force --deep -s - "$APP" >/dev/null 2>&1

echo " Starting the game... (Esc inside the game opens the menu)"
open "$APP"
