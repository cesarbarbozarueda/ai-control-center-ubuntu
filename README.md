# AI Control Center para Ubuntu

Panel local para administrar y actualizar tus IAs locales. Reconoce 19 (Ollama, Open WebUI, Immich, ComfyUI, LM Studio, Jan, GPT4All, LocalAI, AnythingLLM, Stable Diffusion WebUI y Forge, Fooocus, InvokeAI, text-generation-webui, SillyTavern, n8n, Flowise, LibreChat y Dify) y podés agregar cualquier otra. Se instala como paquete `.deb` o snap, aparece en el menú de aplicaciones y se abre en su propia ventana (con `ai-control-center --browser`, en el navegador, en `http://127.0.0.1:8765`).

Desarrollado por [devcibr](https://www.devcibr.com).

## Funciones

- **Detección automática** de cada IA: servicio del sistema, contenedor Docker, ejecutable en el PATH, carpeta (se busca en las rutas típicas y en tu carpeta personal) o app de escritorio (AppImage, Flatpak o .deb). Las que no se encuentran quedan en una lista plegable "No detectadas".
- **Agregar IA** (botón "＋ Agregar IA"): para cualquier IA que no esté en la lista, indicando su carpeta y el comando que la inicia, o su contenedor Docker, y el puerto opcional. Después se maneja igual que las demás.
- **Actualizar**, un botón por IA al lado de Iniciar/Detener, con ventana de progreso:
  - Ollama: instalador oficial (pide contraseña si está instalado en el sistema).
  - Docker: `pull` de la imagen y recreación del contenedor con la misma configuración (si falla, vuelve al anterior); con docker compose, `pull` + `up -d`.
  - Carpeta con git: `git pull` y reinstala dependencias (pip o npm).
  - Paquetes pip, npm y Flatpak con su propia herramienta.
  - AppImage o .deb: abre la página oficial para descargar la nueva versión.
- **Aviso "Actualización disponible"** en cada tarjeta: el panel revisa cada 6 horas (se puede desactivar en Configuración o revisar a mano).
- **Indicar ruta a mano** cuando no se detecta algo: carpeta, ejecutable o contenedor Docker, con puerto opcional.
- **Iniciar al iniciar sesión**, un interruptor por IA:
  - Servicio del sistema (Ollama oficial): `systemctl enable/disable`.
  - Docker: política de reinicio `unless-stopped` o `no`.
  - Carpeta o ejecutable: servicio de usuario `~/.config/systemd/user/ai-<id>.service`.
- **Desinstalar por completo**, con vista previa de lo que se borra. El programa se marca por defecto; los datos (modelos, volúmenes, imágenes generadas) solo si los marcás. Hay que escribir el nombre de la IA para confirmar.
- **Ventana propia** de escritorio (GTK + WebKit del sistema); si falta WebKit se abre en el navegador.
- **Tema claro u oscuro** con los dos cuadrados de arriba a la derecha (por defecto sigue al sistema).
- **Panel de configuración**: color de acento, tamaño de texto, bordes, densidad, columnas, fondo, animaciones, intervalo de actualización y abrir el panel al iniciar sesión.
- Métricas de CPU, RAM y GPU NVIDIA, globales y por servicio, y modelos de Ollama cargados en memoria.

## Compatibilidad

Ubuntu 20.04, 22.04, 24.04 y posteriores (y derivadas como Linux Mint 20+ o Pop!_OS). Usa el Python del sistema con `python3-flask` y `python3-psutil` de apt, sin entorno virtual. Ubuntu 18.04 o anterior no está soportado (Python demasiado viejo).

## Instalar

```bash
./install.sh
```

Construye `dist/ai-control-center_<versión>_all.deb`, lo instala con apt (pide tu contraseña) y abre el panel. Si tenías la versión anterior (servicio de usuario `ai-control-center`), la desactiva.

Para solo construir el paquete, por ejemplo para compartirlo:

```bash
packaging/build-deb.sh
sudo apt install ./dist/ai-control-center_2.0.0_all.deb
```

Para probar cambios: `./deploy.sh` reconstruye, reinstala, reinicia el panel y muestra el estado de la API.

## Publicar y compartir (.deb y snap / App Center)

Los pasos completos están en [docs/PUBLICAR.md](docs/PUBLICAR.md): construir los dos paquetes, subir el snap a la Snap Store para que aparezca en el App Center (necesita confinamiento `classic`, que aprueba Canonical), completar la ficha con las imágenes de `packaging/store/` y compartir el `.deb`.

## Permisos

- El panel solo escucha en `127.0.0.1` y cada acción requiere un token de la página, así que otros sitios web no pueden controlarlo.
- Para Ollama instalado como servicio del sistema, el paquete instala tres ayudantes con polkit:
  - `aicc-service-helper`: iniciar, detener y activar o desactivar `ollama.service`, sin contraseña para el usuario de la sesión.
  - `aicc-uninstall-helper`: desinstalar Ollama; siempre pide la contraseña de administrador.
  - `aicc-update-helper`: actualizar Ollama con su instalador oficial; siempre pide la contraseña de administrador.
  Solo aceptan esos valores fijos; no ejecutan comandos arbitrarios.
- Docker requiere que tu usuario esté en el grupo `docker` (`sudo usermod -aG docker $USER` y volver a iniciar sesión).

## Qué no se borra nunca

- Carpetas montadas en contenedores (por ejemplo, la biblioteca de fotos de Immich) ni la carpeta de docker compose.
- Archivos fuera de tu carpeta personal, salvo los de Ollama del sistema mediante el ayudante.
- Archivos que pertenecen a paquetes apt (se indica que los quites con apt).

## Archivos

- Configuración: `~/.config/ai-control-center/config.json`
- Registro del panel: `~/.cache/ai-control-center/server.log`
- Código instalado: `/usr/lib/ai-control-center/`

## Diagnóstico

```bash
ai-control-center --server          # correr el panel en primer plano para ver errores
systemctl --user status ai-comfyui  # servicios de usuario creados por el panel
systemctl status ollama
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

## Desinstalar el panel

```bash
./uninstall.sh
```

Quita la aplicación. Tus IAs, modelos y datos no se tocan.

## Donaciones

Si el proyecto te sirve, podés apoyarlo con el botón **♥ Donar** del panel (Binance Pay). El botón aparece solo si existe `static/donate-binance.png`; el Binance Pay ID opcional se configura en `DONATE` dentro de `app.py`.

## Licencia

Copyright © 2026 devcibr. AI Control Center es software libre: podés redistribuirlo y modificarlo bajo los términos de la Licencia Pública General GNU (GPL) versión 3 o, a tu elección, cualquier versión posterior. Se distribuye sin ninguna garantía. Ver [LICENSE](LICENSE).
