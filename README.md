# AI Control Center para Ubuntu

Panel web local para gestionar Ollama, Open WebUI, Immich y ComfyUI.

## Requisitos

- Ubuntu con Python 3 y `python3-venv`
- Docker CLI y permiso del usuario para ejecutar `docker`
- Ollama instalado como `ollama.service`
- Para métricas de CPU/RAM: se instala `psutil` dentro del entorno virtual
- Para métricas NVIDIA: `nvidia-smi` funcionando
- ComfyUI: por defecto se espera en `~/Documents/IA/IA_VIDEOS/ComfyUI`, con `main.py` y `venv/bin/python`

## Instalar

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
chmod +x install.sh
./install.sh
```

Abrir `http://127.0.0.1:8765`. El servicio del panel se activa al iniciar sesión en Ubuntu y se abre automáticamente en el navegador predeterminado.

El instalador configura una regla sudoers estricta que permite al panel únicamente `start`, `stop` y `restart` de `ollama.service`. No permite comandos arbitrarios. Si preferís no instalar esa regla, eliminá `/etc/sudoers.d/ai-control-center`; el panel seguirá mostrando el estado de Ollama, pero no podrá controlarlo.

## Docker

El usuario debe tener permiso para usar Docker. Comprobá con:

```bash
docker ps
```

Los nombres configurados por defecto son `open-webui` e `immich_server`. Si tus contenedores tienen otros nombres, editá el diccionario `SERVICES` en `app.py` y reinstalá copiando el archivo actualizado al directorio `~/.local/share/ai-control-center/`.

No se crean, eliminan ni modifican contenedores, imágenes, volúmenes ni datos.

## ComfyUI

Si existe `main.py` y `venv/bin/python` en la ruta esperada, el instalador crea `ai-comfyui.service` para el usuario. Revisá la ruta antes de iniciarlo. No se habilita automáticamente; se controla desde el panel y puede habilitarse con:

```bash
systemctl --user enable ai-comfyui.service
```

Si tu instalación usa `python_embeded`, Conda, otra ruta o argumentos extra, editá `~/.config/systemd/user/ai-comfyui.service`.

## Seguridad

- Flask escucha únicamente en `127.0.0.1`, no en la red local.
- Las acciones de servicio están limitadas a IDs y operaciones permitidos.
- No hay terminal web ni ejecución de comandos enviados por el navegador.
- Las acciones de detener/reiniciar pueden interrumpir sesiones activas.
- No se borran modelos ni datos.

## Diagnóstico

```bash
systemctl --user status ai-control-center
journalctl --user -u ai-control-center -f
systemctl status ollama
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
nvidia-smi
```

## Desinstalar

```bash
./uninstall.sh
```

El script desactiva los servicios de usuario del panel, pero deja los archivos y los datos intactos. Para quitar los permisos limitados de Ollama:

```bash
sudo rm -f /etc/sudoers.d/ai-control-center
```
