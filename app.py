#!/usr/bin/env python3
"""AI Control Center - local-only dashboard for Ubuntu."""
from flask import Flask, jsonify, render_template, request
import subprocess, json, os, time, re, shutil
from pathlib import Path

app = Flask(__name__)
HOST = "127.0.0.1"
PORT = 8765
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
COMFY_DIR = Path(os.environ.get("COMFYUI_DIR", str(Path.home() / "Documents/IA/IA_VIDEOS/ComfyUI")))
COMFY_VENV_PY = COMFY_DIR / "venv" / "bin" / "python"
COMFY_MAIN = COMFY_DIR / "main.py"

# Fixed allowlist: requests never supply shell commands or arbitrary service names.
SERVICES = {
    "ollama": {"label": "Ollama", "kind": "system", "unit": "ollama.service", "url": "http://127.0.0.1:11434"},
    "open-webui": {"label": "Open WebUI", "kind": "docker", "container": "open-webui", "url": "http://127.0.0.1:3000"},
    "immich": {"label": "Immich", "kind": "docker", "container": "immich_server", "url": "http://127.0.0.1:2283"},
    "comfyui": {"label": "ComfyUI", "kind": "user", "unit": "ai-comfyui.service", "url": "http://127.0.0.1:8188"},
}
ACTIONS = {"start", "stop", "restart"}

def run(args, timeout=5):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": p.returncode == 0, "out": p.stdout.strip(), "err": p.stderr.strip(), "code": p.returncode}
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "out": "", "err": str(e), "code": -1}

def systemd_state(unit, user=False):
    args = ["systemctl"] + (["--user"] if user else []) + ["is-active", unit]
    r = run(args)
    return r["out"] if r["out"] else ("unknown" if "not found" in r["err"].lower() else "inactive")

def docker_state(container):
    r = run(["docker", "inspect", "--format", "{{.State.Status}}", container])
    return r["out"] if r["ok"] and r["out"] else ("missing" if "No such object" in r["err"] or "No such object" in r["out"] else "unavailable")

def get_json(url, timeout=2):
    # Use urllib only against fixed localhost Ollama URL.
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

def service_status(key, spec):
    if spec["kind"] == "system":
        state = systemd_state(spec["unit"])
    elif spec["kind"] == "user":
        state = systemd_state(spec["unit"], user=True)
    else:
        state = docker_state(spec["container"])
    return {
        "id": key, "name": spec["label"], "state": state,
        "running": state in ("active", "running"), "url": spec.get("url"),
        "kind": spec["kind"]
    }

def metrics():
    result = {"cpu_percent": None, "ram_total_mb": None, "ram_used_mb": None,
              "ram_percent": None, "gpu": None, "gpu_error": None}
    try:
        import psutil
        vm = psutil.virtual_memory()
        result.update(cpu_percent=psutil.cpu_percent(interval=0.15),
                      ram_total_mb=round(vm.total / 1048576),
                      ram_used_mb=round((vm.total-vm.available) / 1048576),
                      ram_percent=vm.percent)
    except Exception:
        pass
    if shutil.which("nvidia-smi"):
        r = run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"], timeout=3)
        if r["ok"] and r["out"]:
            parts = [x.strip() for x in r["out"].splitlines()[0].split(",")]
            if len(parts) >= 5:
                try:
                    result["gpu"] = {"name": parts[0], "util_percent": int(parts[1]),
                                     "vram_used_mb": int(parts[2]), "vram_total_mb": int(parts[3]),
                                     "temperature_c": int(parts[4])}
                except ValueError:
                    result["gpu_error"] = "No se pudieron interpretar las métricas de NVIDIA."
        else:
            result["gpu_error"] = r["err"] or "nvidia-smi no devolvió datos."
    else:
        result["gpu_error"] = "nvidia-smi no está instalado o no está en PATH."
    return result

def loaded_models():
    data = get_json(OLLAMA_URL + "/api/ps")
    if data is None:
        return None
    return data.get("models", [])

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/status")
def api_status():
    return jsonify({"services": [service_status(k, v) for k, v in SERVICES.items()],
                    "metrics": metrics(), "models": loaded_models(), "timestamp": int(time.time())})

@app.post("/api/service/<service_id>/<action>")
def api_service_action(service_id, action):
    if service_id not in SERVICES or action not in ACTIONS:
        return jsonify({"ok": False, "message": "Servicio u operación no permitidos."}), 400
    spec = SERVICES[service_id]
    if spec["kind"] == "system":
        # install.sh grants only these exact systemctl commands through sudoers.
        args = ["sudo", "-n", "systemctl", action, spec["unit"]]
    elif spec["kind"] == "user":
        args = ["systemctl", "--user", action, spec["unit"]]
    else:
        args = ["docker", action if action != "restart" else "restart", spec["container"]]
    r = run(args, timeout=20)
    if not r["ok"]:
        msg = r["err"] or r["out"] or "La operación falló."
        if service_id == "ollama" and ("password" in msg.lower() or "sudo" in msg.lower()):
            msg = "No se pudo ejecutar systemctl para Ollama. Ejecutá install.sh para configurar permisos limitados."
        return jsonify({"ok": False, "message": msg}), 500
    return jsonify({"ok": True, "message": f"{spec['label']}: {action} solicitado."})

@app.post("/api/model/unload")
def api_unload_model():
    body = request.get_json(silent=True) or {}
    name = body.get("name", "")
    # Model name validation prevents arbitrary URLs/commands; unload via Ollama keep_alive=0.
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", name):
        return jsonify({"ok": False, "message": "Nombre de modelo inválido."}), 400
    import urllib.request, urllib.error
    payload = json.dumps({"model": name, "keep_alive": 0}).encode()
    req = urllib.request.Request(OLLAMA_URL + "/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()
        return jsonify({"ok": True, "message": f"Solicitud de descarga enviada para {name}."})
    except Exception as e:
        return jsonify({"ok": False, "message": f"No se pudo descargar el modelo: {e}"}), 500

if __name__ == "__main__":
    # No external network exposure: bind loopback only.
    app.run(host=HOST, port=PORT, debug=False)
