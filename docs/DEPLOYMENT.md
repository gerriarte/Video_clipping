# Despliegue — Fast Video Clipping

Guía para preparar un **despliegue rápido desde GitHub**. La app es pesada
(ffmpeg + Node/Remotion + Chromium headless + MediaPipe + Whisper), así que la
estrategia recomendada es **Docker sobre una VM**, no un PaaS de funciones.

> Estado: la app corre hoy en local (Windows/`iniciar.bat`, `streamlit run app.py`).
> Este documento deja el camino listo para contenerizarla; el `Dockerfile` y el
> `docker-compose.yml` de abajo son la referencia a crear cuando se decida desplegar.

---

## Por qué Docker en VM (y no Streamlit Cloud / PaaS de funciones)

- Necesita binarios de sistema: **ffmpeg**, **Node.js**, y las **libs de Chromium**
  que Remotion usa para renderizar. Streamlit Community Cloud no los provee de forma confiable.
- Los renders de Remotion y las transcripciones Whisper son **largos** (minutos):
  chocan con los timeouts de PaaS de funciones (Vercel/Render free, etc.).
- Genera **archivos grandes** (`downloads/`, `clips/`, `output/`): necesita disco
  persistente (volumen), no un filesystem efímero.

**Opciones válidas:** una VM (Hetzner / DigitalOcean / EC2) con `docker compose`, o
un PaaS que corra contenedores con disco y sin timeout agresivo (Fly.io, Railway).
Una VM con GPU es opcional (acelera Whisper/MediaPipe; no es obligatoria).

---

## Dependencias de sistema

| Dependencia | Para qué | Notas |
|---|---|---|
| Python 3.11+ | App Streamlit y pipeline | |
| Node.js 18+ / npm | Remotion (render) **y** build del componente `clip_editor` | Ya requerido por Remotion |
| ffmpeg | Cortar clips, extraer frames/peaks | En PATH |
| Libs de Chromium | Remotion headless | `libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1 libasound2 libpango-1.0-0 libcairo2 libxcomposite1 libxdamage1 libxrandr2 libxfixes3 libxkbcommon0` (ver guía Docker de Remotion) |
| libGL / libglib | MediaPipe / OpenCV | `libgl1 libglib2.0-0` |

---

## Variables de entorno

Todas se leen en `config.py`. Ver `.env.example` para la plantilla completa.

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `LLM_PROVIDER` | no | `anthropic` | `anthropic` (nube) u `ollama` (local) |
| `ANTHROPIC_API_KEY` | sí (si `anthropic`) | — | API key de Claude |
| `CLAUDE_MODEL` | no | `claude-sonnet-4-6` | Modelo de Claude |
| `OLLAMA_HOST` | no | `http://localhost:11434` | Solo si `LLM_PROVIDER=ollama` |
| `OLLAMA_MODEL` | no | `qwen2.5:14b` | Modelo local |
| `OLLAMA_TIMEOUT` | no | `600` | Segundos |
| `OLLAMA_TEMPERATURE` | no | `0.3` | Temperatura de extracción |
| `OLLAMA_NUM_CTX_ANALYZE` | no | `32768` | Ventana de contexto del análisis |
| `POSTIZ_API_URL` | no | `https://redes.abralatam.com/api/public/v1` | Base de la API de Postiz (self-hosted termina en `/api/public/v1`) |
| `POSTIZ_API_KEY` | no | — | Habilita el Paso 6 (programar publicaciones) |

---

## Build del componente custom `clip_editor` (Track 2)

El editor visual (ver `ROADMAP.md`) es un componente React que **debe compilarse**.
Para desplegar sin `npm install/build` en producción:

1. Compilar localmente: `cd components/clip_editor/frontend && npm ci && npm run build`.
2. **Commitear** `components/clip_editor/frontend/build/`.
3. `.gitignore` ya tiene la **negación** que evita que la regla global `build/` lo
   excluya (`!components/clip_editor/frontend/build/`). Verificar con
   `git status` que los assets se agregan.

Alternativa (imagen más grande, build reproducible): compilar el componente **dentro
del Dockerfile** en vez de commitear `build/`. Elegir una de las dos, no ambas.

---

## Dockerfile (referencia a crear)

```dockerfile
FROM python:3.11-slim

# Node.js 20 + ffmpeg + libs de Chromium/MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ffmpeg git \
      libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libgbm1 libasound2 \
      libpango-1.0-0 libcairo2 libxcomposite1 libxdamage1 libxrandr2 \
      libxfixes3 libxkbcommon0 libgl1 libglib2.0-0 \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y nodejs \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Deps de Remotion (descarga Chromium headless ~300 MB)
COPY remotion/package*.json remotion/
RUN cd remotion && npm ci

COPY . .

# Si NO se commiteó el build del componente, compilarlo acá:
# RUN cd components/clip_editor/frontend && npm ci && npm run build

EXPOSE 8501
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true"]
```

### docker-compose.yml (referencia)

```yaml
services:
  clipping:
    build: .
    ports:
      - "8501:8501"
    env_file: .env
    volumes:
      - media:/app/downloads
      - clips:/app/clips
      - output:/app/output
      - models:/app/models        # cache del modelo MediaPipe/Whisper
    restart: unless-stopped
volumes:
  media:
  clips:
  output:
  models:
```

---

## Puertos internos

- **8501** — Streamlit (exponer detrás de reverse proxy).
- **19876** — `_ClipServer` de Remotion (`renderer.py`), interno; no exponer.
- El server de media del editor (Track 2) usa el mismo patrón; asignar un puerto
  fijo y mantenerlo interno.

---

## Seguridad para deploy público

La app **no tiene autenticación**. Para exponerla:
- Ponerla detrás de un reverse proxy (Caddy/nginx) con **basic auth** o un túnel
  autenticado (Cloudflare Access, Tailscale).
- No commitear `.env` (ya está en `.gitignore`). Inyectar secretos por el entorno
  del host / gestor de secretos.

---

## Checklist pre-deploy

- [ ] `.env` completo en el host (no en git). `ANTHROPIC_API_KEY` presente si `LLM_PROVIDER=anthropic`.
- [ ] `Dockerfile` y `docker-compose.yml` creados a partir de esta referencia.
- [ ] Componente `clip_editor` compilado y `build/` commiteado (o build en Dockerfile).
- [ ] Volúmenes montados para `downloads/ clips/ output/ models/`.
- [ ] Reverse proxy + auth delante del 8501.
- [ ] `git status` limpio salvo lo que se quiere versionar (assets del componente sí, media generada no).
- [ ] Prueba: descargar un video corto → cortar → renderizar un formato → verificar dimensiones con `ffprobe`.

---

## Despliegue rápido (una vez contenerizado)

```bash
# En la VM
git clone https://github.com/gerriarte/Video_clipping.git
cd Video_clipping
cp .env.example .env    # y completar los valores
docker compose up -d --build
# actualizar:
git pull && docker compose up -d --build
```
