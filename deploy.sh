#!/usr/bin/env bash
set -Eeuo pipefail

# AI Control Center: copiar archivos del repositorio a la instalación activa,
# reiniciar el servicio y comprobar las métricas expuestas por la API.

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/share/ai-control-center"
SERVICE_NAME="ai-control-center"
API_URL="http://127.0.0.1:8765/api/status"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for cmd in cp curl python3 systemctl; do
  command -v "$cmd" >/dev/null 2>&1 || die "No se encontró el comando requerido: $cmd"
done

[[ -f "$REPO_DIR/app.py" ]] || die "No existe $REPO_DIR/app.py"
[[ -f "$REPO_DIR/README.md" ]] || die "No existe $REPO_DIR/README.md"
[[ -f "$REPO_DIR/static/app.js" ]] || die "No existe $REPO_DIR/static/app.js"
[[ -f "$REPO_DIR/static/style.css" ]] || die "No existe $REPO_DIR/static/style.css"
[[ -d "$INSTALL_DIR" ]] || die "No existe la instalación activa: $INSTALL_DIR"

mkdir -p "$INSTALL_DIR/static"

printf 'Repositorio: %s\n' "$REPO_DIR"
printf 'Instalación: %s\n' "$INSTALL_DIR"
printf '\nCopiando archivos...\n'

cp "$REPO_DIR/app.py" "$INSTALL_DIR/app.py"
cp "$REPO_DIR/README.md" "$INSTALL_DIR/README.md"
cp "$REPO_DIR/static/app.js" "$INSTALL_DIR/static/app.js"
cp "$REPO_DIR/static/style.css" "$INSTALL_DIR/static/style.css"

printf '\nReiniciando %s...\n' "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"
sleep 2

if ! systemctl --user is-active --quiet "$SERVICE_NAME"; then
  systemctl --user status "$SERVICE_NAME" --no-pager || true
  die "El servicio $SERVICE_NAME no quedó activo. Revisá: journalctl --user -u $SERVICE_NAME -n 60 --no-pager"
fi

printf '\nConsultando API: %s\n' "$API_URL"
response="$(curl --fail --silent --show-error --max-time 10 "$API_URL")" ||
  die "No se pudo consultar la API. Revisá el servicio y la URL $API_URL"

printf '%s' "$response" | python3 -c '
import json
import sys

try:
    data = json.load(sys.stdin)
except Exception as exc:
    print(f"ERROR: la API no devolvió JSON válido: {exc}", file=sys.stderr)
    raise SystemExit(1)

services = data.get("services")
if not isinstance(services, list):
    print("ERROR: la respuesta JSON no contiene una lista services.", file=sys.stderr)
    raise SystemExit(1)

for service in services:
    name = service.get("name", service.get("id", "Servicio desconocido"))
    metrics = service.get("metrics", "SIN MÉTRICAS")
    print(f"{name} => {json.dumps(metrics, ensure_ascii=False)}")
'

printf '\nDespliegue completado. Si el navegador no refleja cambios, recargá con Ctrl+Shift+R.\n'
