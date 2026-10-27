#!/usr/bin/env bash
# Build dist/ai-control-center_<version>_all.deb from this repository.
# Works on Ubuntu 20.04 and newer (needs dpkg-deb, which every Ubuntu has).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$ROOT/app.py")"
# Maintainer shown by apt: "devcibr <your git email>" unless MAINTAINER is set.
EMAIL="$(git -C "$ROOT" config user.email 2>/dev/null || echo "contacto@devcibr.com")"
MAINTAINER="${MAINTAINER:-devcibr <$EMAIL>}"
BUILD="$ROOT/build/pkg"
LIB="$BUILD/usr/lib/ai-control-center"

rm -rf "$ROOT/build"
mkdir -p "$LIB" "$BUILD/DEBIAN" "$BUILD/usr/bin" "$BUILD/usr/share/applications" \
  "$BUILD/usr/share/icons/hicolor/scalable/apps" "$BUILD/usr/share/polkit-1/actions" "$BUILD/usr/share/metainfo" \
  "$BUILD/usr/share/doc/ai-control-center" "$ROOT/dist"

cp "$ROOT/app.py" "$LIB/"
cp -r "$ROOT/aicc" "$ROOT/templates" "$ROOT/static" "$ROOT/helpers" "$LIB/"
find "$LIB" -name '__pycache__' -prune -exec rm -rf {} +
install -m 0755 "$ROOT/packaging/ai-control-center" "$BUILD/usr/bin/ai-control-center"
install -m 0644 "$ROOT/packaging/com.devcibr.AIControlCenter.desktop" "$BUILD/usr/share/applications/"
install -m 0644 "$ROOT/packaging/com.devcibr.AIControlCenter.metainfo.xml" "$BUILD/usr/share/metainfo/"
install -m 0644 "$ROOT/static/icon.svg" "$BUILD/usr/share/icons/hicolor/scalable/apps/ai-control-center.svg"
for size in 128 256 512; do
  install -D -m 0644 "$ROOT/packaging/store/icon-$size.png" "$BUILD/usr/share/icons/hicolor/${size}x${size}/apps/ai-control-center.png"
done
install -m 0644 "$ROOT/packaging/io.github.aicontrolcenter.policy" "$BUILD/usr/share/polkit-1/actions/"
install -m 0644 "$ROOT/README.md" "$BUILD/usr/share/doc/ai-control-center/"
cat > "$BUILD/usr/share/doc/ai-control-center/copyright" <<'COPYRIGHT'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: AI Control Center
Upstream-Contact: devcibr <https://www.devcibr.com>
Source: https://github.com/cesarbarbozarueda/ai-control-center-ubuntu

Files: *
Copyright: 2026 devcibr
License: GPL-3.0+
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 .
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 .
 On Debian and Ubuntu systems, the complete text of the GNU General
 Public License version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPYRIGHT
install -m 0755 "$ROOT/packaging/postinst" "$ROOT/packaging/postrm" "$BUILD/DEBIAN/"

find "$LIB" -type d -exec chmod 0755 {} +
find "$LIB" -type f -exec chmod 0644 {} +
chmod 0755 "$LIB/app.py" "$LIB/helpers/"*

SIZE="$(du -sk "$BUILD/usr" | cut -f1)"
cat > "$BUILD/DEBIAN/control" <<CONTROL
Package: ai-control-center
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-flask, python3-psutil, pkexec | policykit-1, xdg-utils, systemd
Recommends: python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0, docker.io | docker-ce
Installed-Size: $SIZE
Maintainer: $MAINTAINER
Homepage: https://www.devcibr.com
Description: Panel para administrar tus IAs locales / Local AI control panel
 AI Control Center es un panel de escritorio para administrar tus IAs locales
 en Ubuntu: Ollama, Open WebUI, Immich, ComfyUI, LM Studio, Jan, GPT4All,
 LocalAI, Stable Diffusion WebUI, n8n y más, o cualquier otra que agregues.
 Detecta dónde está instalada cada una o te deja indicar la ruta, las inicia,
 detiene y actualiza, avisa cuando hay versiones nuevas, elige cuáles arrancan
 al iniciar sesión, las desinstala por completo y muestra el uso de CPU, RAM y
 GPU. Tema claro u oscuro. Solo escucha en 127.0.0.1.
 Desarrollado por devcibr - https://www.devcibr.com
 .
 AI Control Center is a desktop panel to manage your local AI tools on Ubuntu:
 Ollama, Open WebUI, Immich, ComfyUI, LM Studio, Jan, GPT4All, LocalAI,
 Stable Diffusion WebUI, n8n and more, or any other you add. It finds where each
 one is installed or lets you set the path, starts, stops and updates them,
 notifies you of new versions, chooses which ones start when you log in, fully uninstalls them and shows CPU, RAM and GPU usage. Light or dark
 theme. Only listens on 127.0.0.1.
 Developed by devcibr - https://www.devcibr.com
CONTROL

OUT="$ROOT/dist/ai-control-center_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$BUILD" "$OUT" >/dev/null
echo "Paquete creado: $OUT"
