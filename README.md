# Clip Studio

Convierte un video largo en clips verticales listos para publicar. Descarga el
video, deja que Claude proponga los mejores momentos, los corta con ffmpeg, los
recorta al hablante y los renderiza con Remotion en el formato de cada red, con
capas de texto encima si las querés. Todo corre en tu máquina, en una interfaz
web local.

```
URL de YouTube (o un archivo tuyo)
  → yt-dlp baja el video + el transcript
  → Claude lee el transcript y propone los momentos   (o los marcás vos en la timeline)
  → elegís qué cortar y en qué formato, viendo el recorte sobre la foto del tramo
  → ffmpeg corta, pega los bordes al audio y normaliza a −14 LUFS
  → Remotion renderiza en 9:16 / 1:1 / 16:9 / split, siguiendo al que habla
  → Claude escribe los textos para TikTok, Instagram y YouTube Shorts
  → CSV con todo
```

> Este repositorio tiene **dos proyectos** que comparten entorno pero no código:
>
> | | Dónde | Qué es |
> |---|---|---|
> | **Clip Studio** | raíz (`app.py`, `modules/`, `components/`, `remotion/`) | Lo que describe este README. |
> | **Episodios** | [`episodios/`](episodios/) | Videos animados verticales sincronizados a una locución, uno por carpeta. Ver [`episodios/COMO-ENTREGAR.md`](episodios/COMO-ENTREGAR.md). |

---

## Requisitos

| | Versión | Para qué |
|---|---|---|
| **Python** | 3.11 o superior | La app y el pipeline |
| **Node.js + npm** | 18 o superior | Remotion (el render) |
| **ffmpeg** | cualquiera reciente, en el `PATH` | Cortar, medir y normalizar audio |
| **API key de Anthropic** | — | Elegir momentos y escribir los textos. **Opcional**: se puede usar Ollama local en su lugar. |

```bash
python --version     # 3.11+
node --version       # 18+
ffmpeg -version
```

Instalar ffmpeg:

```bash
winget install ffmpeg        # Windows
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian / Ubuntu
```

La API key se saca de [console.anthropic.com](https://console.anthropic.com).

---

## Instalación

```bash
git clone https://github.com/gerriarte/Video_clipping.git
cd Video_clipping

python -m venv .venv
# Windows:        .venv\Scripts\Activate.ps1
# Linux / macOS:  source .venv/bin/activate
pip install -r requirements.txt

cd remotion && npm install && cd ..
```

`npm install` baja Chromium y las dependencias de Remotion: la primera vez son
unos 300 MB.

**No hace falta compilar el frontend.** Los componentes React de la interfaz
(`components/clip_ui/`, `components/clip_editor/`) se versionan ya compilados;
Node solo es necesario para Remotion. Si vas a modificarlos, ver
[Desarrollo](#desarrollo).

---

## Arrancar

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`. En Windows también está `iniciar.bat`.

**La primera vez** te recibe la pantalla de configuración: los datos de tu canal
y con qué modelo querés trabajar.

- Los **datos del canal** (nombre, de qué trata, quiénes aparecen, tono) son lo
  que recibe el modelo para elegir los clips y escribir los textos. Cuanto más
  concretos, mejor salen. Se guardan en `settings.json`.
- La **API key** se guarda en `.env`, que está en `.gitignore`. Nunca entra en
  `settings.json` ni en el estado del pipeline, que son archivos que se copian y
  se comparten sin pensarlo.
- Si elegís **Ollama**, no hace falta ninguna key: corre en tu máquina, es
  gratis y privado, y es más lento.

Se vuelve a esa pantalla desde **⚙ Ajustes**, en la barra lateral.

Si preferís dejarlo configurado antes de abrirla, copiá `.env.example` a `.env`
y completá `ANTHROPIC_API_KEY`.

---

## Cómo se usa

### 1 · Fuente

Pegás una URL de YouTube, o elegís un archivo local de una lista: la app muestra
lo que hay en tu carpeta de material (configurable en Ajustes; por defecto
`downloads/`) con nombre, carpeta y peso. No es un formulario de subida a
propósito — el archivo ya está en tu disco.

Si el video no trae subtítulos, o los que trae cubren menos de la mitad,
transcribe con Whisper local (`faster-whisper`).

### 2 · Clips

Claude lee el transcript completo y propone momentos repartidos a lo largo del
video. Elegís cuántos (1–30) y el rango de duración.

**No depende de Claude:** con **✂ Timeline** se abre un editor visual —forma de
onda, transcript clicable, regiones arrastrables— donde marcás los cortes a
mano. Atajos: espacio reproduce, `I` y `O` marcan entrada y salida.

### 3 · Corte

Una grilla con una tarjeta por clip. En cada una:

- La **foto del tramo**, y **dibujado encima, el recorte que hace el formato**.
  Lo que queda afuera se apaga. Es la diferencia entre elegir mirando un nombre
  y elegir mirando lo que va a pasar.
- **La evidencia del análisis de la toma**: el tramo se muestrea cada ~3 s y se
  mide *cuánto tiempo* hay una o dos personas en cuadro — `1 persona el 92% del
  clip`, `2 personas en el 88%`, `cambia de plano`. El formato sugerido lleva ★,
  y se pueden aplicar todas de una.
- Título editable, timecodes, tipo, y los cinco formatos:

| Formato | Qué hace |
|---|---|
| **9:16** | Recorte vertical a pantalla completa, centrado en quien habla |
| **9:16 completo** | El 16:9 entero sobre negro, con barras: lienzo vertical sin perder nada |
| **1:1** | Recorte cuadrado centrado en el hablante |
| **16:9** | El plano original completo |
| **split** | Dos recortes apilados: un host arriba, otro abajo |

- **Sigue al hablante** — el recorte se desplaza para acompañar a quien habla.
- **Sigue la toma** — para los clips que alternan planos: el recorte cambia
  *dentro* del clip (split cuando están los dos, cerrado cuando la cámara va a
  uno). Las dimensiones nunca cambian: un mp4 no puede cambiar de aspecto a
  mitad de camino, lo que cambia es cómo se recorta el mismo lienzo.

Antes de cortar, dos decisiones sobre el audio:

- **Ajustar los bordes al audio** (por defecto sí) — los tiempos del transcript
  traen 1–2 s de error; esto pega el inicio y el fin a la pausa real más cercana
  para que el clip no arranque con media palabra.
- **Sacar silencios internos (jump cuts)** — elimina las pausas de más de 0,7 s
  y pega los trozos. Acelera el ritmo; en charlas pausadas puede sonar brusco.

El audio siempre se normaliza a **−14 LUFS**, que es el nivel de TikTok,
Instagram y Shorts.

### 4 · Render

La misma grilla, ahora con los clips ya cortados. Tocás una tarjeta y abajo
aparecen sus ajustes.

**Encuadre** — a quién recorta, y en split quién va arriba. Se previsualiza en
tres momentos del clip (arranque, medio, final), así ves si la persona se corre
antes de pagar un render entero.

**Capas** — texto encima del video. No alargan el clip ni obligan a volver a
cortar:

| Capa | Qué es |
|---|---|
| **Gancho** | Una frase grande al arranque (usa el título del clip si no escribís otra). Entra de golpe, subiendo, o escribiéndose sola. |
| **Placa de nombre** | Nombre y rol de quien habla, tomados de los hosts que cargaste en Ajustes. |
| **Apertura / Cierre** | Un título sobre los primeros o los últimos segundos. No tapan el video: lo oscurecen lo que le digas. |

**Ver cómo queda** renderiza un frame real con las capas puestas — la misma
composición que el render final. Si después cambiás algo, el preview queda
marcado como viejo en vez de mentir.

Las capas respetan las zonas que tapan las apps: se reserva el 18% de abajo y el
10% de arriba, donde TikTok, Reels y Shorts dibujan su propia interfaz.

Desde acá también se pueden **buscar más clips** en las zonas del video que
todavía no se usaron.

### 5 · Publicar

Lista de clips a la izquierda, el clip abierto a la derecha: el video
renderizado, su formato, y los textos para TikTok, Instagram y YouTube Shorts,
editables y con botón de copiar. Los cambios se guardan.

Al final, **⬇️ Descargar CSV** con todos los clips: tiempos, duración real,
rutas de archivo y los tres textos.

---

## Qué hay en el repositorio

```
app.py                     La interfaz (Streamlit)
config.py                  Rutas, modelo, formatos, parámetros de corte
pipeline.py                El mismo flujo por línea de comandos

modules/
  downloader.py            yt-dlp: video + transcript
  transcriber.py           Whisper local, cuando no hay subtítulos
  analyzer.py              Parseo del VTT y elección de momentos
  llm.py                   Anthropic u Ollama, detrás de una sola interfaz
  clipper.py               Corte con ffmpeg, bordes al audio, jump cuts
  audio_edit.py            Detección de silencios y normalización
  segment_preview.py       Análisis de la toma (cuántas personas, cuánto tiempo)
  layout_detector.py       Detección de caras para decidir el encuadre
  framing.py               Geometría del recorte
  renderer.py              Llama a Remotion; render en paralelo
  finish.py                Arte final del video (colorimetría, terminación)
  overlays.py              El modelo de las capas
  ui_state.py              Traducción entre los clips y las pantallas
  library.py               Qué material hay para trabajar
  settings.py              Configuración del usuario y manejo del .env
  imaging.py               Lectura de imágenes (ver la nota sobre acentos)
  media_server.py          Servidor HTTP local con Range, para el navegador
  peaks.py, proxy.py       Forma de onda y proxy 480p del editor

components/
  clip_ui/                 Las pantallas en React (galería y publicación)
  clip_editor/             El editor de timeline (wavesurfer.js)

remotion/                  El proyecto Remotion del render de clips
  src/ClipComposition.tsx  Recortes: fill / fit / letterbox / split
  src/overlays/            Gancho, placa de nombre, apertura y cierre

tests/                     186 tests (pytest)
docs/ROADMAP.md            Historia de decisiones y cómo se llegó acá
docs/DEPLOYMENT.md         Notas de despliegue
```

**Qué no está en el repositorio, a propósito:** este repo lleva el *proyecto*,
no el contenido. No se versionan las carpetas de trabajo (`downloads/`,
`clips/`, `output/`), ni la configuración de cada uno (`.env`, `settings.json`,
`.pipeline_state.json`), ni **el material de los episodios** — la locución, el
video y las fotos de referencia que van en `episodios/*/_entrada/`. Eso lo pone
quien hace el episodio; el texto (`brief.md`, `guion.md`, las composiciones de
referencia) sí se versiona, porque es la especificación y pesa nada.

---

## Configuración

Todo esto sale de variables de entorno o del `.env`. Los valores por defecto
están en `config.py`.

| Variable | Default | Qué hace |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Requerida si el proveedor es `anthropic` |
| `LLM_PROVIDER` | `anthropic` | `anthropic` u `ollama` |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Modelo de Claude |
| `OLLAMA_HOST` | `http://localhost:11434` | Servidor Ollama |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Modelo local |
| `RENDER_CONCURRENCY` | 2 (1 con menos de 8 núcleos) | Clips que se renderizan a la vez. Cada uno levanta su Chromium: bajala si te quedás sin memoria. |
| `SPEAKER_FOLLOW_DEFAULT` | `1` | Si el recorte sigue al hablante por defecto |
| `CLIP_STUDIO_MATERIAL_DIR` | `downloads/` | Dónde busca los videos locales (también en Ajustes) |
| `CLIP_STUDIO_OUTPUT_DIR` | `output/` | Dónde quedan los clips terminados (también en Ajustes) |
| `CLIP_STUDIO_DOWNLOADS_DIR` | `downloads/` | Dónde bajan los videos de YouTube |
| `CLIP_STUDIO_CLIPS_DIR` | `clips/` | Los cortes intermedios, antes de renderizar |
| `CLIP_STUDIO_STATE_FILE` | `.pipeline_state.json` | Útil para levantar una instancia de prueba sin pisar la que estás usando |
| `CLIP_STUDIO_SETTINGS_FILE` | `settings.json` | Ídem, para la configuración |
| `CLIP_STUDIO_ENV_FILE` | `.env` | Ídem, para las claves |

Las cuatro últimas se llamaban `ZUMO_*` y ese nombre se sigue aceptando: si lo
usás esperando apuntar a un archivo de prueba y te lo ignoráramos en silencio,
la app escribiría sobre el archivo real.

Parámetros que se editan en `config.py`: `TARGET_CLIPS` (10),
`MIN_CLIP_SECONDS` (15), `MAX_CLIP_SECONDS` (60), `FORMAT_PRESETS` (las
dimensiones de cada formato) y `MAX_OUTPUT_FPS` (60).

### Dónde queda cada cosa

Por defecto todo vive adentro de la carpeta del proyecto, lo cual es cómodo para
arrancar y un problema cuando crece: en un uso real esto junta decenas de GB de
video al lado del código.

| Carpeta | Qué guarda |
|---|---|
| `downloads/` | Los videos fuente completos |
| `clips/` | Los cortes intermedios de ffmpeg y las fotos del análisis |
| `output/<video>/` | **Lo que te llevás**: el clip renderizado, su portada y el CSV |

Las dos que importan —de dónde salen los videos y dónde quedan los terminados—
se cambian en **⚙ Ajustes** sin reiniciar. Las otras dos, con las variables de
entorno de la tabla de arriba. El Paso 5 muestra la ruta exacta de la carpeta
del episodio.

---

## Desarrollo

```bash
pytest -q                        # los 186 tests
cd remotion && npx tsc --noEmit  # typecheck del render
```

Para tocar las pantallas React:

```bash
cd components/clip_ui/frontend
npm install
npm run dev                      # servidor de Vite en :5174
# y poner _RELEASE = False en components/clip_ui/__init__.py
npm run build                    # el build se commitea
```

Para previsualizar en Remotion Studio (`cd remotion && npx remotion studio`)
dejá cualquier clip en `remotion/public/preview.mp4` — está gitignorado. Sin él
la composición abre en negro con una duración de muestra.

**Una trampa que ya costó cara:** las rutas de este proyecto salen del título
del video, o sea que casi siempre tienen acentos. `cv2.imread` en Windows no
abre esas rutas y devuelve `None` sin avisar. Usá `modules.imaging.imread`.

---

## Dependencias y licencias

### Python

| Paquete | Licencia |
|---|---|
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | MIT |
| [streamlit](https://streamlit.io) | Apache-2.0 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense |
| [curl_cffi](https://github.com/lexiforest/curl_cffi) | MIT |
| [requests](https://requests.readthedocs.io) | Apache-2.0 |
| [pandas](https://pandas.pydata.org) | BSD-3-Clause |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT |
| [opencv-python](https://github.com/opencv/opencv-python) | Apache-2.0 |
| [mediapipe](https://github.com/google-ai-edge/mediapipe) | Apache-2.0 |
| [numpy](https://numpy.org) | BSD-3-Clause |

### JavaScript

| Paquete | Licencia |
|---|---|
| [remotion](https://www.remotion.dev) y los `@remotion/*` del core | **Licencia propia — ver abajo** |
| `@remotion/layout-utils`, `@remotion/media-utils`, `@remotion/zod-types` | MIT |
| [react](https://react.dev) / react-dom | MIT |
| [vite](https://vite.dev) | MIT |
| [typescript](https://www.typescriptlang.org) | Apache-2.0 |
| [zod](https://zod.dev) | MIT |
| [wavesurfer.js](https://wavesurfer.xyz) | BSD-3-Clause |
| [streamlit-component-lib](https://github.com/streamlit/streamlit) | Apache-2.0 |

### Herramientas externas

| | Licencia |
|---|---|
| [ffmpeg](https://ffmpeg.org) | LGPL-2.1+ o GPL-2+ **según cómo esté compilado el binario que tengas instalado**. No se distribuye con este proyecto. |
| Chromium | BSD-3-Clause (lo baja Remotion) |

### ⚠️ Remotion no es MIT

Remotion tiene una **licencia de dos niveles**. Según sus términos, podés usarlo
gratis si sos:

- una persona,
- una organización con fines de lucro de **hasta 3 empleados**,
- una organización sin fines de lucro,
- o estás evaluando si te sirve.

Por encima de eso hace falta una **licencia de empresa paga**. Los términos
completos están en [remotion.dev/license](https://www.remotion.dev/docs/license)
y en `remotion/node_modules/remotion/LICENSE.md`.

Si tu organización supera ese umbral, esto te aplica: el render de clips no
funciona sin Remotion.

### Sobre el material que procesás

Los videos que produce esta herramienta salen de **material tuyo**. Descargar
videos de YouTube que no te pertenecen puede violar sus términos de servicio y
los derechos de quien los hizo. Tener los derechos sobre lo que se procesa es
responsabilidad de quien usa la herramienta.

Los textos los genera un modelo de Anthropic; se aplican sus
[términos de uso](https://www.anthropic.com/legal/consumer-terms).

---

## Licencia de este proyecto

**Todavía no tiene una.** Sin un archivo `LICENSE`, y aunque el repositorio sea
público, por defecto se reservan todos los derechos: nadie más puede usarlo,
copiarlo ni modificarlo legalmente.

Si querés que otros lo usen hay que elegir una y agregar el archivo. MIT y
Apache-2.0 son las opciones habituales para algo así; Apache-2.0 además incluye
una cláusula de patentes. Una aclaración que importa: **una licencia permisiva
sobre este código no cambia la de Remotion** — quien lo use va a seguir
necesitando la licencia de empresa si supera el umbral.

---

## Si algo falla

**"Falta la API key de Anthropic"**
Ponela en **⚙ Ajustes** dentro de la app, o en `.env`. Los scripts de línea de
comandos (`pipeline.py`) no tienen esa pantalla y fallan al arrancar si falta.

**yt-dlp devuelve 403 al bajar el video**
YouTube rota el cifrado de sus URLs y una versión vieja de yt-dlp deja de
firmarlas: `pip install -U yt-dlp`. Si el video baja pero dura 60 segundos no es
yt-dlp, es la IP, que está limitada — probá desde otra red o usá un archivo
local.

**Remotion falla con `[WinError 2]`**
En Windows `npx` no es un ejecutable directo. El proyecto ya usa `npx.cmd`;
verificá que Node esté instalado y en el `PATH`.

**El transcript viene vacío o muy corto**
El video no tiene subtítulos automáticos. La app lo detecta y ofrece transcribir
con Whisper local; la primera vez se baja el modelo.

**Se queda sin memoria al renderizar**
Cada render levanta su propio Chromium. Bajá `RENDER_CONCURRENCY` a 1.

**Remotion Studio se queda en "Running calculateMetadata()…"**
Falta `remotion/public/preview.mp4`. Poné cualquier clip ahí.

---

## Más

- **[docs/ROADMAP.md](docs/ROADMAP.md)** — cómo se llegó a cada decisión, qué se
  probó y no funcionó, y las mediciones detrás de cada cambio.
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — notas de despliegue.
