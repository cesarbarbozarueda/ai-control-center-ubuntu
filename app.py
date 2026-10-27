#!/usr/bin/env python3
"""AI Control Center - local-only dashboard for Ubuntu.

  ai-control-center               start the panel in the background (if needed) and open its window
  ai-control-center --browser     same, but open it in the web browser instead of a window
  ai-control-center --background  start the panel without opening anything
  ai-control-center --server      run the web server in the foreground
"""
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from aicc import config, detect, metrics, services, uninstall, update
from aicc.catalog import CATALOG, ORDER, register_custom
from aicc.util import HOME, port_open, run

VERSION = "2.0.0"
HOST = "127.0.0.1"
PORT = int(os.environ.get("AICC_PORT", "8765"))
BASE_URL = "http://{}:{}".format(HOST, PORT)
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
APP_FILE = Path(__file__).resolve()
WINDOW_FILE = APP_FILE.parent / "aicc" / "window.py"
DEVELOPER = {"name": "devcibr", "url": "https://www.devcibr.com"}
# Donations: the button appears once static/donate-binance.png exists.
DONATE = {"qr": "donate-binance.png", "binance_id": ""}
AUTOSTART_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or (HOME / ".config")) / "autostart" / "ai-control-center.desktop"
LOG_FILE = Path(os.environ.get("XDG_CACHE_HOME") or (HOME / ".cache")) / "ai-control-center" / "server.log"

app = Flask(__name__)
# Random per-run token: pages from other sites cannot call the API (CSRF).
TOKEN = secrets.token_urlsafe(32)
ALLOWED_HOSTS = {"127.0.0.1:{}".format(PORT), "localhost:{}".format(PORT)}
CANDIDATES = {}   # service id -> folders found by the last detection
DETECT_NOTES = []
POOL = ThreadPoolExecutor(max_workers=6)


# ---------- detection ----------

def run_detection(force=False):
    """Detect services that are missing from the config (all of them if force)."""
    global DETECT_NOTES
    cfg = config.load()
    register_custom(cfg["custom"])
    known = cfg["services"]
    todo = [sid for sid in ORDER if not CATALOG[sid].get("custom") and (force or sid not in known)]
    if not todo:
        return cfg
    found = detect.detect_all()
    notes = []
    for sid in todo:
        CANDIDATES[sid] = found[sid]["candidates"]
        notes += found[sid]["notes"]
        current = known.get(sid)
        # Keep paths chosen by hand unless they no longer exist.
        if current and current.get("source") == "manual" and services.status(sid, current, False)["state"] != "missing":
            continue
        known[sid] = found[sid]["location"]
    DETECT_NOTES = sorted(set(notes))
    cfg["services"] = known
    config.save(cfg)
    return cfg


def _location(service_id):
    if service_id not in CATALOG:
        abort(404)
    return config.load()["services"].get(service_id)


# ---------- panel autostart (XDG autostart entry) ----------

def launcher_command():
    from shutil import which
    if which("ai-control-center"):
        return "ai-control-center --autostart"
    return '"{}" "{}" --autostart'.format(sys.executable, APP_FILE)


def set_panel_autostart(enabled):
    if enabled:
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(
            "[Desktop Entry]\nType=Application\nName=AI Control Center\n"
            "Comment=Abrir el panel local de control de IA\n"
            "Exec={}\nIcon=ai-control-center\nTerminal=false\n"
            "X-GNOME-Autostart-enabled=true\n".format(launcher_command()), encoding="utf-8")
    elif AUTOSTART_FILE.exists():
        AUTOSTART_FILE.unlink()


# ---------- request guards ----------

@app.before_request
def guard():
    # Block DNS rebinding: only answer requests addressed to loopback.
    if request.host not in ALLOWED_HOSTS:
        abort(403)
    if request.method != "GET" and request.headers.get("X-AICC-Token") != TOKEN:
        return jsonify({"ok": False, "message": "Token inválido. Recargá la página."}), 403


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def body():
    return request.get_json(silent=True) or {}


# ---------- pages and API ----------

@app.route("/")
def index():
    donate = None
    if (APP_FILE.parent / "static" / DONATE["qr"]).is_file():
        donate = DONATE
    return render_template("index.html", token=TOKEN, version=VERSION, developer=DEVELOPER, donate=donate)


@app.route("/api/version")
def api_version():
    return jsonify({"app": "ai-control-center", "version": VERSION})


def loaded_models():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/ps", timeout=2) as response:
            return json.loads(response.read().decode("utf-8")).get("models", [])
    except Exception:
        return None


@app.route("/api/status")
def api_status():
    cfg = run_detection()
    futures = [POOL.submit(services.status, sid, cfg["services"].get(sid)) for sid in ORDER]
    system = POOL.submit(metrics.system_metrics)
    items = []
    for sid, fut in zip(ORDER, futures):
        item = fut.result()
        item["candidates"] = CANDIDATES.get(sid, [])
        item["updating"] = update.running_for(sid)
        item["update"] = update.CHECKS.get(sid)
        items.append(item)
    return jsonify({"services": items, "metrics": system.result(), "models": loaded_models(),
                    "notes": DETECT_NOTES, "timestamp": int(time.time())})


@app.route("/api/detect", methods=["POST"])
def api_detect():
    run_detection(force=True)
    cfg = config.load()
    found = [CATALOG[s]["label"] for s in ORDER if cfg["services"].get(s)]
    return jsonify({"ok": True, "message": "Detectadas: " + (", ".join(found) if found else "ninguna")})


@app.route("/api/docker/containers")
def api_containers():
    items, err = detect.docker_containers()
    return jsonify({"containers": items or [], "error": err})


@app.route("/api/service/<service_id>/location", methods=["POST"])
def api_set_location(service_id):
    _location(service_id)
    loc, err = detect.validate_manual(service_id, body())
    if err:
        return jsonify({"ok": False, "message": err}), 400
    if loc["type"] == "process":
        services.ensure_user_unit(service_id, loc, force=True)
    config.update(lambda c: c["services"].__setitem__(service_id, loc))
    return jsonify({"ok": True, "message": "{} configurado.".format(CATALOG[service_id]["label"])})


@app.route("/api/service/<service_id>/<action>", methods=["POST"])
def api_service_action(service_id, action):
    loc = _location(service_id)
    if action not in services.ACTIONS:
        return jsonify({"ok": False, "message": "Operación no permitida."}), 400
    if not loc:
        return jsonify({"ok": False, "message": "Servicio no detectado."}), 400
    ok, msg = services.control(service_id, loc, action)
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 500)


@app.route("/api/service/<service_id>/autostart", methods=["POST"])
def api_autostart(service_id):
    loc = _location(service_id)
    if not loc:
        return jsonify({"ok": False, "message": "Servicio no detectado."}), 400
    ok, msg = services.set_autostart(service_id, loc, bool(body().get("enabled")))
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 500)


@app.route("/api/service/<service_id>/uninstall-plan")
def api_uninstall_plan(service_id):
    loc = _location(service_id)
    if not loc:
        return jsonify({"ok": False, "message": "Servicio no detectado."}), 400
    return jsonify(dict(uninstall.plan(service_id, loc), ok=True))


@app.route("/api/service/<service_id>/uninstall", methods=["POST"])
def api_uninstall(service_id):
    loc = _location(service_id)
    data = body()
    if not loc:
        return jsonify({"ok": False, "message": "Servicio no detectado."}), 400
    if str(data.get("confirm", "")).strip().lower() != CATALOG[service_id]["label"].lower():
        return jsonify({"ok": False, "message": "La confirmación no coincide con el nombre."}), 400
    keys = data.get("keys")
    if not isinstance(keys, list) or not keys:
        return jsonify({"ok": False, "message": "No elegiste nada para quitar."}), 400
    label = CATALOG[service_id]["label"]
    results, removed = uninstall.execute(service_id, loc, [str(k) for k in keys])
    if removed and CATALOG[service_id].get("custom"):
        def forget(c):
            c["custom"].pop(service_id, None)
            c["services"].pop(service_id, None)
        register_custom(config.update(forget)["custom"])
    elif removed:
        config.update(lambda c: c["services"].__setitem__(service_id, None))
    ok = all(r["ok"] for r in results)
    msg = "{} desinstalado.".format(label) if ok else "Algunas partes no se pudieron quitar."
    return jsonify({"ok": ok, "message": msg, "results": results})


@app.route("/api/service/<service_id>/update-info")
def api_update_info(service_id):
    loc = _location(service_id)
    if not loc:
        return jsonify({"ok": False, "message": "Servicio no detectado."}), 400
    return jsonify(dict(update.info(service_id, loc), ok=True))


@app.route("/api/service/<service_id>/update", methods=["POST"])
def api_update(service_id):
    loc = _location(service_id)
    if not loc:
        return jsonify({"ok": False, "message": "Servicio no detectado."}), 400
    job = update.start(service_id, loc)
    if job is None:
        return jsonify({"ok": False, "message": "Ya hay una actualización en curso."}), 409
    return jsonify({"ok": True, "job": job.id})


@app.route("/api/check-updates", methods=["POST"])
def api_check_updates():
    services_now = config.load()["services"]
    threading.Thread(target=update.check_all, args=(services_now,), daemon=True).start()
    return jsonify({"ok": True, "message": "Buscando actualizaciones…"})


@app.route("/api/custom", methods=["POST"])
def api_add_custom():
    data = body()
    label = str(data.get("label") or "").strip()[:40]
    if not label:
        return jsonify({"ok": False, "message": "Poné un nombre."}), 400
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:30] or "ia"
    sid = "custom-" + slug
    if sid in CATALOG and not CATALOG[sid].get("custom"):
        return jsonify({"ok": False, "message": "Ese nombre ya existe."}), 400
    port = data.get("port") or None
    try:
        port = int(port) if port else None
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "El puerto debe ser un número entre 1 y 65535."}), 400
    custom = {"label": label, "description": str(data.get("description") or "")[:80], "port": port}
    if data.get("type") == "docker":
        containers, err = detect.docker_containers()
        if err:
            return jsonify({"ok": False, "message": err}), 400
        name = str(data.get("container") or "")
        if name not in {c["name"] for c in containers}:
            return jsonify({"ok": False, "message": "Elegí un contenedor existente."}), 400
        loc = {"type": "docker", "container": name, "source": "manual"}
    else:
        folder = Path(os.path.expanduser(str(data.get("path") or "").strip()))
        command = str(data.get("command") or "").strip()
        if not folder.is_absolute() or not folder.is_dir():
            return jsonify({"ok": False, "message": "La carpeta no existe (usá una ruta absoluta)."}), 400
        if not command or len(command) > 500 or "\n" in command:
            return jsonify({"ok": False, "message": "Escribí el comando para iniciarla (una línea)."}), 400
        custom["command"] = command
        loc = {"type": "process", "kind": "dir", "path": str(folder.resolve()), "python": detect.python_for_dir(folder),
               "port": port, "unit_name": detect.user_unit_name(sid), "source": "manual"}

    def save(c):
        c["custom"][sid] = custom
        c["services"][sid] = loc
    cfg = config.update(save)
    register_custom(cfg["custom"])
    if loc["type"] == "process":
        services.ensure_user_unit(sid, loc, force=True)
    return jsonify({"ok": True, "message": "{} agregada.".format(label), "id": sid})


@app.route("/api/jobs/<job_id>")
def api_job(job_id):
    job = update.JOBS.get(job_id)
    if not job:
        abort(404)
    return jsonify(dict(job.as_dict(), ok=True))


@app.route("/api/service/<service_id>/job")
def api_service_job(service_id):
    jobs = [j for j in update.JOBS.values() if j.service == service_id]
    if not jobs:
        return jsonify({"ok": False, "message": "Sin actualizaciones."}), 404
    return jsonify(dict(jobs[-1].as_dict(), ok=True))


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "POST":
        data = body()
        ui = config.clean_ui(data.get("ui"))
        config.update(lambda c: c["ui"].update(ui))
        if isinstance(data.get("panel_autostart"), bool):
            set_panel_autostart(data["panel_autostart"])
    cfg = config.load()
    return jsonify({"ok": True, "ui": cfg["ui"], "defaults": config.DEFAULT_UI,
                    "panel_autostart": AUTOSTART_FILE.exists(), "version": VERSION})


@app.route("/api/model/unload", methods=["POST"])
def api_unload_model():
    name = body().get("name", "")
    # Model name validation prevents arbitrary URLs/commands; unload via Ollama keep_alive=0.
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", name):
        return jsonify({"ok": False, "message": "Nombre de modelo inválido."}), 400
    payload = json.dumps({"model": name, "keep_alive": 0}).encode()
    req = urllib.request.Request(OLLAMA_URL + "/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()
        return jsonify({"ok": True, "message": "Solicitud de descarga enviada para {}.".format(name)})
    except Exception as e:
        return jsonify({"ok": False, "message": "No se pudo descargar el modelo: {}".format(e)}), 500


# ---------- launcher ----------

def server_version():
    try:
        with urllib.request.urlopen(BASE_URL + "/api/version", timeout=1) as r:
            return json.loads(r.read().decode("utf-8")).get("version")
    except (urllib.error.URLError, ValueError, OSError):
        return None


def ensure_server():
    """Start the server in the background unless it is already running."""
    if server_version():
        return True
    if port_open(PORT):
        # An older panel (from the old install.sh) holds the port: stop its user service.
        run(["systemctl", "--user", "disable", "--now", "ai-control-center.service"], timeout=15)
        for _ in range(20):
            if not port_open(PORT):
                break
            time.sleep(0.25)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = open(str(LOG_FILE), "ab")
    subprocess.Popen([sys.executable, str(APP_FILE), "--server"], stdin=subprocess.DEVNULL,
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(APP_FILE.parent))
    for _ in range(60):
        if server_version():
            return True
        time.sleep(0.25)
    print("No se pudo iniciar el panel. Revisá {}".format(LOG_FILE), file=sys.stderr)
    return False


def main(argv):
    if "--server" in argv:
        register_custom(config.load()["custom"])
        update.start_checker(lambda: config.load()["services"],
                             lambda: config.load()["ui"].get("auto_update_check", True))
        # No external network exposure: bind loopback only.
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
        return 0
    if not ensure_server():
        return 1
    if "--background" not in argv:
        open_ui("--browser" in argv)
    return 0


def open_ui(browser=False):
    """Open the panel in its own window, or in the web browser as a fallback."""
    if not browser and Path("/usr/bin/python3").exists():
        # The window uses the system's GTK/WebKit, so run it with the system Python
        # and without variables that a snap or venv may have set.
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH")}
        if subprocess.call(["/usr/bin/python3", "-I", str(WINDOW_FILE), BASE_URL], env=env) != 3:
            return
    webbrowser.open(BASE_URL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
