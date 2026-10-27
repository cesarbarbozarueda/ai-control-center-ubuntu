"""Full removal of a service: build a plan the user reviews, then execute it.

The browser only sends back the keys of plan items; every path and command is
recomputed here from the stored location, never taken from the request.
"""
import os
from pathlib import Path

from .catalog import CATALOG
from .services import _installed_helper, docker_group, docker_inspect, remove_user_unit, root_systemctl
from .util import HOME, dir_size_mb, expand, is_under, run, safe_rmtree


def _item(key, label, detail, group, root=False, size_mb=None):
    return {"key": key, "label": label, "detail": detail, "group": group,
            "default": group == "program", "root": root, "size_mb": size_mb}


def _user_data_items(spec):
    items = []
    for i, raw in enumerate(spec.get("user_data", [])):
        p = expand(raw)
        if p.exists():
            items.append(_item("user-data-{}".format(i), "Datos de usuario", str(p), "data",
                               size_mb=dir_size_mb(p)))
    return items


def _pipx_managed(path):
    real = os.path.realpath(path)
    return "/pipx/" in real


def plan(service_id, loc):
    spec = CATALOG[service_id]
    items, notes = [], []
    if loc["type"] == "systemd":
        items.append(_item("root-program", "Servicio y programa de {}".format(spec["label"]),
                           "Detiene y quita {} y sus ejecutables. Pide la contraseña de administrador."
                           .format(loc["unit"]), "program", root=True))
        items.append(_item("root-data", "Modelos descargados y usuario del sistema",
                           "/usr/share/ollama y el usuario ollama", "data", root=True))
        items += _user_data_items(spec)
    elif loc["type"] == "docker":
        main, names = docker_group(loc["container"])
        if main is None:
            notes.append("El contenedor ya no existe.")
        else:
            info = docker_inspect(names)
            images = sorted({c.get("Config", {}).get("Image", "") for c in info} - {""})
            volumes = sorted({m["Name"] for c in info for m in c.get("Mounts", [])
                              if m.get("Type") == "volume" and m.get("Name")})
            binds = sorted({m["Source"] for c in info for m in c.get("Mounts", [])
                            if m.get("Type") == "bind" and m.get("Source")})
            items.append(_item("containers", "Contenedores", ", ".join(names), "program"))
            if images:
                items.append(_item("images", "Imágenes Docker", ", ".join(images), "program"))
            if volumes:
                items.append(_item("volumes", "Volúmenes Docker (datos, bases de datos)", ", ".join(volumes), "data"))
            workdir = (main.get("Config", {}).get("Labels") or {}).get("com.docker.compose.project.working_dir")
            if workdir:
                notes.append("La carpeta de docker compose ({}) no se borra.".format(workdir))
            if binds:
                notes.append("Las carpetas montadas no se borran, por si contienen tus archivos: "
                             + ", ".join(binds[:6]) + (" …" if len(binds) > 6 else ""))
    elif loc["type"] == "app":
        kind, path = loc.get("source_kind"), loc.get("path", "")
        if kind == "flatpak":
            items.append(_item("flatpak", "App Flatpak", "flatpak uninstall " + loc["flatpak_id"], "program"))
            var = expand("~/.var/app/" + loc["flatpak_id"])
            if var.exists():
                items.append(_item("flatpak-data", "Datos de la app", str(var), "data", size_mb=dir_size_mb(var)))
        elif kind == "deb" and loc.get("package"):
            items.append(_item("apt-remove", "Paquete " + loc["package"],
                               "apt remove {} (pide la contraseña de administrador)".format(loc["package"]),
                               "program", root=True))
        elif is_under(path, HOME):
            items.append(_item("app-file", "Programa", path, "program"))
        else:
            notes.append("{} está fuera de tu carpeta personal; quitalo con el método con que lo instalaste.".format(path))
        items += _user_data_items(spec)
    elif spec.get("custom"):
        items.append(_item("forget", "Quitarla del panel y su servicio de inicio", loc["path"], "program"))
        if is_under(loc["path"], HOME):
            items.append(_item("custom-folder", "Carpeta completa", loc["path"], "data",
                               size_mb=dir_size_mb(loc["path"])))
    else:
        path = Path(loc["path"])
        if loc.get("kind") == "dir":
            keep = [d for d in spec.get("dir_data", []) if (path / d).exists()]
            detail = str(path)
            if keep:
                detail += " (se conservan: {})".format(", ".join(keep))
            items.append(_item("program", "Programa, entorno virtual y servicio", detail, "program"))
            py = Path(loc.get("python", ""))
            venv = py.parent.parent if py.parent.name == "bin" else None
            if venv and venv.parent == path.parent and is_under(venv, HOME):
                items.append(_item("venv", "Entorno virtual externo", str(venv), "program"))
            for d in keep:
                items.append(_item("data-" + d, "Carpeta {}".format(d), str(path / d), "data",
                                   size_mb=dir_size_mb(path / d)))
        else:
            if service_id == "open-webui":
                how = "pipx uninstall open-webui" if _pipx_managed(path) else "pip uninstall open-webui"
                items.append(_item("program", "Paquete y servicio de Open WebUI", how, "program"))
            elif npm_package(service_id, path):
                items.append(_item("npm", "Paquete npm y servicio", "npm uninstall -g " + npm_package(service_id, path),
                                   "program"))
            elif is_under(path, HOME):
                items.append(_item("program", "Ejecutable y servicio", str(path), "program"))
            elif service_id == "ollama":
                items.append(_item("root-program", "Ejecutable y servicio", str(path) +
                                   " (pide la contraseña de administrador)", "program", root=True))
            else:
                notes.append("{} está fuera de tu carpeta personal; quitalo con el método con que lo instalaste."
                             .format(path))
            items += _user_data_items(spec)
    return {"items": items, "notes": notes}


def npm_package(service_id, path):
    """npm package name when the executable comes from "npm install -g"."""
    names = {"flowise": "flowise", "n8n": "n8n"}
    return names.get(service_id) if "node_modules" in os.path.realpath(str(path)) else None


def _python_of_script(path):
    try:
        with open(str(path), "rb") as f:
            first = f.readline().decode("utf-8", "replace").strip()
    except OSError:
        return None
    if first.startswith("#!"):
        parts = first[2:].split()
        if parts and "python" in parts[0]:
            return parts[0]
    return None


def execute(service_id, loc, keys):
    """Run the selected plan items. Returns (results, program_removed)."""
    spec = CATALOG[service_id]
    current = {i["key"]: i for i in plan(service_id, loc)["items"]}
    keys = [k for k in keys if k in current]
    results = []

    def done(key, ok, msg):
        results.append({"key": key, "label": current[key]["label"], "ok": ok, "message": msg})

    # Stop the service first so files are not in use.
    if loc["type"] == "process":
        remove_user_unit(loc)
    elif loc["type"] == "systemd" and "root-program" in keys:
        root_systemctl("stop", loc["unit"])

    if loc["type"] == "app":
        from .services import _app_stop, remove_app_autostart
        _app_stop(service_id, loc)
        remove_app_autostart(service_id)

    root_keys = [k for k in keys if current[k]["root"] and k != "apt-remove"]
    if root_keys:
        helper = _installed_helper("aicc-uninstall-helper")
        if not helper:
            for k in root_keys:
                done(k, False, "Necesita el paquete .deb instalado (o hacelo a mano con sudo).")
        else:
            args = ["pkexec", helper, "ollama"]
            if "root-data" in root_keys:
                args.append("--data")
            r = run(args, timeout=300)
            for k in root_keys:
                if r["ok"]:
                    done(k, True, "Quitado.")
                elif r["code"] in (126, 127):
                    done(k, False, "Se canceló la autorización de administrador.")
                else:
                    done(k, False, r["err"] or r["out"] or "Falló la desinstalación.")

    if "apt-remove" in keys:
        r = run(["pkexec", "apt-get", "remove", "-y", loc["package"]], timeout=600)
        done("apt-remove", r["ok"], "Quitado." if r["ok"] else
             ("Se canceló la autorización." if r["code"] in (126, 127) else r["err"] or r["out"]))
    if "flatpak" in keys:
        r = run(["flatpak", "uninstall", "-y", loc["flatpak_id"]], timeout=600)
        done("flatpak", r["ok"], "Quitada." if r["ok"] else r["err"] or r["out"])
    if "flatpak-data" in keys:
        ok, msg = safe_rmtree(expand("~/.var/app/" + loc["flatpak_id"]))
        done("flatpak-data", ok, msg)
    if "app-file" in keys:
        ok, msg = safe_rmtree(loc["path"])
        done("app-file", ok, msg)
    if "forget" in keys:
        done("forget", True, "Quitada del panel.")
    if "custom-folder" in keys:
        ok, msg = safe_rmtree(loc["path"])
        done("custom-folder", ok, msg)
    if "npm" in keys:
        r = run(["/bin/bash", "-lc", "npm uninstall -g " + npm_package(service_id, loc["path"])], timeout=300)
        done("npm", r["ok"], "Quitado." if r["ok"] else r["err"] or r["out"])

    if loc["type"] == "docker":
        main, names = docker_group(loc["container"])
        info = docker_inspect(names)
        if "containers" in keys:
            r = run(["docker", "rm", "-f"] + names, timeout=120)
            done("containers", r["ok"], "Eliminados." if r["ok"] else r["err"])
        if "images" in keys:
            images = sorted({c.get("Config", {}).get("Image", "") for c in info} - {""})
            r = run(["docker", "rmi"] + images, timeout=300)
            done("images", r["ok"], "Eliminadas." if r["ok"] else (r["err"] or "Alguna imagen sigue en uso."))
        if "volumes" in keys:
            volumes = sorted({m["Name"] for c in info for m in c.get("Mounts", [])
                              if m.get("Type") == "volume" and m.get("Name")})
            r = run(["docker", "volume", "rm"] + volumes, timeout=120)
            done("volumes", r["ok"], "Eliminados." if r["ok"] else r["err"])

    if loc["type"] == "process":
        path = Path(loc["path"])
        if "program" in keys:
            if loc.get("kind") == "dir":
                keep = set(spec.get("dir_data", []))
                errors = []
                if path.is_dir():
                    for child in path.iterdir():
                        if child.name in keep:
                            continue
                        ok, msg = safe_rmtree(child)
                        if not ok:
                            errors.append("{}: {}".format(child.name, msg))
                done("program", not errors, "Eliminado." if not errors else "; ".join(errors[:3]))
            elif service_id == "open-webui":
                if _pipx_managed(path):
                    r = run(["pipx", "uninstall", "open-webui"], timeout=180)
                else:
                    py = _python_of_script(path) or "python3"
                    r = run([py, "-m", "pip", "uninstall", "-y", "open-webui"], timeout=180)
                done("program", r["ok"], "Eliminado." if r["ok"] else (r["err"] or r["out"]))
            else:
                ok, msg = safe_rmtree(path)
                done("program", ok, msg)
        if "venv" in keys:
            ok, msg = safe_rmtree(Path(loc["python"]).parent.parent)
            done("venv", ok, msg)
        for d in spec.get("dir_data", []):
            key = "data-" + d
            if key in keys:
                ok, msg = safe_rmtree(path / d)
                done(key, ok, msg)
        if loc.get("kind") == "dir" and "program" in keys and path.is_dir() and not any(path.iterdir()):
            path.rmdir()

    for i, raw in enumerate(spec.get("user_data", [])):
        key = "user-data-{}".format(i)
        if key in keys:
            ok, msg = safe_rmtree(expand(raw))
            done(key, ok, msg)

    program_keys = [k for k in keys if current[k]["group"] == "program"]
    program_removed = bool(program_keys) and all(r["ok"] for r in results if r["key"] in program_keys)
    return results, program_removed
