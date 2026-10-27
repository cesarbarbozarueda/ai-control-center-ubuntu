# Cómo publicar y compartir AI Control Center

Hay dos paquetes:

| | `.deb` | snap |
|---|---|---|
| Qué es | El formato clásico de Ubuntu/Debian | Paquete autocontenido de Canonical |
| Tamaño | ~40 KB (usa el Python del sistema) | ~30-40 MB (trae su propio Python) |
| Actualizaciones | Manuales (o con un repositorio apt propio) | Automáticas desde la Snap Store |
| App Center | Se instala con doble clic, pero **no aparece en la tienda** | **Aparece en el App Center** |
| Dónde se comparte | Tu web, GitHub Releases | snapcraft.io / App Center |

Las imágenes para las tiendas están en `packaging/store/`:

- `icon-512.png`: ícono (también `icon-256.png` y `icon-128.png`).
- `banner-1218x406.png`: banner de la ficha de la Snap Store.
- `screenshot-0` a `screenshot-4`: capturas de 1366×768.

---

## 1. El paquete .deb

### Construirlo

```bash
bash packaging/build-deb.sh
# genera dist/ai-control-center_2.0.0_all.deb
```

En el campo "Maintainer" aparece `devcibr <tu email de git>`. Para usar otro:

```bash
MAINTAINER="devcibr <contacto@devcibr.com>" bash packaging/build-deb.sh
```

### Probarlo

```bash
sudo apt install ./dist/ai-control-center_2.0.0_all.deb
ai-control-center            # abre la ventana
ai-control-center --browser  # o en el navegador
```

### Compartirlo

1. **GitHub Releases** (recomendado). Con la CLI de GitHub:
   ```bash
   gh release create v2.0.0 dist/ai-control-center_2.0.0_all.deb \
     --title "AI Control Center 2.0.0" --notes "Ventana propia, detección de IAs, inicio automático por IA..."
   ```
   El link de descarga queda en `https://github.com/cesarbarbozarueda/ai-control-center-ubuntu/releases`.
2. **Tu web** (www.devcibr.com). Subí el `.deb` y poné un botón "Descargar para Ubuntu (.deb)".
3. Quien lo descargue lo instala con doble clic, que lo abre en el App Center o en el instalador de paquetes, o con:
   ```bash
   sudo apt install ./ai-control-center_2.0.0_all.deb
   ```

Las capturas de la ficha (`packaging/com.devcibr.AIControlCenter.metainfo.xml`) se leen de GitHub. Para que se vean, el repositorio tiene que ser público y `packaging/store/` tiene que estar subido a `main`.

---

## 2. El snap (App Center)

### 2.1 Preparar la máquina (una sola vez)

```bash
sudo snap install snapcraft --classic
sudo snap install lxd
sudo lxd init --auto
sudo usermod -aG lxd $USER   # después cerrá sesión y volvé a entrar
```

### 2.2 Construirlo

Desde la carpeta del repo:

```bash
snapcraft
# genera ai-control-center_2.0.0_amd64.snap
```

Si falla, mandame el error completo. El `snapcraft.yaml` no se pudo compilar en mi entorno de prueba.

### 2.3 Probarlo antes de subirlo

```bash
sudo snap install --dangerous --classic ./ai-control-center_2.0.0_amd64.snap
ai-control-center
```

### 2.4 Crear la cuenta y reservar el nombre

1. Creá una cuenta en https://snapcraft.io (usa Ubuntu One).
2. En la terminal:
   ```bash
   snapcraft login
   snapcraft register ai-control-center
   ```
   Si el nombre está tomado, cambiá `name:` en `snap/snapcraft.yaml` (por ejemplo `devcibr-ai-control-center`) y registrá ese.

### 2.5 Pedir confinamiento "classic" (obligatorio)

El panel necesita controlar systemd, Docker y carpetas de tu home, algo que el confinamiento estricto no permite. Por eso usa `classic`, que Canonical aprueba a mano.

1. Entrá a https://forum.snapcraft.io y creá un tema en la categoría **store-requests**.
2. Título: `Classic confinement request: ai-control-center`
3. Texto sugerido:
   > AI Control Center is a desktop panel to manage and update local AI tools (Ollama, Open WebUI, ComfyUI, LM Studio, Jan, SillyTavern, n8n and others, plus user-defined ones). It needs classic confinement because it:
   > - starts/stops and enables/disables systemd system and user units (e.g. ollama.service, ~/.config/systemd/user/*.service),
   > - runs the host `docker` CLI to start/stop containers and change their restart policy,
   > - reads and removes AI tool folders anywhere in the user's home when the user asks to uninstall them,
   > - updates those tools with the host's own tools when the user clicks Update (`docker pull`/`docker compose`, `git pull` + pip/npm in the tool's folder, `flatpak update`, the official Ollama installer via pkexec),
   > - starts desktop AI apps (AppImage, Flatpak, .deb) and writes XDG autostart entries.
   > There are no snapd interfaces that cover managing arbitrary systemd units or the host Docker daemon.
   > Source: https://github.com/cesarbarbozarueda/ai-control-center-ubuntu · Website: https://www.devcibr.com
4. Suelen responder en unos días. Mientras tanto podés subir el snap; queda en revisión.

### 2.6 Subirlo

```bash
snapcraft upload --release=edge ai-control-center_2.0.0_amd64.snap
```

Cuando esté aprobado y probado, pasalo a estable (el número de revisión sale en `snapcraft status ai-control-center`):

```bash
snapcraft release ai-control-center <revisión> stable
```

### 2.7 Completar la ficha de la tienda

En https://snapcraft.io/ai-control-center/listing:

- **Icono**: `packaging/store/icon-512.png`
- **Capturas** (hasta 5): `packaging/store/screenshot-*.png`
- **Banner**: `packaging/store/banner-1218x406.png`
- **Título, resumen y descripción**: se toman de `snap/snapcraft.yaml` (español primero y abajo inglés).
- **Sitio web y contacto**: https://www.devcibr.com
- **Categorías**: Utilities y Development
- **Licencia**: GPL-3.0-or-later (ya está en `snapcraft.yaml` y en el metainfo; el texto completo está en `LICENSE`).

Cuando está en `stable`, aparece en el **App Center** de Ubuntu al buscar "AI Control Center". Puede tardar algunas horas.

### 2.8 Compartir el snap

- Link: https://snapcraft.io/ai-control-center
- Instalación por terminal: `sudo snap install ai-control-center --classic`
- Botón para tu web: en https://snapcraft.io/ai-control-center/publicise hay badges "Get it from the Snap Store" listos para copiar.

### ARM (opcional)

Para equipos ARM64 (por ejemplo Raspberry Pi):

```bash
snapcraft remote-build --build-for=arm64
```

---

## 3. Sacar una versión nueva

1. Cambiá la versión en `app.py` (`VERSION = "2.0.1"`) y en `snap/snapcraft.yaml` (`version:`).
2. Agregá un `<release>` en `packaging/com.devcibr.AIControlCenter.metainfo.xml`.
3. `.deb`: `bash packaging/build-deb.sh` y subilo a un nuevo Release.
4. snap: `snapcraft`, `snapcraft upload --release=stable ai-control-center_2.0.1_amd64.snap`. Los usuarios lo reciben solo.
