#!/usr/bin/env bash
# Remove the AI Control Center app. Your AI tools, models and data are not touched.
set -euo pipefail
pkill -f "/usr/lib/ai-control-center/app.py --server" 2>/dev/null || true
rm -f "$HOME/.config/autostart/ai-control-center.desktop"
sudo apt-get remove -y ai-control-center
echo "AI Control Center desinstalado."
echo "Tu configuración sigue en ~/.config/ai-control-center (borrala si no la querés)."
echo "Los servicios de usuario creados para tus IAs (~/.config/systemd/user/ai-*.service) se mantienen."
