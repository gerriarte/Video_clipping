# Roadmap — Clip Studio

Plan de evolución acordado para la app. Dos tracks independientes entre sí; se
pueden construir en cualquier orden o en paralelo. Nada de esto está implementado
todavía — este documento es la especificación de referencia.

> Contexto de la decisión: los **subtítulos quemados** se **descartan** del render.
> Se agregan desde las apps de redes (TikTok/IG/YT). El foco es la **calidad y
> lo visual** del video, y **quitar la dependencia de Claude** para poder avanzar
> a mano si el análisis no rinde.

---

## Track 1 — Formato manual por clip + calidad visual   ✅ IMPLEMENTADO (2026-07-17)

> Estado: implementado y verificado end-to-end (los 4 formatos renderizan con
> dimensiones correctas: 1080×1920 / 1080×1080 / 1920×1080 / split 1080×1920).
> Subtítulos quemados quitados del render. Pendiente opcional: Fase 2 del split
> (sliders manuales de foco por mitad).

Elegir, **por clip y desde la UI**, el formato final de salida, reemplazando la
decisión automática anterior.

### Formatos objetivo

| Formato | Dimensiones | Layout Remotion | Encuadre |
|---|---|---|---|
| `9:16` | 1080×1920 | `fill` / `fit` (auto) | Recorte que sigue al hablante, o plano 16:9 sobre fondo borroso |
| `1:1`  | 1080×1080 | `fill` / `fit` (auto) | Recorte cuadrado centrado en el hablante |
| `16:9` | 1920×1080 | `fill` (fijo)         | Plano completo (fuente ya es 16:9) |
| `split`| 1080×1920 | `split` (**nuevo**)   | Dos recortes apilados, un host arriba y otro abajo |

**Hallazgo que simplifica:** `1:1` y `16:9` reutilizan los layouts existentes
(`fill`/`fit`); el **único layout nuevo** en Remotion es `split`.

### Encuadre del `split`
- **Fase 1 (ahora):** automático. Reutiliza el clustering de caras que ya
  calcula `layout_detector` (`_cluster_by_x`) para asignar host-izquierdo→arriba,
  host-derecho→abajo, con foco estático por mitad.
- **Fase 2 (después):** sliders manuales de foco arriba/abajo por clip. Se deja
  el *hook* preparado en Fase 1 para no reescribir.

### Cambios por archivo

| Archivo | Cambio |
|---|---|
| `config.py` | `FORMAT_PRESETS` (dims + layout + `auto_layout` por formato) y `DEFAULT_FORMAT`. Se conservan `OUTPUT_*` como default 9:16 para no romper otros consumidores. |
| `remotion/src/ClipComposition.tsx` | **Quitar `SubtitleLayer`** y el prop `subtitles`/`leadPad`. Agregar layout `split` (dos `OffthreadVideo` en mitades con `objectPosition` propio). `fill`/`fit` quedan igual. |
| `remotion/src/Root.tsx` | Sacar `subtitles`/`leadPad` de `defaultProps`. |
| `modules/layout_detector.py` | `detect_split()` → centros de los 2 hosts. Parametrizar `_CROP_VISIBLE_FRAC` **por aspecto** (hoy fijo a 9:16) para centrar bien en 1:1 y en cada mitad del split. |
| `modules/renderer.py` | `render_clip`/`render_cover` derivan `width/height/layout` del preset (no de `config.OUTPUT_*`). Sin subtítulos. Branch por `clip["formato"]`. |
| `app.py` | Selectbox "Formato" con 4 opciones; **todos** los formatos pasan por Remotion; badges de preview; migración de valores viejos del estado persistido (`"9:16 vertical"→"9:16"`, `"Original 16:9"→"16:9"`). |

### Calidad visual (lo que hace que "se vea bien")
1. **Centrado exacto por formato** — `_face_x_to_object_position` hoy solo calibra
   9:16; parametrizar la fracción visible por aspecto. *Alta prioridad: es la
   diferencia entre centrar al host o cortarlo.*
2. **Encuadre del split** — headroom parejo y costura prolija entre mitades.
3. **Cámara que sigue al hablante** — ya suavizada (media móvil + histéresis +
   dwell); verificar que se sienta natural en los formatos nuevos.
4. **Fondo del modo `fit`** — `blur(18px) brightness(0.35)`; ajuste estético opcional.
5. **Portada/cover** — mejor frame con cara, en las dimensiones del formato elegido.

### Orden
`config` → `ClipComposition` (quitar subs + `split`) → `layout_detector`
(`detect_split` + fracción por aspecto) → `renderer` → `app.py` → prueba
end-to-end con un clip por formato (idealmente uno con los dos hosts para el split).

### Preview del tramo antes de elegir el formato   ✅ IMPLEMENTADO (2026-08-02)

El formato se elegía a ciegas: en el Paso 3 el clip todavía no está cortado, así
que no había nada que mirar para saber si el tramo tiene **una** persona (→ 9:16)
o **dos** (→ split). Ahora el Paso 3 trae el panel *"👁 Ver el video y elegir
formato"*:

- **Tres fotos por tramo** (inicio / medio / final) sacadas del video original con
  seek rápido de ffmpeg (`-ss` antes de `-i`, sin recodificar) y cacheadas en
  `clips/_previews/`. ~0,6 s por tramo la primera vez, instantáneo después.
- **Reproductor del tramo** (toggle "▶ Ver el tramo en video"), servido por el
  mismo `media_server` con Range del editor de timeline: el navegador baja solo
  los bytes de ese tramo aunque el episodio pese varios GB. Usa el proxy 480p si
  ya existe; si no, el original.
- **Conteo de personas + sugerencia ⭐** (`modules/segment_preview.py`): Haar
  frontal + perfil (y perfil espejado, si no se pierde a quien mira al otro host).
  Una cara solo cuenta si aparece en la mitad de los frames — así una detección
  espuria no inventa una tercera persona y una cara perdida en un frame no
  desaparece. `people_max` avisa cuando el plano cambia dentro del tramo
  ("1–2 personas · mirá las fotos").
- **Botones de formato por clip** (el activo resaltado) + "Aplicar los N formatos
  sugeridos". Escriben en `st.session_state.clips` y refrescan la tabla vía
  `clips_editor_rev`; `merge_df_into_clips` persiste lo editado en la tabla antes
  del rerun para que no se pierdan títulos ni tiempos.

Sugerencia: 2+ personas → `split`, 1 → `9:16`, 0 caras claras → `16:9` (no
recorta nada). Es solo una sugerencia: la elección final siempre es del usuario.

Tests: `tests/test_segment_preview.py` (conteo, ruido, cambio de plano, claves de
caché).

### Cortes guiados por el audio + jump cuts + render paralelo   ✅ IMPLEMENTADO (2026-08-02)

Cuatro mejoras al proceso de edición, todas verificadas sobre material real
("Influencer Inside – Juanchi", 2h14):

**1. Bordes al audio** (`modules/audio_edit.py` + `clipper.plan_clip`). Los
tiempos vienen del VTT rolling de YouTube (±1–2 s), y el pad fijo de 0,25 s no
alcanzaba: había clips que arrancaban con media palabra. Ahora `silencedetect`
marca las pausas reales y el borde se pega a la más cercana dentro de ±1,5 s.
Dos detalles que importan:
- Se analiza un tramo **más ancho** que el clip (`start - SNAP_WINDOW`,
  `end + SNAP_WINDOW`). Mirando solo [start, end] el borde únicamente podía
  moverse hacia adentro, que es justo la dirección que come voz.
- Ante dos pausas igual de cerca gana la que **alarga** el clip (`_PREFER_FACTOR`):
  sumar aire es barato, perder palabras no tiene arreglo.
Cuando hubo snap se desactivan los pads fijos (el aire ya lo puso el snap).

**2. Loudness a -14 LUFS** (`LOUDNORM_FILTER`). El episodio de prueba medía
-21,2 LUFS integrados; la salida da -14,0 exactos. Sin esto cada episodio sale
con un volumen distinto y el clip se escucha flojo al lado del feed.

**3. Jump cuts** (opcional, checkbox en el Paso 3). `speech_segments` saca las
pausas de más de 0,7 s dejando 0,15 s de aire a cada lado, y `build_concat_filter`
arma un `filter_complex` con `trim`/`atrim` + `concat` en **un solo pase de
ffmpeg** (no hay archivos intermedios). Cada trozo de audio lleva un fundido de
20 ms: sin eso los empalmes hacen click. En los clips de prueba sacó 4–5 s de 65.
`clip_duration` ahora se mide con ffprobe del archivo real, porque con jump cuts
ya no es `end - start`.

**4. Render en paralelo** (`renderer.render_clips`, `config.RENDER_CONCURRENCY`,
default 2). Pool de hilos (cada uno lanza su propio proceso de Remotion) con dos
cuidados: `progress_fn` se llama **siempre desde el hilo principal** (quien lo
pasa está pintando en Streamlit) y los resultados se reordenan por `index`,
porque los renders terminan en cualquier orden. Además se reparten los núcleos
(`--concurrency` por render) para que dos renders no crean cada uno que tienen la
máquina entera. `media_server` ahora se traga los `ConnectionResetError` que
Chromium genera al abrir y cerrar sockets: con varios renders llenaban la consola.

**5. Encuadre previsualizado en 3 momentos** (`_clip_frames_bgr`). El encuadre
manual se aprobaba mirando UN frame (la mitad del clip) y se pagaba el error
después de un render entero. Ahora el mismo recorte se muestra en arranque /
medio / final — en la prueba quedó a la vista que un split elegido en el medio
dejaba al peluche en la mitad de arriba al principio y al final.

Tests: `tests/test_audio_edit.py` (parseo de silencedetect, snap, jump cuts,
armado del filtro).

**Pendiente / próximo:** los jump cuts son binarios por lote; estaría bueno
poder activarlos por clip y ver el "antes/después" antes de cortar.

### Análisis real de la toma (reemplaza el conteo de 3 frames)   ✅ (2026-08-02)

La primera versión sacaba 3 fotos por tramo y contaba caras exigiendo que
aparecieran en la mitad de los frames. Resultado sobre 30 clips reales: 19
sugerencias de 9:16 — pero **17 de esas 19 tenían 2 caras en algún frame**. Con 3
muestras en 70 s de un episodio que alterna plano general y primer plano, la
regla de mayoría es casi una moneda. No era un análisis, era una foto.

**Ahora** (`segment_preview`): una sola pasada de ffmpeg saca ~24 muestras (una
cada ~3 s) y se mide **cuánto tiempo** hay dos personas en cuadro:
`two_shot_ratio` ≥ 45% → split; casi sin caras → 16:9; el resto → 9:16. Entre 20%
y 45% se marca **MIXTO** ("cambia de plano"), que es justo el caso donde ningún
formato único sirve. La UI muestra el porcentaje y las muestras: la sugerencia es
auditable, no un veredicto.

Sobre los 30 clips reales pasó de 11 a 18 splits, y los extremos se verificaron a
ojo: 100% de dos personas = los dos hombres en el sillón; 8% = primer plano de
uno solo. Costo: ~1,3 s por tramo la primera vez (0,9 s extraer + 0,4 s detectar);
las caras se cachean en `faces.json` junto a los frames → 0,2 s para los 30 en
sesiones siguientes.

**Detector:** se probó MediaPipe FaceLandmarker (el que usa `layout_detector`
sobre el clip cortado) y devuelve **0 caras donde a ojo hay dos**: su detector es
de corto alcance y acá la gente está lejos y de perfil. Haar frontal + perfil a
480 px es el que acierta (a 720 px empieza a ver caras en los peluches).

**Limitación conocida (medida el 2026-09-23, ver más abajo):** Haar marca como
cara la mano de quien gesticula y algún objeto del set. Por eso las etiquetas
dicen **"2+ personas"** y nunca un número exacto mayor que 2.

### Seguir la toma: layout que cambia dentro del clip   ✅ (2026-08-02)

**Qué NO se puede:** cambiar la relación de aspecto a mitad del archivo. Un mp4
tiene dimensiones fijas. **Lo que sí:** cambiar el recorte dentro del mismo
lienzo — split mientras están los dos en cuadro, recorte cerrado al hablante
cuando la cámara va a uno solo. Es lo que necesitan los clips marcados como
"cambia de plano" (9 de 30 en el episodio de prueba).

- `segment_preview.shot_segments` convierte la línea de tiempo de muestras en
  tramos de layout. Cada muestra manda sobre la franja que la rodea; las muestras
  sin caras **heredan** el tramo anterior (un frame perdido no es un corte) y los
  tramos de menos de 3 s se funden con el vecino más largo, si no el recorte
  parpadea.
- `renderer.follow_shot_segments` los pasa a frames y calcula el `objectPosition`
  de cada tramo (aspecto completo para "fill", medio para "split"). Analiza el
  **archivo de clip ya cortado**, no el tramo del original: después del ajuste de
  bordes y los jump cuts los tiempos del original ya no mapean. Si el clip no
  cambia de plano devuelve None y se usa un layout fijo.
- `ClipComposition.tsx`: nuevo prop `layoutSegments` + `segmentAt(frame)`. Los
  branches de layout se extrajeron a un componente `ClipVisual` reutilizado por
  los dos caminos, así el modo normal quedó igual que antes.
- **El audio es el punto delicado:** al cambiar de layout los `OffthreadVideo` se
  desmontan y remontan, y si el sonido colgara de ellos se cortaría en cada
  cambio. En este modo los videos van todos muteados y el audio sale de un
  `<Audio src={clipPath}>` que abarca el clip entero.
- El encuadre manual sigue teniendo prioridad: si el usuario lo fijó, manda.

En la UI es un checkbox por clip ("🔀 Seguir la toma") en el panel del Paso 3.

### Dos versiones del 9:16   ✅ (2026-08-02)

Antes había un solo "9:16" y era **impredecible**: `auto_layout` decidía entre
recortar al hablante y mostrar el plano completo sobre fondo borroso, según el
tamaño de la cara detectada. Ahora son dos formatos explícitos:

| Formato | `base` | Qué hace |
|---|---|---|
| `9:16` | `fill` | Recorte vertical a pantalla completa, centrado en quien habla |
| `9:16-full` | `letterbox` (**nuevo**) | El 16:9 entero centrado sobre negro, barras arriba y abajo |

- Layout `letterbox` en `ClipComposition`: igual que `fit` pero **sin el fondo
  borroso** — fondo negro liso. `fit` se conserva porque 1:1 lo sigue usando como
  red de seguridad cuando no hay una cara grande.
- `allow_fit: False` en el preset de `9:16`: la caída a "fit" existía para no
  recortar mal cuando no hay cara; ahora eso se elige a mano con `9:16-full`, así
  que el recorte llena la pantalla siempre. **Ojo:** los clips ya guardados como
  `9:16` que dependían de esa caída (pantalla compartida, plano abierto) ahora se
  recortan — hay que pasarlos a `9:16-full` a mano.
- `crop: True/False` por preset reemplaza los `!= "16:9"` sueltos que había en
  tres lugares (encuadre manual, "seguir la toma", controles de la UI).
- La sugerencia automática cambió: "casi sin caras" ya no propone `16:9` sino
  `9:16-full` — lienzo vertical para redes, pero sin comerse nada de la imagen.
- `letterbox` no necesita detección de caras: se ahorra esa pasada entera.

### UX de "Ajustar encuadre"   ✅ (2026-08-02)

Reporte del usuario: *"al realizar cambios en los slides se cierra a veces y no se
ve bien los cambios"*. Tres causas, tres arreglos:

1. **Se cerraba solo.** El título del expander incluía un contador
   (`"…(1 manual)"`). Al activar el encuadre manual el título CAMBIA, Streamlit lo
   trata como un elemento nuevo y lo monta colapsado — justo mientras ajustabas.
   Ahora la sección es un `st.toggle` con key (su estado sobrevive los reruns) y
   el título es fijo. **Regla general para esta app: no meter valores variables en
   el label de un expander.**
2. **Se veía mal y andaba lento.** Se dibujaban los 15 clips a la vez, así que
   cada movimiento de slider recalculaba todos los recortes y cada preview
   quedaba diminuto. Ahora se ajusta **un clip por vez** (selectbox) y hay un
   "🔍 Ver el preview grande" que muestra un solo momento a todo el ancho.
3. **No se podía cambiar el formato después de cortar.** Se agregó el selector de
   formato en el Paso 4 y también en el Paso 5 (junto a "Re-renderizar este
   clip"). El corte es el mismo para todos los formatos — el formato solo afecta
   al render — así que corregir una elección mala **no requiere volver a cortar**.

`format_picker` pasó a recibir el dict del clip (antes escribía en
`st.session_state.clips[pos]`, lo que lo ataba al Paso 3).

**Extra:** `_STATE_FILE` ahora respeta la variable de entorno `ZUMO_STATE_FILE`,
para poder levantar una instancia de prueba sin pisar el estado de la que estás
usando.

**4. La página se rehacía entera con cada slider** (y el scroll saltaba). Streamlit
re-ejecuta todo el script ante cualquier widget. La solución es `@st.fragment`:
`framing_panel` (Paso 4) y `clip_framing_fragment` (Paso 5) se re-ejecutan
**solos**, sin volver a dibujar los videos de arriba. Medido en el navegador:
`scrollTop` = 1082 antes y después de mover el zoom, con el preview actualizado.
El cambio de **formato** sí hace rerun completo a propósito (cambia badges y el
resumen de render que viven fuera del fragment); para eso `_rerun_here()` usa
`scope="fragment"` cuando corresponde (p. ej. el botón de intercambiar mitades).

---

## Track 2 — Editor visual de timeline (Claude-opcional)   ✅ IMPLEMENTADO (2026-07-17)

> Estado: implementado y probado end-to-end. Componente React+wavesurfer en
> `components/clip_editor/`; media server con Range en `modules/media_server.py`;
> peaks en `modules/peaks.py` (cacheados en disco). Se llega desde el Paso 2
> ("✂️ Editar en timeline") o Paso 3 ("✂️ Timeline"); al Aplicar+Continuar, los
> cortes caen en la tabla de formato existente y siguen el pipeline normal.
> Aprendizajes: (1) las regiones necesitan la duración conocida — se siembran en
> `loadedmetadata`, no al montar; (2) el video se sirve con soporte de **Range**
> (el SimpleHTTPServer no lo trae) o el seek se rompe en archivos grandes.

Componente custom de Streamlit para **validar, ajustar y crear cortes a mano**
sobre una línea de tiempo, de modo que el pipeline **no dependa de Claude**.
Claude pasa a ser un "sembrador" opcional de candidatos.

### Stack (decidido)
- **Frontend:** React (plantilla oficial de componentes Streamlit) + TypeScript.
- **Waveform + regiones:** **wavesurfer.js v7** + plugin **Regions** (da regiones
  arrastrables/redimensionables de fábrica) atado al `<video>` vía `media`
  (sync player↔waveform por construcción).
- **Título/tipo:** se editan **dentro** del componente (panel de la región seleccionada).

### Estructura
```
components/clip_editor/
├─ __init__.py          # declare_component + wrapper clip_editor(...)
└─ frontend/            # React + TS
   ├─ package.json      # wavesurfer.js v7, @wavesurfer/react, plugin regions
   ├─ src/ClipEditor.tsx
   └─ build/            # assets COMPILADOS y COMMITEADOS (no npm en runtime)
```

### Piezas
1. **Flujo Claude-opcional** (`app.py`): botón "✏️ Editar clips manual" salta al
   Paso 3 con lista vacía; los clips de Claude, si existen, entran como semilla.
   Los cues siguen sirviendo para titular pero **ya no son requisito** para avanzar.
2. **Server de media de sesión:** reutilizar `_ClipServer` (`renderer.py:32`) para
   servir el video al iframe del componente (`file://` está bloqueado). Handle en
   `session_state`.
3. **Componente `clip_editor`:** `<video>` + wavesurfer + Regions; cada región es
   `{start, end, title, type}`; botones marcar IN/OUT en `currentTime`, añadir,
   borrar, reproducir región. **Commit-on-"Aplicar"** (no enviar en cada drag,
   para no thrashear los reruns de Streamlit).
4. **Waveform de videos largos:** **precomputar los peaks** server-side una vez
   (ffmpeg → JSON min/max) y pasarlos a wavesurfer (`peaks`); decode client-side
   como fallback para clips cortos. Evita decodificar una hora de audio en el browser.
5. **Salida:** la lista del editor reemplaza `approved` → `cut_clips` sin cambios.
   "Buscar más clips" (Claude) empuja candidatos como regiones nuevas.

### Riesgos (acotados)
| Riesgo | Estado |
|---|---|
| Drag/resize de regiones | Resuelto por plugin Regions |
| Sync video↔timeline | Resuelto por `media` de wavesurfer |
| Reruns de Streamlit | Commit-on-Aplicar |
| Waveform en videos largos | Peaks precomputados server-side |
| Build de frontend | Assets commiteados; Node ya existe por Remotion |
| **`build/` en `.gitignore`** | Resuelto: negación para `components/clip_editor/frontend/build/` (ver `.gitignore`) |

### Orden de construcción
1. Scaffold del componente (plantilla + wavesurfer + build vacío que renderiza).
2. Server de media de sesión + carga del video en el componente.
3. Waveform + Regions + marcar IN/OUT + add/delete.
4. Edición de título/tipo por región + commit-on-Aplicar.
5. Precómputo de peaks (ffmpeg) para videos largos.
6. Integración en `app.py` (flujo Claude-opcional + salida a `cut_clips`).
7. Prueba end-to-end: abrir vacío, marcar 2-3 cortes a mano, cortar; y sembrado desde Claude.

---

## Track 3 — Animaciones (overlays con Remotion)   ✅ COMPLETO (2026-09-23)

Cuatro capas encima del clip, manejadas por parámetros (sin LLM): el **gancho**,
la **placa de nombre** y las placas de **apertura** y **cierre**. Van como overlay y no como placas concatenadas, así que
**no alargan el clip ni obligan a volver a cortar** — solo afectan al render.

### Lo que hay

**Gancho** (`overlays/HookTitle.tsx`). Una frase grande al arranque. Si no se le
escribe nada usa el título del clip, que es texto que Claude ya escribió.
- Tres entradas: aparece de golpe (`pop`), sube desde abajo (`slide`), se
  escribe sola (`type`).
- La entrada dura **0,35 s** a propósito: el primer segundo es el que decide si
  alguien se queda, y no se puede gastar esperando una animación.
- Lleva un **velo en degradado** detrás. Se agregó después de mirar el primer
  render: la sombra del texto alcanza sobre una imagen oscura, pero el set tiene
  un mural blanco y ahí el texto blanco se perdía. El degradado arranca del
  borde y se va a nada, así no se lee como una caja encima de la cara.

**Placa de nombre** (`overlays/LowerThird.tsx`). Nombre y rol de quien habla.
- Los nombres salen de los **hosts que ya están cargados en Ajustes**: se elige
  de una lista en vez de escribirlos de nuevo. "Otro…" queda para un invitado.
- El nombre "lower third" viene de la tele, donde iba en el tercio inferior. En
  vertical eso queda **debajo de la interfaz de la app**, así que se apoya más
  arriba (ver `SAFE_BOTTOM`).

**Las zonas seguras** (`overlays/theme.ts`). TikTok, Reels y Shorts dibujan su
propia interfaz encima del video: se reserva el 18% de abajo y el 10% de arriba.
Cualquier cosa puesta ahí la tapa la app.

### Lo que cuesta

Medido sobre el mismo clip de 8 s, mismo formato:

| | tiempo |
|---|---|
| sin capas | 29,8 s |
| con capas | 29,9 s |

Es ruido. Y un clip **sin** capas renderiza idéntico a antes: comparando la
mitad inferior del cuadro entre los dos renders, la diferencia media es
**0,36/255** — ruido de codificación, no un cambio visual. Eso es por diseño:
`for_render` devuelve `None` cuando no hay nada prendido, el prop no viaja y
`OverlayLayer` corta enseguida.

La fuente se pide con pesos y subset explícitos (`loadFont("normal", {weights:
["700","900"], subsets: ["latin"]})`): sin argumentos son ~190 peticiones por
render para usar dos. Es la misma trampa que ya había costado en `ColdOpen`.

### Fase 2 — Ver las capas sin renderizar el clip   ✅ (2026-09-23)

Un botón **"Ver cómo queda"** en la pestaña de capas genera un frame real: el
mismo `remotion still` que hace la portada y **la misma composición** que el
render final, así que lo que se ve ahí es lo que va a salir. Un still por capa
prendida, en el medio de su ventana visible.

**Por qué es un botón y no automático.** Medido: el still tarda **5,1 s**, y
resolver el encuadre **11,5 s** (detecta caras sobre el archivo de clip).
Regenerar en cada movimiento de un control sería insoportable. Entonces:

- El encuadre se cachea por clip, con una firma que incluye formato, seguimiento
  y encuadre manual — pero **no** las capas, que no lo afectan. Mover un control
  de capas no vuelve a pagar los 11,5 s.
- Si tocás algo después de generar, el preview queda marcado — *"⚠️ Cambiaste
  algo: este preview es de antes"* — en vez de mentir mostrando lo viejo.
- El still se dibuja a la mitad del tamaño. Todo en la composición es
  proporcional al ancho, así que se ve igual, solo que más chico y más rápido.

**Dos cosas que aparecieron al construirlo:**

1. **Chromium bloquea `file://`.** El primer still falló con *"Media load
   rejected by URL safety check"*. El render del clip y el de la portada ya
   servían el archivo por HTTP por esta misma razón; `overlay_preview` pide
   `clip_url` como obligatorio, y quien llama lo sirve (en la app, el mismo
   MediaServer de las miniaturas).
2. **El gancho "abajo" y la placa se pisan.** Los dos se apoyan justo arriba de
   la zona que tapa la interfaz de la app, así que si además coinciden en el
   tiempo quedan uno encima del otro. `overlays.collision()` lo detecta y la UI
   lo avisa con los segundos exactos: *"se pisan entre el segundo 3.0 y el
   6.0"*. Es barato avisarlo y carísimo descubrirlo en el render.

### Fase 3 — Las placas de apertura y cierre   ✅ (2026-09-23)

Estaban descartadas en la fase 1 con este argumento: *una placa a pantalla
completa en un clip de 60 s se come justo los segundos donde se decide si
alguien se queda*. El argumento sigue en pie, así que la placa **no tapa el
video**: lo oscurece lo que se le diga (`dim`, 0,55 por default) y el
movimiento sigue abajo mientras se lee. Con `dim` en 1 queda la placa opaca de
toda la vida, para quien la quiera.

- La de **apertura** cuenta desde el frame 0. Al prenderla se propone el nombre
  del canal como título, que es lo que uno pone ahí casi siempre.
- La de **cierre** se ancla al **final** del clip, que es lo que uno quiere
  decir cuando dice "los últimos 3 segundos".
- Ninguna alarga el clip: siguen siendo overlays.

**Un bug que encontró el preview, no el render.** La placa de cierre salía
vacía en el preview: `overlay_preview` no mandaba `durationInFrames`, así que la
composición calculaba la duración leyendo el archivo entero (64 s) y anclaba la
placa contra un final que no era el del clip (8 s). En el render nunca pasó —
`render_clip` sí lo manda— pero el preview mentía. Para eso sirve mirar.

**El aviso de choque** ahora cubre dos casos: el gancho "abajo" contra la placa
de nombre, y la placa de apertura contra el gancho (las dos ocupan el centro en
los primeros segundos). Dice los números: *"La placa de apertura dura 2.0 s y el
gancho arranca en 0.2 s: se superponen."*

Verificado con un render de verdad de 8 s: segundo 1 con la apertura, segundo 4
limpio, segundo 7,2 con el cierre.

### Dónde vive cada cosa

| Archivo | Qué |
|---|---|
| `remotion/src/overlays/types.ts` | el contrato (tiempos en segundos, que es lo que edita una persona) |
| `remotion/src/overlays/theme.ts` | fuente, acento, zonas seguras, la envolvente de entrada/salida |
| `remotion/src/overlays/HookTitle.tsx` · `LowerThird.tsx` · `Card.tsx` | las capas |
| `remotion/src/overlays/OverlayLayer.tsx` | las compone; `null` si no hay nada |
| `remotion/src/ClipComposition.tsx` | `ClipBody` resuelve el video y el recorte; la exportada lo envuelve con las capas **una sola vez**, para no repetirlas en cada rama de layout |
| `modules/overlays.py` | defaults, validación, recorte de tiempos a la duración del clip |
| `app.py` | pestaña "✨ Capas" en el Paso 4, sobre el clip en foco |

`modules/overlays.py` tiene 23 tests. El que más importa: **una capa no puede
arrancar después de que el clip terminó** — un gancho en el segundo 80 de un
clip de 60 no se ve nunca, y descubrirlo cuesta un render entero.

---

## Palanca transversal — Más candidatos de Claude para curar (opcional, barato)
Hoy Claude genera un 50% extra de candidatos y luego los **descarta** para quedarse
en N exactos (`analyzer.py:189` pide de más, `analyzer.py:308` trunca). Exponer
**todos los candidatos con un score/ranking** (campo "gancho 1-5" en el tool schema)
da más material para elegir en el editor. Cambio chico, encaja en el Track 2.

---

## Track 4 — La UI en React, pantalla por pantalla   ✅ FASES 1 a 6 (2026-09-23)

> Decisión: la UI se mueve a React **por pantalla**, empezando por la que más
> dolía. El componente se escribe contra una interfaz de props/callbacks y toda
> la atadura a Streamlit vive en un solo archivo, para que la mudanza a una API
> HTTP sea cambiar el bridge y no reescribir la pantalla.

### El problema, medido sobre un episodio real

Sobre *Automatización con IA* (78:48, 15 clips analizados / 20 cortados):

| Pantalla | Antes |
|---|---|
| Paso 3 con el panel de formato abierto | **6.664 px = 7,5 pantallas** de scroll, 45 miniaturas; al abrirlo Chrome dejó de responder >30 s |
| Paso 5 (captions) | 27.982 px = **31,5 pantallas**, 297 botones, **20 `<video>` cargados a la vez** |
| Tabla del Paso 3 | tiempos en segundos decimales (`97.1 → 163.4`), títulos y razones truncados |

El diagnóstico de fondo: la app era un formulario de una columna que crece
linealmente con la cantidad de clips, con el texto al frente y la evidencia
visual escondida detrás de un expander.

### Lo que hay ahora

`components/clip_gallery/` reemplaza, en el Paso 3, a la planilla + el panel
"👁 Ver el video y elegir formato" + los botones de selección rápida.

- **Una tarjeta por clip**: foto del tramo, timecode (`1:37 → 2:43`), duración,
  tipo, título editable en línea, la evidencia del análisis con su barra, los 5
  formatos y los toggles de seguimiento.
- **El recorte, dibujado sobre la foto** (`Crop.tsx`). Es el cambio que hace
  intuitiva la elección: el marco muestra qué se queda el formato y lo de afuera
  va apagado. El `split` dibuja los dos recortes, ubicados en `centers_x` si el
  análisis los tiene. Los formatos que no recortan muestran "plano completo".
- **Iconos dibujados, no emojis.** Cada formato es un rectángulo con su
  proporción real: los emojis (📱 ⬛ 🖥 ⧉) se veían distinto en cada máquina y
  rompían la altura de la fila de botones.
- **El video no se precarga**: las miniaturas son `loading="lazy"` y el `<video>`
  del tramo se monta recién al tocar ▶.

| Pantalla | Antes | Ahora |
|---|---|---|
| Paso 3 (alto de página) | 6.664 px · 7,5 pantallas | **2.175 px · 2,4 pantallas** |
| Botones que dibuja Streamlit | 244 | **10** |
| Videos precargados | — | **0** |

### El bridge (lo que hace barata la mudanza a una API)

```
frontend/src/
  types.ts              contrato (sin React, sin host)
  bridge.ts             interfaz Host: subscribe / commit / setHeight / ready
  bridge.streamlit.ts   UNICO archivo que importa streamlit-component-lib
  ClipGallery.tsx       React puro: props y callbacks
  ClipCard.tsx  Crop.tsx  ui.ts
  main.tsx              elige la implementación del Host
```

**Regla:** si `streamlit-component-lib` aparece importado fuera de
`bridge.streamlit.ts`, la mudanza dejó de ser gratis. El día que exista la API,
se agrega `bridge.http.ts` y se cambia una línea en `main.tsx`.

### Dos trampas del modelo de Streamlit, y cómo quedaron resueltas

1. **La carrera del eco.** Cada commit del componente dispara un rerun, y la
   respuesta del host llega *después*. Con dos clics seguidos, el eco del primero
   pisaba al segundo — se perdían cambios. La galería ahora espera ver de vuelta
   exactamente lo que mandó (`pendingRef`) antes de volver a aceptar datos de
   afuera. Verificado: 4 clics a 60 ms de distancia, los 4 llegan al disco.
2. **El nonce que se repite.** Las acciones que no ejecuta la galería (abrir el
   editor de timeline) viajan en el valor, y Streamlit devuelve ese mismo valor
   en cada rerun; hace falta un nonce para no dispararlas dos veces. Si el
   contador arrancara en 0, al remontarse el componente repetiría un nonce ya
   consumido y la acción quedaría ignorada: se siembra con `Date.now()`. El
   último nonce consumido se guarda con el estado, así tampoco se repite la
   acción al reiniciar la app.

### Fase 2 — El Paso 5 deja de ser una lista infinita   ✅ (2026-09-23)

El Paso 5 dibujaba los 20 clips en expanders **abiertos a la vez**: 27.982 px de
alto (31,5 pantallas), 297 botones y 20 `<video>` cargados al mismo tiempo. Ahora
es lista + detalle (`src/publish/`): la lista a la izquierda es el mapa del
episodio (portada, número, duración, formato, aviso de "sin render"), y a la
derecha hay un solo clip abierto con su video, su formato y sus tres textos.

| | Antes | Ahora |
|---|---|---|
| Alto de la página | 27.982 px · 31,5 pantallas | **2.457 px · 2,6 pantallas** |
| Videos cargados | 20 | **1** |
| Botones que dibuja Streamlit | 297 | **17** |

**El bug que estaba escondido ahí:** los captions se dibujaban con
`st.text_area(...)` y **nunca se leían de vuelta**. Editar un caption no hacía
nada: el CSV y Postiz seguían mandando el texto original de Claude. Ahora los
textos son del componente y `apply_publish` los vuelca sobre el clip. Verificado
escribiendo en el textarea y leyendo `.pipeline_state.json`.

**Copiar al portapapeles.** `navigator.clipboard.writeText` dentro de un iframe
sin foco **no resuelve ni rechaza: se cuelga**, así que un aviso de "copiado"
colgado de ese `await` no llegaba nunca. El camino es el `textarea` +
`execCommand("copy")`, que es sincrónico y devuelve si funcionó; la API moderna
queda de respaldo. Y si falla, el botón dice **"no se pudo"** en vez de mentir.
Verificado con clic real de mouse: devuelve `true` y el botón dice "copiado".

**Lo que se queda en Streamlit, a propósito:** el encuadre manual
(`clip_framing_fragment`) saca frames del clip en el servidor y los dibuja, que
es justo lo que el componente no puede hacer. Se dibuja debajo, para el clip que
esté abierto — el componente informa cuál en `selected`.

### Fase 3 — El Paso 4 y los tests que faltaban   ✅ (2026-09-23)

**El Paso 4** dibujaba los 20 clips como reproductores en una grilla de 3
columnas: 20 `<video>` montados a la vez que mostraban un spinner en vez de un
frame, y las filas se desalineaban cuando un título ocupaba dos líneas. Ahora usa
la **misma galería del Paso 3** con dos banderas:

- `pickable=False` — ya están cortados, no hay nada que tildar: la tarjeta
  muestra el número del clip en vez del checkbox y no se apaga.
- `show_timeline=False` — el editor de timeline corta, y eso ya pasó.

Y dos cosas nuevas que la galería no tenía:

- **`clipUrl` por clip.** Si viene, la tarjeta reproduce el archivo ya cortado
  en vez de buscar el tramo dentro del original. Importa: después del ajuste de
  bordes y los jump cuts, el corte real no es el tramo del original.
- **`selected` en el valor de vuelta.** La tarjeta en foco viaja al host para
  que dibuje el encuadre manual de *ese* clip debajo. Avisar cuesta un rerun
  entero, así que solo se manda cuando el host tiene algo que dibujar
  (`!pickable`): en el Paso 3 hacer foco no cuesta nada.

| Paso 4 | Antes | Ahora |
|---|---|---|
| Videos montados | **20** (todos con spinner) | **0** hasta que tocás ▶ |
| Se ve el contenido sin esperar | no | sí, con el recorte del formato encima |
| Alto | 2.862 px | 2.751 px |

`framing_panel` y `format_picker` quedaron sin uso: el selectbox "clip a
ajustar" lo reemplaza tocar la tarjeta, y los botones de formato ya están en
cada tarjeta.

### `modules/ui_state.py` — la traducción, con tests

`clips_to_gallery`, `apply_gallery`, `clips_to_publish`, `apply_publish` y
`normalize_format` salieron de `app.py`. No es prolijidad: es **el punto donde
un error hace perder ediciones sin avisar**, que es exactamente lo que pasó con
los captions del Paso 5 durante meses sin que se notara.

Para que el módulo no dependa de Streamlit, las funciones reciben un
`url_for(path) -> str`; los MediaServer siguen siendo de `app.py`.

`tests/test_ui_state.py`: 20 tests. Cubren la normalización de formatos viejos,
que la galería no pise el encuadre manual, que un payload de ida y vuelta sin
tocar nada devuelva `False` (si no, cada rerun escribiría el estado en disco al
pedo), que los captions editados se guarden y que no se borren las plataformas
que no vinieron en el patch. Se verificó que tienen dientes: inyectando el bug
viejo (que `apply_publish` no escriba `clip["captions"]`), 2 tests fallan.

### Fase 4 — Tema propio y pantalla de configuración   ✅ (2026-09-23)

**El tema** vive en `.streamlit/config.toml`. El acento es `#FFD000`, el mismo
amarillo de la pieza de cierre de Remotion (`CierreOutro.tsx`), así la
herramienta y los videos que salen de ella hablan el mismo idioma. El fondo **no**
es el marrón cálido del ColdOpen a propósito: acá se mira material para decidir
encuadres y colorimetría, y un fondo tibio tiñe la percepción de lo que estás
juzgando.

El tema llega gratis a las pantallas React: leen `theme` del host. Pero eso
destapó algo — el texto sobre el acento estaba hardcodeado en blanco, que con el
rojo de Streamlit se leía y con el amarillo da **1,7:1**. Ahora `theme.ts`
calcula el color por luminancia (`readableOn`): medido en el navegador, el chip
de formato activo quedó en **12,3:1**.

Además, un `<style>` chico para lo que el tema no alcanza: el aire de arriba
(Streamlit deja ~6 rem, media pantalla perdida en cada recarga), una sola altura
de botón, y el encabezado con los 5 pasos. La barra de progreso azul y el
`st.title` con emoji se fueron.

**La pantalla de configuración.** Antes, sin `ANTHROPIC_API_KEY` la app no
arrancaba: `config.py` hacía `raise` al importarse y lo único que ofrecía era un
mensaje pidiendo editar el `.env` a mano. Ahora:

- `config.py` no revienta al importar. `llm_missing()` dice qué falta y
  `require_llm()` (que sí levanta) la usan los scripts de línea de comandos, que
  no tienen dónde configurar nada. El uso real siempre estuvo protegido:
  `modules/llm.py` no llama a la API sin key.
- La primera vez que abrís la app te recibe la configuración: datos del canal y
  con qué modelo trabajás. Después se vuelve desde **⚙ Ajustes**.
- **Dónde va cada cosa:** la API key al `.env` y solo ahí (ya estaba en
  `.gitignore`, y es de donde `config.py` lee al arrancar). Los datos del canal a
  `settings.json`. `save_settings` **levanta una excepción** si alguien le pasa
  una key: `settings.json` y `.pipeline_state.json` se copian y se comparten sin
  pensarlo. En pantalla la key se muestra enmascarada (`sk-ant-…4f2a`): alcanza
  para reconocer cuál está puesta sin dejarla legible en una captura.
- `env_upsert` reemplaza la línea y deja el resto intacto. Reescribir el archivo
  entero se llevaría puestos los comentarios y `POSTIZ_API_KEY`.

**El bug que apareció probándolo:** los campos del canal usaban `key="ch_name"`
y compañía. Streamlit **purga de `session_state` las claves ligadas a un widget
en cuanto ese widget deja de dibujarse**, así que al salir de Ajustes los datos
del canal desaparecían — y con ellos el contexto que recibe el modelo para
elegir clips y escribir captions. Los campos ahora usan claves propias
(`setup_ch_*`) y vuelcan sobre las plantas al guardar. Es exactamente la misma
trampa que ya estaba documentada para `source_mode`, y vale como regla: **en esta
app, un dato que tiene que sobrevivir a que su pantalla se cierre no puede usar
la clave del widget.**

`tests/test_settings.py`: 17 tests. Que el `.env` no se rompa (clave parecida,
línea comentada, valor con un salto de línea que partiría el archivo en dos
variables), que `save_settings` rechace secretos, y que la máscara no filtre.

**De paso:** la fila de entrada (URL / archivo local) solo se dibuja en el paso
1. Antes quedaba arriba para siempre, deshabilitada y con `C:\Videos\mi_video.mp4`
adentro. El Reset se fue a la barra lateral, que ahora dice el canal y el modelo
en vez de los cuatro campos de configuración que ocupaban 245 px para siempre.

### Fase 5 — Se va Postiz, entra el material, y el bug de la tilde   ✅ (2026-09-23)

**Postiz, afuera.** La integración no funciona por el lado de Postiz, así que se
saca entera: `modules/postiz.py`, `schedule_postiz.py`, el Paso 6 de la app, las
variables de `config.py` y del `.env.example`, y la sección de `DEPLOYMENT.md`.
La salida del pipeline es el CSV, que de paso ahora reporta la duración **real**
del archivo (con jump cuts no es `end - start`).

`POSTIZ_API_KEY` sigue en la lista negra de `settings.py` a propósito: la
integración se fue, pero el `.env` de quien venía usando esto la tiene igual, y
esa lista existe para que una key no termine en un archivo que se comparte.

**El material se elige, no se escribe.** "Archivo local" era un campo de texto
donde había que tipear `C:\Videos\mi_video.mp4`. Ahora lista lo que hay en una
carpeta configurable (`modules/library.py`), con nombre, carpeta de origen y
peso, del más nuevo al más viejo, y deja "Otra ruta…" para el resto. No es un
`file_uploader` a propósito: el archivo está en el disco de la misma máquina que
corre la app, así que subirlo por HTTP sería mandar varios GB para dejarlos
donde ya estaban.

Dos cosas que el listado no hace, y son el punto:
- **No ofrece los `proxy480`.** Son las copias de 480p que genera la app para
  editar. Elegir una significaría cortar y renderizar el episodio entero desde
  una copia degradada sin que nada lo avise.
- **No trata una carpeta vacía como "la raíz".** `Path("")` es `Path(".")`: sin
  ese corte, dejar el campo vacío en Ajustes listaría los renders de `output/`
  como si fueran material de origen. Lo encontró el test, no la vista.

---

### El bug de la tilde

Venía arrastrándose que el análisis de la toma decía **"sin caras el 100% del
clip"** en todos los tramos, con las caras a la vista en la miniatura de al lado.
Estaba anotado como un problema del detector contra el fondo verde del set. No
era el detector.

`cv2.imread` en Windows abre el archivo con la *code page* ANSI del sistema, no
con UTF-8. Con una `ó` en la ruta no encuentra nada y devuelve `None`: sin
excepción, sin aviso. Y el `video_id` de esta app sale del título del episodio,
así que `clips/_previews/Automatización_con_IA…/f_001.jpg` era ilegible y
`detect_faces` devolvía `[]` para todos los frames.

Medido sobre los 735 frames cacheados del episodio de prueba:

| | Antes | Después |
|---|---|---|
| Frames con al menos una cara | **0 (0%)** | **710 (96%)** |
| Frames con dos o más | 0 (0%) | 52 (7%) |

Y eso cambia lo que la app recomienda: los 15 clips sugerían `9:16-full`
(lienzo vertical con barras, sin recortar nada), que es lo que sugiere cuando no
ve caras. Ahora sugieren `9:16` con el recorte **puesto sobre la persona**, que
es lo que se ve en la galería: el marco dejó de estar centrado por defecto.

El arreglo es `modules/imaging.py`: leer los bytes desde Python (que sí entiende
la ruta) y dejar que OpenCV decodifique el buffer. Reemplaza a `cv2.imread` en
los cuatro lugares donde estaba (`segment_preview`, `layout_detector`,
`renderer`, `app`).

**No alcanzaba con arreglar la lectura:** los `faces.json` guardados tenían los
ceros adentro y se habrían seguido usando para siempre. El caché ahora lleva
versión (`FACES_CACHE_VERSION`), y el formato viejo — una lista pelada, sin
versión — se descarta por definición.

**Para acordarse:** cualquier ruta de esta app puede tener acentos, porque sale
del título de un episodio en español. Nada que toque archivos puede asumir ASCII.

### Fase 6 — Cuánto ruido mete el detector, medido   ✅ (2026-09-23)

Con la detección funcionando de verdad ([[el bug de la tilde]]), se midió qué
son las detecciones de más. Sobre **3.314 frames de 6 episodios**:

| detecciones en el frame | frames |
|---|---|
| 0 | 65 |
| 1 | 2.588 |
| 2+ | 661 |

Mirando los casos a ojo con las cajas dibujadas encima, los falsos positivos son
**la mano de quien gesticula** y **un objeto del fondo del set**. No son los
dibujos del mural, que era la sospecha anotada.

**Dos hipótesis, una sirve y la otra no:**

- *Filtrar por tamaño* (una cara espuria es más chica): **no sirve**. La
  relación entre la segunda detección y la más grande del mismo frame da mediana
  0,81 y p25 0,69 — y los falsos positivos verificados caían en 0,67 y 0,69,
  mezclados con two-shots reales donde una persona está un poco más lejos.
- *Filtrar por estabilidad temporal* (un dibujo no se mueve nunca): **no sirve**.
  De 147 tramos, **cero** tienen una detección clavada en la misma celda en el
  60% de los frames: Haar tiembla frame a frame aun sobre un objeto quieto. La
  idea estaba anotada como "pendiente de evaluar"; queda evaluada y descartada.
- *Filtrar por altura*: **sirve**. La detección más grande de cada frame vive
  entre cy 0,30 y 0,44 (p10–p90) y solo el 1% baja de 0,62; las secundarias
  llegan a 0,67 en el p90.

**Lo que cambia, y lo que no.** Barriendo el umbral, entre 0,60 y 0,65 hay una
meseta: mismos 19 splits que sin filtro. Por debajo de 0,55 se empiezan a perder
two-shots de verdad (18, después 17). Se fija en **0,62**.

| sobre 147 tramos | sin filtro | con filtro |
|---|---|---|
| Sugerencias `9:16` / `9:16-full` / `split` | 127 / 1 / 19 | **127 / 1 / 19** |
| Tramos marcados "cambia de plano" | 29 | **19** |

O sea: **el ruido nunca cambiaba el formato sugerido** — no era el problema que
parecía. Lo que sí hacía era inflar el aviso de "cambia de plano", que le dice al
usuario que ningún formato único le sirve: un tercio de esas advertencias eran
una mano.

`FACES_CACHE_VERSION` sube a 3, porque el caché guarda el resultado ya filtrado.

### La estructura del frontend

Un solo proyecto de frontend y un solo build; `screen` elige la pantalla.

```
components/zumo_ui/
  __init__.py              clip_gallery(...) y clip_publish(...)
  frontend/src/
    bridge.ts              interfaz Host (subscribe / commit / setHeight / ready)
    bridge.streamlit.ts    UNICO archivo que importa streamlit-component-lib
    theme.ts  Crop.tsx  types.ts        compartidos
    main.tsx               despacha por args.screen
    gallery/               Paso 3
    publish/               Paso 5
```

Se probó tener un proyecto npm por componente con el código común afuera: no va.
La resolución de módulos de Node busca `node_modules` desde la carpeta del
archivo hacia arriba, así que un `src/` compartido fuera del proyecto no
encuentra ni `react`. Un proyecto con dos entradas HTML tampoco: Vite emite
`../assets/...` para una entrada anidada y el server de componentes de Streamlit
sirve una sola raíz. Una entrada y un `screen` en los props resuelve las dos
cosas sin pelearse con nada.

### Lo que queda para las fases siguientes

- Nada pendiente de la UI.
- **El detector de caras no ve este set.** En el episodio de prueba, los 15
  tramos dan "sin caras el 100%" y la sugerencia sale `9:16-full` para todos,
  aunque las fotos tienen caras claras. Es el Haar de `segment_preview` contra
  el fondo verde/mural del set, no la galería — pero ahora se ve de un vistazo,
  que es justamente para lo que sirve mostrar la evidencia.

---

## Remotion 4.0.500 → 4.0.527   ✅ (2026-09-23)

`npx remotion upgrade` calcula bien el conjunto de paquetes (todos los
`@remotion/*` tienen que ir en la misma versión) pero **en Windows no puede
lanzar `npm`**: falla con `ENOENT spawn npm` porque busca `npm` y no `npm.cmd`.
La vuelta es dejar que imprima el comando y correrlo a mano. Sube también `zod`
(4.4.3 → 4.5.4), que va de la mano.

**Verificado contra una referencia, no de palabra.** Se renderizó el mismo clip
de 8 s con gancho, placa de nombre y placa de cierre, antes y después:

| | 4.0.500 | 4.0.527 |
|---|---|---|
| Dimensiones / fps / códec / duración | 1080×1920 · 30 · h264 · 8,107 s | **idéntico** |
| Tiempo de render (mediana de 3) | 31,0 s | **31,2 s** |
| Diferencia media entre frames | — | 1,6/255 · 1,07 difuminando 3 px |

La primera corrida después de actualizar tardó 42,4 s, pero es arranque en frío:
las tres siguientes dieron 31,7 / 31,2 / 30,2. La diferencia entre frames es
ruido de compresión sobre los bordes de alto contraste (texto, el mural del
fondo): al difuminar cae a ~1/255 y no hay corrimiento — el texto, la barra de
acento y el recorte caen en el mismo lugar.

`src/` compila limpio; los 7 errores de `tsc` son de las definiciones de tipos
de `node_modules` y son los mismos que antes.

### El Studio colgado: no era la versión

Estaba anotado que el Studio arrancaba tirando `TypeError: Cannot use 'in'
operator to search for 'width' in undefined` y que "se cae solo al subir de
versión". No era eso. El Studio se queda **para siempre** en *"Running
calculateMetadata()…"* al abrir `ClipComposition`, y la causa es local:
`public/preview.mp4` está gitignorado y **no existe**.

El guard que había (`if (!p.clipPath)`) no lo atrapa, porque `staticFile()`
devuelve una ruta igual aunque el archivo no esté. Y un `try/catch` tampoco
alcanza — se probó: contra un archivo inexistente `getVideoMetadata` **no
rechaza, se cuelga**, así que no hay error que atrapar. Lo que funciona es una
carrera contra el reloj (4 s) y caer a una duración de muestra.

Con eso el Studio abre la composición (timeline de 30 s, lienzo negro porque no
hay video) en vez de quedarse girando. Sigue siendo mejor dejar un
`remotion/public/preview.mp4` para previsualizar de verdad.

**Los proyectos de `episodios/` quedan en 4.0.494 a propósito:** son proyectos
aparte, y `episodios/criterio/` ya está renderizado y sincronizado al VO. Subir
su versión es cambiar la herramienta de un episodio terminado sin necesidad.

---

## Registro de decisiones

| Fecha | Decisión |
|---|---|
| 2026-07-17 | Formato manual por clip: 16:9, 1:1, split (stack de 2), además del 9:16 actual. |
| 2026-07-17 | **Se descartan los subtítulos quemados** del render; se agregan desde las apps de redes. La transcripción (VTT/Whisper) se conserva porque la usa el análisis de Claude. |
| 2026-07-17 | Todos los formatos pasan por Remotion (consistencia de portada/calidad). |
| 2026-07-17 | Encuadre del split: automático ahora (reusa clustering de caras), sliders manuales después. |
| 2026-07-17 | Editor visual de timeline como componente custom, para independizar el pipeline de Claude. |
| 2026-07-17 | Editor: React (plantilla oficial) + wavesurfer.js v7 (waveform + Regions) + edición de título/tipo dentro del componente. |
| 2026-07-17 | Track 3 (animaciones): 3 overlays (hook / intro-outro / lower-third) como capa sobre el clip, con presets de parámetros (sin LLM), render en paralelo. Planificado, sin implementar. |
| 2026-09-23 | La UI se mueve a React por pantalla. Empieza la galería de clips (Paso 3); el componente se escribe contra props/callbacks con el bridge de Streamlit aislado, para poder mudarlo a una API sin reescribirlo. |
| 2026-09-23 | Un solo proyecto de frontend y un solo build para todas las pantallas; `screen` elige cuál montar. Un proyecto npm por componente no funciona (resolución de módulos), y varias entradas HTML tampoco (rutas de assets). |
| 2026-09-23 | La traducción clips ↔ pantallas sale de `app.py` a `modules/ui_state.py` con tests: es donde un bug hace perder ediciones sin avisar. |
| 2026-09-23 | La API key se pone desde la app y va al `.env`, nunca a `settings.json` ni al estado. `config.py` deja de reventar al importar: sin key la app abre y te lleva a configurarla. |
| 2026-09-23 | Se saca la integración con Postiz: no funciona del lado de Postiz. La salida del pipeline es el CSV. |
| 2026-09-23 | `cv2.imread` no lee rutas con acentos en Windows: se prohíbe en el proyecto, va `modules.imaging.imread`. Cualquier ruta de esta app puede tener una tilde, porque sale del título del episodio. |
| 2026-09-23 | Track 3 fase 1: gancho y placa de nombre como overlay. Intro/outro queda afuera — una placa a pantalla completa se come los segundos donde se decide la retención, que es lo que el gancho resuelve sin costar tiempo. |
| 2026-09-23 | Remotion 4.0.500 → 4.0.527, verificado contra un render de referencia. `remotion upgrade` no puede lanzar npm en Windows (busca `npm`, no `npm.cmd`): el comando se corre a mano. Los proyectos de `episodios/` se quedan en 4.0.494. |
