#!/usr/bin/env bash
set -Eeuo pipefail

# AI Control Center: reconstruir el .deb, reinstalarlo, reiniciar el panel
# y comprobar las métricas expuestas por la API.

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
API_URL="http://127.0.0.1:8765/api/status"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$REPO_DIR/app.py")"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for cmd in curl python3 dpkg-deb; do
  command -v "$cmd" >/dev/null 2>&1 || die "No se encontró el comando requerido: $cmd"
done

printf 'Construyendo paquete %s...\n' "$VERSION"
bash "$REPO_DIR/packaging/build-deb.sh"
sudo apt-get install -y --reinstall "$REPO_DIR/dist/ai-control-center_${VERSION}_all.deb"

printf '\nReiniciando el panel...\n'
pkill -f "/usr/lib/ai-control-center/app.py --server" 2>/dev/null || true
sleep 1
ai-control-center --background || die "El panel no arrancó. Revisá ~/.cache/ai-control-center/server.log"

printf '\nConsultando API: %s\n' "$API_URL"
response="$(curl --fail --silent --show-error --max-time 15 "$API_URL")" ||
  die "No se pudo consultar la API. Revisá ~/.cache/ai-control-center/server.log"

printf '%s' "$response" | python3 -c '
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception as exc:
    print(f"ERROR: la API no devolvió JSON válido: {exc}", file=sys.stderr)
    raise SystemExit(1)

for service in data.get("services", []):
    name = service.get("name", service.get("id", "Servicio desconocido"))
    if not service.get("installed"):
        print(f"{name} => no detectado")
        continue
    state, where = service.get("state"), service.get("location")
    metrics = json.dumps(service.get("metrics"), ensure_ascii=False)
    print(f"{name} => {state} · {where} · {metrics}")
'

printf '\nDespliegue completado. Si el navegador no refleja cambios, recargá con Ctrl+Shift+R.\n'
