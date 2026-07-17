# Roadmap — Fast Video Clipping

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

## Palanca transversal — Más candidatos de Claude para curar (opcional, barato)
Hoy Claude genera un 50% extra de candidatos y luego los **descarta** para quedarse
en N exactos (`analyzer.py:189` pide de más, `analyzer.py:308` trunca). Exponer
**todos los candidatos con un score/ranking** (campo "gancho 1-5" en el tool schema)
da más material para elegir en el editor. Cambio chico, encaja en el Track 2.

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
