"""Update an installed AI tool to its latest version, as a background job.

Methods:
  Ollama (system service)  official installer, through a root helper (asks the admin password)
  Docker compose project   docker compose pull + up -d (Immich and compose setups)
  Single Docker container  docker pull, then recreate the container with the same settings
  Folder with git          git pull + pip install -r requirements.txt (ComfyUI)
  pip / pipx package       pip install -U / pipx upgrade (Open WebUI without Docker)
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from .catalog import CATALOG
from .services import _installed_helper, _user_unit_state, docker_inspect
from .uninstall import _pipx_managed, _python_of_script, npm_package
from .util import HOME, is_under, run

JOBS = {}
_lock = threading.Lock()
_latest_cache = {}


# ---------- what can be updated and how ----------

def _compose_labels(container):
    info = docker_inspect([container])
    if not info:
        return None, None
    labels = info[0].get("Config", {}).get("Labels") or {}
    if labels.get("com.docker.compose.project") and labels.get("com.docker.compose.project.working_dir"):
        return info[0], labels
    return info[0], None


def _compose_cmd():
    if run(["docker", "compose", "version"])["ok"]:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return None


def _version(text):
    m = re.search(r"(\d+\.\d+\.\d+)", text or "")
    return m.group(1) if m else None


def _ollama_latest():
    cached = _latest_cache.get("ollama")
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    try:
        req = urllib.request.Request("https://api.github.com/repos/ollama/ollama/releases/latest",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "ai-control-center"})
        with urllib.request.urlopen(req, timeout=6) as r:
            latest = _version(json.loads(r.read().decode("utf-8")).get("tag_name"))
    except Exception:
        latest = None
    _latest_cache["ollama"] = (time.time(), latest)
    return latest


def _pip_version(python, package):
    if not python:
        return None
    r = run([python, "-m", "pip", "show", package], timeout=20)
    m = re.search(r"^Version:\s*(\S+)", r["out"], re.M)
    return m.group(1) if m else None


def info(service_id, loc):
    """Describe how the update would be done, and the versions when known."""
    spec = CATALOG[service_id]
    out = {"supported": False, "method": "", "current": None, "latest": None, "up_to_date": None,
           "password": False, "warning": None}
    if loc["type"] == "systemd" and service_id == "ollama":
        out.update(supported=bool(_installed_helper("aicc-update-helper")), password=True,
                   method="Instalador oficial de Ollama (ollama.com/install.sh). Pide la contraseña de administrador.")
        exe = shutil.which("ollama")
        out["current"] = _version(run([exe, "--version"])["out"] + " " + run([exe, "--version"])["err"]) if exe else None
        out["latest"] = _ollama_latest()
        if out["current"] and out["latest"]:
            out["up_to_date"] = out["current"] == out["latest"]
        if not out["supported"]:
            out["warning"] = "Necesita el paquete .deb o snap instalado."
    elif loc["type"] == "docker":
        main, labels = _compose_labels(loc["container"])
        if main is None:
            out["warning"] = "El contenedor ya no existe."
            return out
        out["current"] = main.get("Config", {}).get("Image")
        if labels:
            out.update(supported=bool(_compose_cmd()),
                       method="docker compose pull + up -d en {}".format(labels["com.docker.compose.project.working_dir"]))
            if not out["supported"]:
                out["warning"] = "No se encontró docker compose."
        else:
            out.update(supported=True, method="Descarga la imagen nueva y recrea el contenedor con la misma configuración "
                                              "(puertos, volúmenes, variables). Tus datos en volúmenes se conservan.")
        if service_id == "immich":
            out["warning"] = ("Immich a veces trae cambios que requieren pasos manuales. Revisá las notas en "
                              "github.com/immich-app/immich/releases antes de actualizar.")
    elif loc["type"] == "app":
        if loc.get("source_kind") == "flatpak":
            out.update(supported=True, method="flatpak update " + loc["flatpak_id"])
        else:
            out["warning"] = ("{} se actualiza desde la propia app o descargando la versión nueva{}."
                              .format(spec["label"], " en " + spec["homepage"] if spec.get("homepage") else ""))
    elif loc["type"] == "process" and loc.get("kind") == "dir" and spec.get("update_pip_package"):
        out.update(supported=True, method="pip install -U {} en su entorno virtual".format(spec["update_pip_package"]))
        out["current"] = _pip_version(loc.get("python"), spec["update_pip_package"])
    elif loc["type"] == "process" and loc.get("kind") == "dir":
        path = Path(loc["path"])
        if not (path / ".git").exists():
            out["warning"] = "Esta carpeta no es un repositorio git; actualizala con el método con que la instalaste."
            return out
        extra = " y npm install" if spec.get("update_npm") else " y pip install -r {}".format(
            spec.get("pip_requirements", "requirements.txt"))
        out.update(supported=True, method="git pull" + extra)
        out["current"] = run(["git", "-C", str(path), "log", "-1", "--format=%h (%cs)"])["out"] or None
        if run(["git", "-C", str(path), "fetch", "--quiet"], timeout=30)["ok"]:
            behind = run(["git", "-C", str(path), "rev-list", "--count", "HEAD..@{u}"])["out"]
            if behind.isdigit():
                out["up_to_date"] = behind == "0"
                out["latest"] = "{} cambios nuevos".format(behind) if behind != "0" else out["current"]
    elif loc["type"] == "process" and service_id == "open-webui":
        how = "pipx upgrade open-webui" if _pipx_managed(loc["path"]) else "pip install -U open-webui"
        out.update(supported=True, method=how)
    elif loc["type"] == "process" and npm_package(service_id, loc["path"]):
        out.update(supported=True, method="npm install -g {}@latest".format(npm_package(service_id, loc["path"])))
    else:
        out["warning"] = "Actualizá {} con el mismo método con que lo instalaste.".format(spec["label"])
    return out


# ---------- jobs ----------

class Job:
    def __init__(self, service_id):
        self.id = uuid.uuid4().hex[:12]
        self.service = service_id
        self.state = "running"
        self.lines = []
        self.message = ""

    def log(self, text):
        for line in str(text).splitlines() or [""]:
            self.lines.append(line[:500])
        del self.lines[:-400]

    def step(self, args, cwd=None, timeout=3600):
        """Run a command, streaming its output to the log. Returns the exit code."""
        self.log("$ " + " ".join(args))
        try:
            p = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors="replace", bufsize=1)
        except OSError as e:
            self.log(str(e))
            return -1
        start = time.time()
        for line in p.stdout:
            self.log(line.rstrip())
            if time.time() - start > timeout:
                p.kill()
                self.log("Tiempo de espera agotado.")
        return p.wait()

    def as_dict(self):
        return {"id": self.id, "service": self.service, "state": self.state, "log": self.lines[-200:],
                "message": self.message}


def running_for(service_id):
    with _lock:
        return any(j.service == service_id and j.state == "running" for j in JOBS.values())


def start(service_id, loc):
    with _lock:
        if any(j.service == service_id and j.state == "running" for j in JOBS.values()):
            return None
        job = Job(service_id)
        JOBS[job.id] = job
    threading.Thread(target=_run, args=(job, service_id, loc), daemon=True).start()
    return job


def _run(job, service_id, loc):
    try:
        ok, msg = _dispatch(job, service_id, loc)
    except Exception as e:  # keep the job visible instead of losing the thread
        ok, msg = False, "Error inesperado: {}".format(e)
    if ok:
        check(service_id, loc)  # clear the "update available" badge
    job.message = msg
    job.state = "done" if ok else "error"
    job.log("")
    job.log(msg)


def _dispatch(job, service_id, loc):
    label = CATALOG[service_id]["label"]
    if loc["type"] == "systemd" and service_id == "ollama":
        helper = _installed_helper("aicc-update-helper")
        if not helper:
            return False, "Necesita el paquete .deb o snap instalado."
        rc = job.step(["pkexec", helper, "ollama"])
        if rc in (126, 127):
            return False, "Se canceló la autorización de administrador."
        return rc == 0, "{} actualizado.".format(label) if rc == 0 else "Falló la actualización de {}.".format(label)
    if loc["type"] == "docker":
        main, labels = _compose_labels(loc["container"])
        if main is None:
            return False, "El contenedor ya no existe."
        if labels:
            return _update_compose(job, label, main, labels)
        return _update_container(job, label, main)
    spec = CATALOG[service_id]
    if loc["type"] == "app" and loc.get("source_kind") == "flatpak":
        rc = job.step(["flatpak", "update", "-y", loc["flatpak_id"]])
        return rc == 0, "{} actualizado.".format(label) if rc == 0 else "Falló flatpak update."
    if loc["type"] == "process" and loc.get("kind") == "dir" and spec.get("update_pip_package"):
        unit = loc.get("unit_name")
        was_active = bool(unit) and _user_unit_state(unit) == "active"
        if was_active:
            job.step(["systemctl", "--user", "stop", unit])
        rc = job.step([loc["python"], "-m", "pip", "install", "-U", spec["update_pip_package"]])
        _restart_unit_if(job, unit, was_active)
        return rc == 0, "{} actualizado.".format(label) if rc == 0 else "Falló pip install."
    if loc["type"] == "process" and loc.get("kind") == "dir":
        return _update_git(job, label, loc, spec)
    if loc["type"] == "process" and npm_package(service_id, loc["path"]):
        unit = loc.get("unit_name")
        was_active = bool(unit) and _user_unit_state(unit) == "active"
        rc = job.step(["/bin/bash", "-lc", "npm install -g {}@latest".format(npm_package(service_id, loc["path"]))])
        _restart_unit_if(job, unit, was_active)
        return rc == 0, "{} actualizado.".format(label) if rc == 0 else "Falló npm install."
    if loc["type"] == "process" and service_id == "open-webui":
        return _update_pip(job, label, loc)
    return False, "No se puede actualizar {} desde el panel.".format(label)


def _restart_unit_if(job, unit, was_active):
    if was_active:
        job.step(["systemctl", "--user", "restart", unit])


def _update_git(job, label, loc, spec):
    path = loc["path"]
    unit = loc.get("unit_name")
    was_active = bool(unit) and _user_unit_state(unit) == "active"
    if was_active:
        job.step(["systemctl", "--user", "stop", unit])
    if job.step(["git", "-C", path, "pull", "--ff-only"]) != 0:
        _restart_unit_if(job, unit, was_active)
        return False, "git pull falló (¿hay cambios locales en la carpeta?). No se modificó nada más."
    if spec.get("update_npm"):
        if job.step(["/bin/bash", "-lc", "npm install --no-audit --no-fund"], cwd=path) != 0:
            _restart_unit_if(job, unit, was_active)
            return False, "El código se actualizó, pero falló npm install. Revisá el registro."
    py = loc.get("python") or ""
    req = os.path.join(path, spec.get("pip_requirements", "requirements.txt"))
    if os.path.exists(req) and not spec.get("update_npm"):
        if is_under(py, HOME) or "/venv/" in py or "/.venv/" in py:
            if job.step([py, "-m", "pip", "install", "-r", req], cwd=path) != 0:
                _restart_unit_if(job, unit, was_active)
                return False, "El código se actualizó, pero falló pip install. Revisá el registro."
        else:
            job.log("Python del sistema: no se instalan dependencias para no romper el sistema.")
    _restart_unit_if(job, unit, was_active)
    return True, "{} actualizado.".format(label)


def _update_pip(job, label, loc):
    unit = loc.get("unit_name")
    was_active = bool(unit) and _user_unit_state(unit) == "active"
    if _pipx_managed(loc["path"]):
        rc = job.step(["pipx", "upgrade", "open-webui"])
    else:
        rc = job.step([_python_of_script(loc["path"]) or "python3", "-m", "pip", "install", "-U", "open-webui"])
    _restart_unit_if(job, unit, was_active)
    return rc == 0, "{} actualizado.".format(label) if rc == 0 else "Falló la actualización."


def _update_compose(job, label, main, labels):
    cmd = _compose_cmd()
    if not cmd:
        return False, "No se encontró docker compose."
    project = labels["com.docker.compose.project"]
    workdir = labels["com.docker.compose.project.working_dir"]
    base = cmd + ["-p", project, "--project-directory", workdir]
    for f in (labels.get("com.docker.compose.project.config_files") or "").split(","):
        if f:
            base += ["-f", f]
    was_running = main.get("State", {}).get("Running", False)
    if job.step(base + ["pull"]) != 0:
        return False, "No se pudieron descargar las imágenes nuevas."
    rc = job.step(base + (["up", "-d"] if was_running else ["up", "--no-start"]))
    if rc != 0:
        return False, "docker compose up falló. Revisá el registro."
    return True, "{} actualizado.".format(label)


def _image_info(ref):
    r = run(["docker", "image", "inspect", ref], timeout=15)
    try:
        return json.loads(r["out"])[0] if r["ok"] else {}
    except (ValueError, IndexError):
        return {}


def recreate_args(c, old_image):
    """Rebuild "docker create" arguments from a container's inspect data."""
    hc, cfg = c.get("HostConfig", {}), c.get("Config", {})
    img_cfg = old_image.get("Config", {}) or {}
    args = ["docker", "create", "--name", c["Name"].lstrip("/")]
    rp = hc.get("RestartPolicy") or {}
    if rp.get("Name") and rp["Name"] != "no":
        args += ["--restart", rp["Name"] + (":{}".format(rp["MaximumRetryCount"])
                                             if rp["Name"] == "on-failure" and rp.get("MaximumRetryCount") else "")]
    for m in c.get("Mounts", []):
        src = m.get("Name") if m.get("Type") == "volume" else m.get("Source")
        if m.get("Type") in ("volume", "bind") and src:
            args += ["-v", "{}:{}{}".format(src, m["Destination"], "" if m.get("RW", True) else ":ro")]
    for cport, binds in sorted((hc.get("PortBindings") or {}).items()):
        for b in binds or []:
            ip = b.get("HostIp") or ""
            host = "{}:{}".format(ip, b.get("HostPort")) if ip not in ("", "0.0.0.0", "::") else str(b.get("HostPort") or "")
            args += ["-p", "{}:{}".format(host, cport) if host else cport]
    if hc.get("PublishAllPorts"):
        args.append("-P")
    mode = hc.get("NetworkMode") or ""
    if mode and mode not in ("default", "bridge"):
        args += ["--network", mode]
    for h in hc.get("ExtraHosts") or []:
        args += ["--add-host", h]
    for d in hc.get("Devices") or []:
        args += ["--device", "{}:{}:{}".format(d["PathOnHost"], d["PathInContainer"], d.get("CgroupPermissions", "rwm"))]
    for req in hc.get("DeviceRequests") or []:
        if any("gpu" in caps for caps in req.get("Capabilities") or []):
            ids = req.get("DeviceIDs") or []
            args += ["--gpus", "device=" + ",".join(ids) if ids else "all"]
    if hc.get("Privileged"):
        args.append("--privileged")
    for cap in hc.get("CapAdd") or []:
        args += ["--cap-add", cap]
    if hc.get("IpcMode") == "host":
        args += ["--ipc", "host"]
    if hc.get("ShmSize") and hc["ShmSize"] != 67108864:
        args += ["--shm-size", str(hc["ShmSize"])]
    image_env = set(img_cfg.get("Env") or [])
    for e in cfg.get("Env") or []:
        if e not in image_env:  # only what the user set; image defaults come from the new image
            args += ["-e", e]
    if cfg.get("User") and cfg["User"] != img_cfg.get("User"):
        args += ["--user", cfg["User"]]
    if cfg.get("WorkingDir") and cfg["WorkingDir"] != img_cfg.get("WorkingDir"):
        args += ["-w", cfg["WorkingDir"]]
    cmd = []
    if cfg.get("Entrypoint") and cfg["Entrypoint"] != img_cfg.get("Entrypoint"):
        args += ["--entrypoint", cfg["Entrypoint"][0]]
        cmd = list(cfg["Entrypoint"][1:])
    if cfg.get("Cmd") and (cmd or cfg["Cmd"] != img_cfg.get("Cmd")):
        cmd += list(cfg["Cmd"])
    args.append(cfg["Image"])
    return args + cmd


def _update_container(job, label, c):
    name = c["Name"].lstrip("/")
    ref = c.get("Config", {}).get("Image", "")
    if not ref or ref.startswith("sha256:"):
        return False, "El contenedor no tiene una imagen con nombre; no se puede actualizar."
    old_id = c.get("Image")
    if job.step(["docker", "pull", ref]) != 0:
        return False, "No se pudo descargar la imagen nueva."
    new_id = _image_info(ref).get("Id")
    if new_id == old_id:
        return True, "{} ya estaba en la última versión.".format(label)
    args = recreate_args(c, _image_info(old_id))
    was_running = c.get("State", {}).get("Running", False)
    backup = name + "-aicc-old"
    job.step(["docker", "stop", name])
    if job.step(["docker", "rename", name, backup]) != 0:
        job.step(["docker", "start", name]) if was_running else None
        return False, "No se pudo preparar el reemplazo del contenedor."

    def rollback(reason):
        job.step(["docker", "rm", "-f", name])
        job.step(["docker", "rename", backup, name])
        if was_running:
            job.step(["docker", "start", name])
        return False, reason + " Se restauró el contenedor anterior."

    if job.step(args) != 0:
        return rollback("No se pudo crear el contenedor nuevo.")
    if was_running and job.step(["docker", "start", name]) != 0:
        return rollback("El contenedor nuevo no arrancó.")
    job.step(["docker", "rm", backup])
    job.step(["docker", "image", "rm", old_id])  # frees space; fails harmlessly if still used
    return True, "{} actualizado a la última imagen.".format(label)


# ---------- "update available" checks ----------

CHECKS = {}   # service id -> {"available": True/False/None, "latest": str or None, "checked": time}


def _remote_digest(ref):
    r = run(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"], timeout=40)
    try:
        return json.loads(r["out"]).get("digest") if r["ok"] else None
    except ValueError:
        return None


def _docker_available(container):
    main, labels = _compose_labels(container)
    if main is None:
        return None, None
    names = [container]
    if labels:
        r = run(["docker", "ps", "-a", "--filter", "label=com.docker.compose.project=" + labels["com.docker.compose.project"],
                 "--format", "{{.Names}}"], timeout=10)
        names = r["out"].splitlines() or names
    seen, unknown = set(), False
    for c in docker_inspect(names):
        ref, image_id = c.get("Config", {}).get("Image", ""), c.get("Image")
        if not ref or ref.startswith("sha256:") or ref in seen:
            continue
        seen.add(ref)
        remote = _remote_digest(ref)
        if not remote:
            unknown = True
            continue
        local = _image_info(image_id).get("RepoDigests") or []
        if not any(d.endswith(remote) for d in local):
            return True, ref
    return (None if unknown else False), None


def _pip_latest(python, package):
    r = run([python, "-m", "pip", "index", "versions", package], timeout=40)
    m = re.search(re.escape(package) + r"\s*\(([^)]+)\)", r["out"], re.I)
    return m.group(1) if m else None


def check(service_id, loc):
    """Is there a newer version? Cheap checks only; nothing is downloaded or changed."""
    spec = CATALOG[service_id]
    available, latest = None, None
    try:
        if loc["type"] == "systemd" and service_id == "ollama":
            i = info(service_id, loc)
            latest = i["latest"]
            available = (not i["up_to_date"]) if i["up_to_date"] is not None else None
        elif loc["type"] == "docker":
            available, _ref = _docker_available(loc["container"])
        elif loc["type"] == "app" and loc.get("source_kind") == "flatpak":
            r = run(["flatpak", "remote-ls", "--updates", "--app", "--columns=application"], timeout=60)
            available = loc["flatpak_id"] in r["out"].split() if r["ok"] else None
        elif loc["type"] == "process" and loc.get("kind") == "dir" and spec.get("update_pip_package"):
            current = _pip_version(loc.get("python"), spec["update_pip_package"])
            latest = _pip_latest(loc.get("python"), spec["update_pip_package"])
            available = (current != latest) if current and latest else None
        elif loc["type"] == "process" and loc.get("kind") == "dir" and (Path(loc["path"]) / ".git").exists():
            if run(["git", "-C", loc["path"], "fetch", "--quiet"], timeout=60)["ok"]:
                behind = run(["git", "-C", loc["path"], "rev-list", "--count", "HEAD..@{u}"])["out"]
                available = behind.isdigit() and behind != "0"
        elif loc["type"] == "process" and service_id == "open-webui" and not _pipx_managed(loc["path"]):
            py = _python_of_script(loc["path"])
            current, latest = (_pip_version(py, "open-webui"), _pip_latest(py, "open-webui")) if py else (None, None)
            available = (current != latest) if current and latest else None
    except Exception:
        available = None
    CHECKS[service_id] = {"available": available, "latest": latest, "checked": time.time()}
    return CHECKS[service_id]


def check_all(locations):
    for sid, loc in locations.items():
        if loc and sid in CATALOG:
            check(sid, loc)


def start_checker(get_locations, enabled, interval=6 * 3600, first_delay=30):
    """Background thread that refreshes CHECKS periodically."""
    def loop():
        time.sleep(first_delay)
        while True:
            if enabled():
                check_all(get_locations())
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True).start()
