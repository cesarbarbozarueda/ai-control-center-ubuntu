#!/usr/bin/env bash
set -euo pipefail
systemctl --user disable --now ai-control-center.service 2>/dev/null || true
systemctl --user disable --now ai-comfyui.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/ai-control-center.service" "$HOME/.config/systemd/user/ai-comfyui.service"
systemctl --user daemon-reload
rm -f "$HOME/.config/autostart/ai-control-center.desktop"
echo "Servicios del panel deshabilitados. Los archivos del proyecto, modelos, contenedores y datos no se borraron."
echo "Si también querés quitar el código, borrá manualmente ~/.local/share/ai-control-center."
echo "Para quitar los permisos de Ollama: sudo rm -f /etc/sudoers.d/ai-control-center"
