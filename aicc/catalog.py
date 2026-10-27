"""Known local AI tools and how to find, run, update and remove each one.

Each entry describes the ways a tool can be installed. Detection tries them in
the order of "detect" and stores the first match in the user's config.
Requests from the browser only ever reference these ids, never commands.

Detection methods:
  systemd      a system service (needs root to control)
  docker       a container, matched by name or image (compose projects included)
  binary       an executable in PATH or in binary_dirs, run with binary_command
  dir          a folder (named like dir_names, containing dir_markers), run with dir_command
  legacy_unit  a user unit written by the old install.sh
  app          a desktop app: AppImage, .deb, Flatpak or snap
Command placeholders: {bin} executable, {dir} folder, {python} its venv python, {port}.
"""

APPIMAGE_DIRS = ["~/Applications", "~/AppImages", "~/Apps", "~/Programs", "~/Downloads", "~/Descargas",
                 "~/.local/bin", "~/bin", "/opt"]

CATALOG = {
    "ollama": {
        "label": "Ollama",
        "icon": "◉",
        "description": "Motor de modelos locales",
        "port": 11434,
        "detect": ["systemd", "binary"],
        # System service installed by the official script (needs root to control).
        "systemd_units": ["ollama.service"],
        "binaries": ["ollama"],
        "binary_dirs": ["~/.local/bin", "/usr/local/bin", "/usr/bin"],
        # When there is no system service, the panel runs "ollama serve" as a user service.
        "binary_command": ["{bin}", "serve"],
        "binary_env": {"OLLAMA_HOST": "127.0.0.1:{port}"},
        "process_names": ["ollama"],
        "user_data": ["~/.ollama"],
        "manual_hint": "Ruta al ejecutable de ollama, por ejemplo /usr/local/bin/ollama",
    },
    "open-webui": {
        "label": "Open WebUI",
        "icon": "▦",
        "description": "Interfaz de chat para modelos locales",
        "port": 3000,
        "detect": ["docker", "binary"],
        "docker_names": ["open-webui"],
        "docker_images": ["open-webui/open-webui"],
        # pip / pipx installation
        "binaries": ["open-webui"],
        "binary_dirs": ["~/.local/bin"],
        "binary_command": ["{bin}", "serve", "--host", "127.0.0.1", "--port", "{port}"],
        "binary_port": 8080,
        "manual_hint": "Elegí el contenedor Docker o indicá la ruta del ejecutable open-webui",
    },
    "immich": {
        "label": "Immich",
        "icon": "▧",
        "description": "Servidor de fotos con IA",
        "port": 2283,
        "detect": ["docker"],
        "docker_names": ["immich_server"],
        "docker_images": ["immich-app/immich-server", "immich-server"],
        "manual_hint": "Elegí el contenedor principal de Immich (immich_server)",
    },
    "comfyui": {
        "label": "ComfyUI",
        "icon": "✧",
        "description": "Generación de imágenes y video",
        "port": 8188,
        "detect": ["legacy_unit", "dir"],
        "legacy_units": ["ai-comfyui.service"],
        "dir_markers": ["main.py", "comfy"],
        "dir_names": ["ComfyUI"],
        "dir_search": [
            "~/ComfyUI", "~/comfy/ComfyUI", "~/Documents/ComfyUI", "~/Documentos/ComfyUI",
            "~/Documents/IA/IA_VIDEOS/ComfyUI", "~/AI/ComfyUI", "~/IA/ComfyUI",
            "~/.local/share/ComfyUI", "/opt/ComfyUI",
        ],
        "dir_command": ["{python}", "main.py", "--listen", "127.0.0.1", "--port", "{port}"],
        "cmdline_match": ["main.py"],
        # Folders kept unless the user also chooses to remove data.
        "dir_data": ["models", "output", "input", "user"],
        "manual_hint": "Carpeta de ComfyUI (la que contiene main.py)",
    },
    # ----- web UIs run from a folder -----
    "text-generation-webui": {
        "label": "Text Generation WebUI",
        "icon": "✎",
        "description": "Chat con modelos locales (oobabooga)",
        "port": 7860,
        "detect": ["dir"],
        "dir_markers": ["server.py", "modules"],
        "dir_names": ["text-generation-webui"],
        "dir_command": ["{python}", "server.py", "--listen-port", "{port}"],
        # The one-click installer keeps its own environment; its script knows how to use it.
        "dir_command_if": {"start_linux.sh": ["/bin/bash", "start_linux.sh", "--listen-port", "{port}"]},
        "cmdline_match": ["server.py"],
        "dir_data": ["models", "loras", "characters", "user_data"],
        "manual_hint": "Carpeta text-generation-webui (la que contiene server.py)",
    },
    "sd-webui": {
        "label": "Stable Diffusion WebUI",
        "icon": "◐",
        "description": "Generación de imágenes (AUTOMATIC1111)",
        "port": 7860,
        "detect": ["dir"],
        "dir_markers": ["webui.py", "webui.sh", "modules"],
        "dir_names": ["stable-diffusion-webui"],
        "dir_command": ["/bin/bash", "webui.sh", "--port", "{port}"],
        "cmdline_match": ["launch.py"],
        "dir_data": ["models", "outputs", "embeddings", "extensions"],
        "manual_hint": "Carpeta stable-diffusion-webui (la que contiene webui.sh)",
    },
    "sd-forge": {
        "label": "SD WebUI Forge",
        "icon": "◓",
        "description": "Generación de imágenes (Forge)",
        "port": 7861,
        "detect": ["dir"],
        "dir_markers": ["webui.py", "webui.sh", "modules"],
        "dir_names": ["stable-diffusion-webui-forge", "sd-webui-forge"],
        "dir_command": ["/bin/bash", "webui.sh", "--port", "{port}"],
        "cmdline_match": ["launch.py"],
        "dir_data": ["models", "outputs", "embeddings", "extensions"],
        "manual_hint": "Carpeta stable-diffusion-webui-forge (la que contiene webui.sh)",
    },
    "fooocus": {
        "label": "Fooocus",
        "icon": "❀",
        "description": "Generación de imágenes simple",
        "port": 7865,
        "detect": ["dir"],
        "dir_markers": ["entry_with_update.py", "launch.py"],
        "dir_names": ["Fooocus"],
        "dir_command": ["{python}", "entry_with_update.py", "--listen", "127.0.0.1", "--port", "{port}"],
        "cmdline_match": ["entry_with_update.py"],
        "pip_requirements": "requirements_versions.txt",
        "dir_data": ["models", "outputs"],
        "manual_hint": "Carpeta de Fooocus (la que contiene entry_with_update.py)",
    },
    "invokeai": {
        "label": "InvokeAI",
        "icon": "✺",
        "description": "Estudio de generación de imágenes · puerto según invokeai.yaml",
        "port": 9090,
        "detect": ["dir"],
        "dir_markers": [".venv/bin/invokeai-web"],
        "dir_names": ["invokeai"],
        "dir_command": ["{dir}/.venv/bin/invokeai-web", "--root", "{dir}"],
        "cmdline_match": ["invokeai-web"],
        "update_pip_package": "invokeai",
        "dir_data": ["models", "outputs", "databases"],
        "manual_hint": "Carpeta raíz de InvokeAI (la que contiene .venv e invokeai.yaml)",
    },
    "sillytavern": {
        "label": "SillyTavern",
        "icon": "♞",
        "description": "Interfaz de chat y rol para LLMs",
        "port": 8000,
        "detect": ["dir"],
        "dir_markers": ["server.js", "package.json"],
        "dir_names": ["SillyTavern"],
        # Login shell so a Node installed with nvm is found.
        "dir_command": ["/bin/bash", "-lc", "exec node server.js --port {port}"],
        "cmdline_match": ["server.js"],
        "update_npm": True,
        "dir_data": ["data"],
        "manual_hint": "Carpeta de SillyTavern (la que contiene server.js)",
    },
    # ----- servers usually run with Docker -----
    "localai": {
        "label": "LocalAI",
        "icon": "◆",
        "description": "API compatible con OpenAI, local",
        "port": 8080,
        "detect": ["docker", "binary"],
        "docker_names": ["local-ai", "localai"],
        "docker_images": ["localai/localai", "go-skynet/local-ai", "mudler/localai"],
        "binaries": ["local-ai"],
        "binary_command": ["{bin}", "run", "--address", "127.0.0.1:{port}"],
        "process_names": ["local-ai"],
        "manual_hint": "Elegí el contenedor o indicá la ruta del ejecutable local-ai",
    },
    "anythingllm": {
        "label": "AnythingLLM",
        "icon": "▣",
        "description": "Chat con tus documentos (RAG)",
        "port": 3001,
        "detect": ["docker", "app"],
        "docker_names": ["anythingllm"],
        "docker_images": ["mintplexlabs/anythingllm"],
        "appimage_globs": ["AnythingLLMDesktop*.AppImage", "AnythingLLM*.AppImage"],
        "app_paths": ["~/AnythingLLMDesktop/anythingllm-desktop/anythingllm-desktop"],
        "process_names": ["anythingllm-desktop", "anythingllm"],
        "user_data": ["~/.config/anythingllm-desktop"],
        "homepage": "https://anythingllm.com",
        "manual_hint": "Elegí el contenedor o indicá la ruta del AppImage",
    },
    "flowise": {
        "label": "Flowise",
        "icon": "⧉",
        "description": "Flujos de agentes con LLMs",
        "port": 3000,
        "detect": ["docker", "binary"],
        "docker_names": ["flowise"],
        "docker_images": ["flowiseai/flowise"],
        "binaries": ["flowise"],
        "binary_command": ["{bin}", "start"],
        "binary_env": {"PORT": "{port}"},
        "process_names": ["flowise"],
        "manual_hint": "Elegí el contenedor o indicá la ruta del ejecutable flowise",
    },
    "n8n": {
        "label": "n8n",
        "icon": "⟲",
        "description": "Automatizaciones con IA",
        "port": 5678,
        "detect": ["docker", "binary"],
        "docker_names": ["n8n"],
        "docker_images": ["n8nio/n8n"],
        "binaries": ["n8n"],
        "binary_command": ["{bin}", "start"],
        "binary_env": {"N8N_PORT": "{port}"},
        "user_data": ["~/.n8n"],
        "manual_hint": "Elegí el contenedor o indicá la ruta del ejecutable n8n",
    },
    "librechat": {
        "label": "LibreChat",
        "icon": "✉",
        "description": "Interfaz de chat multi-modelo",
        "port": 3080,
        "detect": ["docker"],
        "docker_names": ["LibreChat", "librechat"],
        "docker_images": ["danny-avila/librechat", "librechat/librechat"],
        "manual_hint": "Elegí el contenedor principal de LibreChat",
    },
    "dify": {
        "label": "Dify",
        "icon": "⬡",
        "description": "Plataforma de apps con LLMs",
        "port": 80,
        "detect": ["docker"],
        "docker_names": ["docker-web-1", "dify-web"],
        "docker_images": ["langgenius/dify-web"],
        "manual_hint": "Elegí el contenedor web de Dify",
    },
    # ----- desktop apps -----
    "lm-studio": {
        "label": "LM Studio",
        "icon": "◎",
        "description": "App de escritorio para modelos locales · API en puerto 1234",
        "port": 1234,
        "web": False,
        "detect": ["app"],
        "appimage_globs": ["LM-Studio*.AppImage", "LM_Studio*.AppImage", "LMStudio*.AppImage"],
        "app_paths": ["/opt/LM Studio/lm-studio", "/opt/lm-studio/lm-studio", "/usr/bin/lm-studio"],
        "process_names": ["lm-studio", "LM Studio"],
        "user_data": ["~/.lmstudio", "~/.config/LM Studio"],
        "homepage": "https://lmstudio.ai",
        "manual_hint": "Ruta del AppImage o del ejecutable de LM Studio",
    },
    "jan": {
        "label": "Jan",
        "icon": "◑",
        "description": "App de escritorio para modelos locales · API en puerto 1337",
        "port": 1337,
        "web": False,
        "detect": ["app"],
        "appimage_globs": ["jan-linux*.AppImage", "Jan_*.AppImage", "jan_*.AppImage", "Jan-*.AppImage"],
        "app_paths": ["/usr/bin/jan", "/opt/Jan/jan"],
        "flatpak_ids": ["ai.jan.Jan"],
        "process_names": ["jan", "Jan"],
        "user_data": ["~/.config/Jan", "~/.local/share/Jan", "~/jan"],
        "homepage": "https://jan.ai",
        "manual_hint": "Ruta del AppImage o del ejecutable de Jan",
    },
    "gpt4all": {
        "label": "GPT4All",
        "icon": "◒",
        "description": "App de escritorio para modelos locales · API en puerto 4891",
        "port": 4891,
        "web": False,
        "detect": ["app"],
        "app_paths": ["~/gpt4all/bin/chat", "/opt/gpt4all/bin/chat"],
        "flatpak_ids": ["io.gpt4all.gpt4all"],
        "process_names": ["chat", "gpt4all"],
        "process_path_match": "gpt4all",
        "user_data": ["~/.local/share/nomic.ai", "~/.config/nomic.ai"],
        "homepage": "https://gpt4all.io",
        "manual_hint": "Ruta del ejecutable de GPT4All (por ejemplo ~/gpt4all/bin/chat)",
    },
}

ORDER = list(CATALOG.keys())
BUILTIN = set(ORDER)


def register_custom(customs):
    """Add the user's own AI tools (from config) to the catalog, replacing older ones."""
    for sid in [s for s in ORDER if s not in BUILTIN]:
        ORDER.remove(sid)
        CATALOG.pop(sid, None)
    for sid, c in (customs or {}).items():
        CATALOG[sid] = {
            "label": c.get("label", sid), "icon": "◇", "description": c.get("description") or "IA personalizada",
            "port": c.get("port") or 0, "detect": [], "custom": True,
            "dir_command": ["/bin/bash", "-lc", c.get("command", "")],
            "manual_hint": "IA agregada a mano",
        }
        ORDER.append(sid)
