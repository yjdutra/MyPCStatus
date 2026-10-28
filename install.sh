#!/usr/bin/env bash
# Registra o MyPCStatus no menu do Zorin. Com --autostart, tambem sobe no login.
set -e
HERE="$(dirname "$(readlink -f "$0")")"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"

# reescreve os caminhos caso a pasta do projeto tenha sido movida
sed -e "s|^Exec=.*|Exec=$HERE/run.sh|" \
    -e "s|^Icon=.*|Icon=$HERE/assets/icon.png|" \
    "$HERE/mypcstatus.desktop" > "$APPS/mypcstatus.desktop"
chmod +x "$APPS/mypcstatus.desktop"
update-desktop-database "$APPS" 2>/dev/null || true
echo "Instalado em $APPS/mypcstatus.desktop"

if [ "$1" = "--autostart" ]; then
    mkdir -p "$HOME/.config/autostart"
    cp "$APPS/mypcstatus.desktop" "$HOME/.config/autostart/mypcstatus.desktop"
    echo "Autostart ligado: $HOME/.config/autostart/mypcstatus.desktop"
fi
