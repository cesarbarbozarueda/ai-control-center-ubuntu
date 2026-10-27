"""CPU, RAM and GPU readings for the whole computer and for each service."""
import re
import shutil
import time

from .util import run

EMPTY = {"cpu_percent": None, "ram_mb": None, "ram_percent": None, "ram_total_mb": None, "available": False}


def system_metrics():
    result = {"cpu_percent": None, "ram_total_mb": None, "ram_used_mb": None,
              "ram_percent": None, "gpu": None, "gpu_error": None}
    try:
        import psutil
        vm = psutil.virtual_memory()
        result.update(cpu_percent=psutil.cpu_percent(interval=0.15),
                      ram_total_mb=round(vm.total / 1048576),
                      ram_used_mb=round((vm.total - vm.available) / 1048576),
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


def process_metrics(process_names=None, cmdline_contains=None, cwd=None):
    """CPU/RAM of matching host processes. CPU is normalized to whole-machine capacity."""
    try:
        import psutil
        matches = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                info = proc.info
                name = (info.get("name") or "").lower()
                cmdline = " ".join(info.get("cmdline") or []).lower()
                name_match = process_names and any(n.lower() in name for n in process_names)
                cmd_match = cmdline_contains and all(n.lower() in cmdline for n in cmdline_contains)
                if cmd_match and cwd and cwd.lower() not in cmdline:
                    # e.g. "python main.py" started inside the ComfyUI folder
                    try:
                        cmd_match = proc.cwd() == cwd
                    except (psutil.AccessDenied, OSError):
                        cmd_match = False
                if name_match or cmd_match:
                    matches.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        # prime CPU counters then read again after a short interval
        for proc in matches:
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(0.12)
        cpu = 0.0
        ram = 0
        for proc in matches:
            try:
                cpu += proc.cpu_percent(interval=None)
                ram += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        total_ram = psutil.virtual_memory().total
        # psutil process CPU can exceed 100 on multi-core systems; express as share of total host capacity.
        cpu = cpu / max(1, psutil.cpu_count() or 1)
        return {"cpu_percent": round(max(0.0, cpu), 1), "ram_mb": round(ram / 1048576),
                "ram_percent": round((ram / total_ram) * 100, 1) if total_ram else None,
                "ram_total_mb": round(total_ram / 1048576), "available": bool(matches)}
    except Exception:
        return dict(EMPTY)


def _to_mb(value):
    value = value.strip().upper().replace(",", ".")
    match = re.match(r"^([0-9.]+)\s*([KMGTP]?I?B)?$", value)
    if not match:
        return None
    factors = {"B": 1 / 1048576, "KB": 1 / 1024, "KIB": 1 / 1024, "MB": 1, "MIB": 1,
               "GB": 1024, "GIB": 1024, "TB": 1048576, "TIB": 1048576}
    return float(match.group(1)) * factors.get((match.group(2) or "B").upper(), 1)


def docker_metrics(containers):
    """Sum CPU and memory of a group of containers from Docker's own statistics."""
    if not containers or not shutil.which("docker"):
        return dict(EMPTY)
    r = run(["docker", "stats", "--no-stream", "--format",
             "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"] + list(containers), timeout=8)
    if not r["out"]:
        return dict(EMPTY)
    cpu = used = mem_pct = 0.0
    limit = None
    try:
        for line in r["out"].splitlines():
            parts = line.split("|")
            cpu += float(parts[0].strip().rstrip("%"))
            mem_pct += float(parts[2].strip().rstrip("%"))
            usage = parts[1].split("/")
            used += _to_mb(usage[0]) or 0
            if len(usage) > 1:
                limit = _to_mb(usage[1])
    except (ValueError, IndexError):
        return dict(EMPTY)
    return {"cpu_percent": round(max(0.0, cpu), 1), "ram_mb": round(used),
            "ram_percent": round(max(0.0, mem_pct), 1),
            "ram_total_mb": round(limit) if limit else None, "available": True}


def pids_metrics(procs):
    """CPU/RAM of an already-found list of psutil processes."""
    try:
        import psutil
        for p in procs:
            try:
                p.cpu_percent(interval=None)
            except psutil.Error:
                pass
        time.sleep(0.12)
        cpu, ram = 0.0, 0
        for p in procs:
            try:
                cpu += p.cpu_percent(interval=None)
                ram += p.memory_info().rss
            except psutil.Error:
                continue
        total = psutil.virtual_memory().total
        return {"cpu_percent": round(cpu / max(1, psutil.cpu_count() or 1), 1), "ram_mb": round(ram / 1048576),
                "ram_percent": round(ram / total * 100, 1) if total else None,
                "ram_total_mb": round(total / 1048576), "available": True}
    except Exception:
        return dict(EMPTY)
