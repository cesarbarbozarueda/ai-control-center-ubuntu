#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/ai-control-center"
UNITDIR="$HOME/.config/systemd/user"
mkdir -p "$DEST" "$UNITDIR" "$HOME/.local/bin"
cp -r "$ROOT/app.py" "$ROOT/requirements.txt" "$ROOT/templates" "$ROOT/static" "$DEST/"
python3 -m venv "$DEST/.venv"
"$DEST/.venv/bin/pip" install --upgrade pip
"$DEST/.venv/bin/pip" install -r "$DEST/requirements.txt"
sed "s|%h/.local/share/ai-control-center|$DEST|g" "$ROOT/systemd/ai-control-center.service" > "$UNITDIR/ai-control-center.service"
# Create the ComfyUI user service only if its expected entry point exists.
COMFY="$HOME/Documents/IA/IA_VIDEOS/ComfyUI"
if [[ -f "$COMFY/main.py" && -x "$COMFY/venv/bin/python" ]]; then
  sed "s|%h/Documents/IA/IA_VIDEOS/ComfyUI|$COMFY|g" "$ROOT/systemd/ai-comfyui.service" > "$UNITDIR/ai-comfyui.service"
  echo "ComfyUI service installed."
else
  echo "ComfyUI service not installed: expected main.py and venv/bin/python in $COMFY"
  echo "Edit ~/.config/systemd/user/ai-comfyui.service if your installation uses another path or environment."
fi

# Grant only exact Ollama systemd actions; no general shell access.
SUDOERS="/etc/sudoers.d/ai-control-center"
TMP="$(mktemp)"
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl start ollama.service, /usr/bin/systemctl stop ollama.service, /usr/bin/systemctl restart ollama.service\n' "$USER" > "$TMP"
chmod 0440 "$TMP"
if command -v visudo >/dev/null 2>&1; then
  if sudo visudo -cf "$TMP" >/dev/null; then
    sudo install -o root -g root -m 0440 "$TMP" "$SUDOERS"
    echo "Permisos limitados para administrar Ollama configurados."
  else
    echo "No se pudo validar la regla sudoers; no se instaló." >&2
  fi
fi
rm -f "$TMP"

systemctl --user daemon-reload
systemctl --user enable --now ai-control-center.service

# Start the dashboard server at login and open it in the default browser.
AUTOSTART="$HOME/.config/autostart"
mkdir -p "$AUTOSTART"
cat > "$AUTOSTART/ai-control-center.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=AI Control Center
Comment=Abrir el panel local de control de IA
Exec=sh -c 'sleep 3; xdg-open http://127.0.0.1:8765'
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP

echo
echo "Instalación terminada."
echo "Abrí: http://127.0.0.1:8765"
echo "Para ver logs: journalctl --user -u ai-control-center -f"
echo "Para desinstalar, consultá README.md; tus modelos y datos no se tocan."
