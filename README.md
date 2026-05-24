# Fast Video Clipping

Pipeline automatizado que descarga un video de YouTube, identifica los mejores momentos con Claude AI, corta los clips con ffmpeg, convierte a formato vertical 9:16 con Remotion y genera captions para TikTok, Instagram y YouTube Shorts — todo desde una interfaz web local.

---

## Demo del flujo

```
URL de YouTube
    → yt-dlp descarga el video + transcript VTT
    → Claude analiza el transcript y elige los mejores momentos
    → El usuario selecciona cuáles cortar y en qué formato
    → ffmpeg corta los clips
    → Remotion convierte a 9:16 (fondo borroso + letterbox)
    → Claude genera captions para cada plataforma
    → Descarga CSV con todos los datos
```

---

## Requisitos del sistema

### 1. Python 3.11+

Descargá desde [python.org](https://www.python.org/downloads/).  
Verificá con:
```bash
python --version
```

### 2. Node.js 18+ y npm

Necesario para Remotion (renderizado de video).  
Descargá desde [nodejs.org](https://nodejs.org/).  
Verificá con:
```bash
node --version
npm --version
```

### 3. ffmpeg

Necesario para cortar los clips del video fuente.

**Windows** (recomendado via Chocolatey o Winget):
```powershell
# Con Chocolatey
choco install ffmpeg

# Con Winget
winget install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

Verificá con:
```bash
ffmpeg -version
```

### 4. Clave API de Anthropic (Claude)

Creá una cuenta en [console.anthropic.com](https://console.anthropic.com) y generá una API key.

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/gerriarte/Video_clipping.git
cd Video_clipping
```

### 2. Configurar la API key

Copiá el archivo de ejemplo y completá tu clave:

```bash
# Linux / macOS
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Abrí `.env` y reemplazá el valor:
```
ANTHROPIC_API_KEY=sk-ant-api03-TU_CLAVE_AQUI
```

Alternativamente podés setear la variable de entorno directamente:
```bash
# Linux / macOS
export ANTHROPIC_API_KEY=sk-ant-api03-TU_CLAVE_AQUI

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-api03-TU_CLAVE_AQUI"
```

### 3. Instalar dependencias Python

```bash
# Crear entorno virtual (recomendado)
python -m venv .venv

# Activar
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Instalar paquetes
pip install -r requirements.txt
```

### 4. Instalar dependencias de Remotion

```bash
cd remotion
npm install
cd ..
```

Este paso descarga Chromium y las dependencias de Remotion (~300 MB la primera vez).

---

## Uso

### Iniciar la app

```bash
streamlit run app.py
```

Se abrirá automáticamente en `http://localhost:8501`.

### Flujo paso a paso

**Sidebar — Configuración del canal**  
Antes de empezar completá (o ajustá) los datos de tu canal: nombre, temática, hosts y tono. Esta info guía a Claude al seleccionar clips y escribir captions.

**Paso 1 — Descargar video**  
Pegá la URL de YouTube y hacé clic en "Descargar". El sistema descarga el video en la mejor calidad disponible y el transcript VTT (subtítulos automáticos de YouTube) que Claude usará para analizar el contenido.

> El video debe tener subtítulos automáticos habilitados en YouTube. Si no los tiene, la detección de momentos no funcionará con precisión de timestamps.

**Paso 2 — Analizar con Claude**  
Elegí cuántos clips querés (1–30) y el rango de duración (10–180 segundos). Claude lee el transcript completo del video, distribuye los clips a lo largo de todo el contenido y genera títulos precisos.

**Paso 3 — Seleccionar y cortar**  
Revisá la tabla de clips identificados. Podés:
- Marcar/desmarcar cuáles cortar
- Editar el título y los tiempos de inicio/fin
- Elegir el formato: **9:16 vertical** (con fondo borroso, ideal para TikTok/Reels/Shorts) o **Original 16:9**
- Seleccionar el tipo de contenido

Hacé clic en "Cortar clips con ffmpeg" para generar los archivos.

**Paso 4 — Preview y captions**  
Previsualizá cada clip y hacé clic en "Generar captions con Claude". Si hay clips en 9:16, Remotion los renderiza primero. Luego Claude genera captions optimizados para TikTok, Instagram y YouTube Shorts. Podés copiarlos directamente desde la interfaz.

**Descarga CSV**  
Al finalizar podés descargar un CSV con todos los clips, tiempos, paths de archivo y captions para cada plataforma.

---

## Estructura del proyecto

```
Video_clipping/
├── app.py                  # Interfaz Streamlit (UI principal)
├── config.py               # Configuración: rutas, modelo, parámetros de clip
├── requirements.txt        # Dependencias Python
├── .env.example            # Plantilla para la API key
│
├── modules/
│   ├── downloader.py       # Descarga video y VTT con yt-dlp
│   ├── analyzer.py         # Parsea VTT y llama a Claude para identificar clips
│   ├── clipper.py          # Corta clips con ffmpeg
│   ├── renderer.py         # Renderiza en 9:16 con Remotion
│   └── caption_gen.py      # Genera captions con Claude
│
└── remotion/               # Proyecto Remotion (TypeScript/React)
    ├── src/
    │   ├── index.ts        # Entry point
    │   ├── Root.tsx        # Registro de composiciones
    │   └── ClipComposition.tsx  # Componente: fondo borroso + letterbox 9:16
    ├── package.json
    └── tsconfig.json
```

### Carpetas generadas en runtime (en .gitignore)

```
downloads/    # Videos descargados de YouTube
clips/        # Clips cortados por ffmpeg
output/       # Clips renderizados en 9:16 por Remotion
```

---

## Configuración avanzada (`config.py`)

| Variable | Default | Descripción |
|---|---|---|
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Modelo de Claude a usar |
| `TARGET_CLIPS` | `10` | Cantidad de clips por defecto |
| `MIN_CLIP_SECONDS` | `15` | Duración mínima de clip |
| `MAX_CLIP_SECONDS` | `60` | Duración máxima de clip |
| `OUTPUT_WIDTH` | `1080` | Ancho del video 9:16 |
| `OUTPUT_HEIGHT` | `1920` | Alto del video 9:16 |
| `OUTPUT_FPS` | `30` | FPS del video de salida |

---

## Troubleshooting

**"Falta ANTHROPIC_API_KEY"**  
Verificá que el archivo `.env` existe en la raíz del proyecto y contiene tu clave correctamente.

**Remotion falla con `[WinError 2]`**  
En Windows, `npx` no es un ejecutable directo. El proyecto ya lo maneja usando `npx.cmd` automáticamente, pero asegurate de tener Node.js instalado y en el PATH.

**Chromium no puede cargar el video**  
El servidor HTTP interno corre en el puerto `19876`. Si ese puerto está ocupado, puede haber un error. Reiniciá la app para que se libere.

**El transcript VTT está vacío**  
El video de YouTube debe tener subtítulos automáticos habilitados. Videos muy recientes o con subtítulos solo manuales no funcionan. Probá con otro video.

**ffmpeg no encontrado**  
Asegurate de que ffmpeg esté en el PATH del sistema. Ejecutá `ffmpeg -version` en la terminal para verificar.

---

## Tecnologías

- [Streamlit](https://streamlit.io) — UI web local
- [Claude (Anthropic)](https://www.anthropic.com) — Análisis de contenido y generación de captions
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Descarga de video y transcript
- [ffmpeg](https://ffmpeg.org) — Corte de video
- [Remotion](https://www.remotion.dev) — Renderizado de video en React/TypeScript
