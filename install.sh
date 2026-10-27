#!/usr/bin/env bash
# Build the .deb from this repository and install it (asks for your sudo password).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$ROOT/app.py")"

# Old versions (v1) ran the panel as a systemd user service; stop it so the port is free.
if [[ -f "$HOME/.config/systemd/user/ai-control-center.service" ]]; then
  systemctl --user disable --now ai-control-center.service 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/ai-control-center.service"
  systemctl --user daemon-reload || true
  echo "Se quitó el servicio de la versión anterior. La copia vieja en ~/.local/share/ai-control-center ya no se usa; podés borrarla."
fi

bash "$ROOT/packaging/build-deb.sh"
sudo apt-get install -y "$ROOT/dist/ai-control-center_${VERSION}_all.deb"
pkill -f "/usr/lib/ai-control-center/app.py --server" 2>/dev/null || true
ai-control-center
echo "Listo. También podés abrirlo desde el menú de aplicaciones: AI Control Center."
