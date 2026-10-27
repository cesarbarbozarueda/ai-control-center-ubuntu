"""Small helpers shared by the AI Control Center modules.

Compatible with Python 3.8+ (Ubuntu 20.04 and newer).
"""
import os
import shutil
import socket
import subprocess
from pathlib import Path

HOME = Path.home()


def run(args, timeout=5, env=None, cwd=None):
    """Run a command without a shell and return a small result dict."""
    try:
        full_env = None
        if env:
            full_env = dict(os.environ)
            full_env.update(env)
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           check=False, env=full_env, cwd=cwd)
        return {"ok": p.returncode == 0, "out": p.stdout.strip(), "err": p.stderr.strip(), "code": p.returncode}
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "out": "", "err": str(e), "code": -1}


def port_open(port, host="127.0.0.1", timeout=0.3):
    if not port:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def expand(path):
    return Path(os.path.expandvars(os.path.expanduser(str(path))))


def find_executable(names, extra_dirs=()):
    """Return the first executable found in PATH or in extra_dirs."""
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for d in extra_dirs:
        for name in names:
            p = expand(d) / name
            if p.is_file() and os.access(str(p), os.X_OK):
                return str(p)
    return None


def is_under(path, root):
    """True if path is strictly inside root (Path.is_relative_to needs 3.9)."""
    try:
        path = Path(path).resolve()
        root = Path(root).resolve()
    except OSError:
        return False
    return path != root and root in path.parents


def safe_rmtree(path, allowed_root=HOME):
    """Delete a file or directory, but only if it lives inside allowed_root."""
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return True, "ya no existe"
    if not is_under(path, allowed_root):
        return False, "ruta fuera de la carpeta permitida, no se borra por seguridad"
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(str(path))
        else:
            path.unlink()
        return True, "borrado"
    except OSError as e:
        return False, str(e)


def dir_size_mb(path, limit_files=200000):
    """Approximate size of a folder in MB, with a file limit to stay fast."""
    total = 0
    count = 0
    try:
        for root, _dirs, files in os.walk(str(path)):
            for f in files:
                count += 1
                if count > limit_files:
                    return None
                try:
                    total += os.lstat(os.path.join(root, f)).st_size
                except OSError:
                    pass
    except OSError:
        return None
    return round(total / 1048576)
