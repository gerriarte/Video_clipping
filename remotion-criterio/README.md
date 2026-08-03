# Episodio · Criterio

Vertical 9:16, 1080×1920 a 30 fps. **La animación está atada al VO**: no
hay un solo frame escrito a mano en las composiciones.

```bash
npm install
npm run cues      # qué cue cayó en qué segundo del audio
npm run dev       # Remotion Studio
npm run render    # → out/criterio.mp4
```

## Cómo funciona la sincronía

```
public/audio/vo-criterio.mp3
        ↓  npm run transcribe        (faster-whisper, palabra por palabra)
public/captions.json
        ↓  src/shared/cues.ts        (tabla de cues + reparto de bloques)
CUE_FRAMES · BLOCKS
        ↓  useCue('c3.filter', …)    en cada composición
```

**`src/shared/cues.ts` es el reloj del episodio.** Ahí vive `CUE_SCRIPT`:
una fila por estado visual, con la palabra que lo dispara y el frame
planificado original. La resolución hace tres cosas:

1. **Matchea hacia adelante.** Cada cue se busca desde donde terminó el
   anterior. Por eso "existe" puede aparecer dos veces en el guion y cada
   una dispara su propia etiqueta: el orden es parte del contrato.
2. **Interpola lo que no matchea.** Si una palabra no está en la
   transcripción, se ubica proporcionalmente entre los dos vecinos que sí
   matchearon. Un cue perdido corre un visual; no rompe el bloque.
3. **Garantiza aire mínimo** entre cues, para que ninguna `<Sequence>`
   quede con duración cero.

Los bloques **no duran lo que decía el plan**: cada uno arranca 18 frames
antes de su primera palabra y termina donde arranca el siguiente. El
episodio entero dura lo que dura el VO.

### El detalle que hace falta entender para tocar esto

`useCue()` devuelve frames **relativos al bloque**, no absolutos. Los cues
se resuelven contra el audio completo, pero adentro de una
`<Series.Sequence>` el frame vuelve a cero. De eso se encarga `<CueScope>`,
que envuelve cada bloque en `CriterioMaster` y le pasa su frame de inicio.
Si un bloque aparece en negro, lo primero a mirar es si está adentro de su
`CueScope`.

## Si se regraba el VO

```bash
cp nuevo-vo.mp3 public/audio/vo-criterio.mp3
npm run transcribe
npm run cues        # verificar que sigan matcheando los 39 cues
npm run render
```

No se toca una línea de animación. Si cambió una formulación, se corrige
el `needle` en `CUE_SCRIPT` — **nunca un frame**.

`npm run transcribe` usa faster-whisper con el `.venv` del repo padre
(modelo `large-v2`, ya cacheado). `npm run transcribe:whispercpp` es la
alternativa autocontenida, pero se baja ~1.5 GB de whisper.cpp.

## A-roll

Todavía no hay clips a cámara, así que el episodio corre a pantalla
completa. Los paths están vacíos en `src/Root.tsx`:

| Constante | Archivo esperado | Cubre |
|---|---|---|
| `AROLL.c1` | `public/video/criterio-aroll-1.mp4` | C1 · ~50s |
| `AROLL.c4` | `public/video/criterio-aroll-2.mp4` | C4 · ~55s |
| `AROLL.c5` | `public/video/criterio-aroll-3.mp4` | C5 · ~75s, de corrido |

Completándolos, C1, C4 y C5 vuelven solos al split que diseñó el guion
(el componente maneja la salida y el reingreso del rostro en C5 con
`exitAt` / `startFrom`). Al pasar a split hay que sacarle el `band` al
`<Subtitles>` de `CriterioMaster`: en split la banda va en 980.

**Encuadre:** los ojos tienen que caer en `y ≈ 1290` del canvas de 1920.
Se ajusta con `offsetY` y `scale` en cada `<FacePane>`.

## Reglas que no son opcionales

Están en `src/theme.ts` y comentadas en cada componente:

- **Acento rojo: exactamente 4 usos.** C1 (el corte en 45 años), C3
  ("Costumbre"), C4 (el tramo de vida productiva descartado), C5 (el
  solape de los dos círculos). Un quinto uso es un bug.
- **Nada legible por debajo de `y = 1570`** — ahí va el caption de la
  plataforma. En modo full la banda de subtítulos va en 1320.
- **Trazo mínimo 2px.** A 1080 de ancho, 1px titila tras la compresión.
- **`linear` solo en dos lugares**: el dash del borde rojo y el
  desplazamiento del grano.
- Sin karaoke, sin amarillo, sin stroke negro en los subtítulos: son
  accesibilidad, no retención.

## Estructura

```
src/
  shared/
    captions.ts   Carga de captions.json + matcheo de palabras
    cues.ts       ★ Tabla de cues, resolución y reparto de bloques
    useCue.tsx    Hook + <CueScope>
    FacePane.tsx  Panes split / full / solo + barra de marca
    anim.tsx      Reveal, FadeUp, Counter, useDraw…
  components/
    Criterio.tsx  Los visuales del episodio
  compositions/criterio/
    C1_C2_C3.tsx  C1 Arranque · C2 Qué es · C3 Precio
    C4_C5.tsx     C4 Absurdo · C5 Salida
    CriterioMaster.tsx
scripts/
  transcribe_fw.py  VO → captions.json (faster-whisper)
  check-cues.ts     npm run cues
```
