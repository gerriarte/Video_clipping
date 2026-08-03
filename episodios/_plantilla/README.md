# Plantilla de episodio

Base para un episodio vertical nuevo. **No se edita acá**: se copia.

```bash
cp -r episodios/_plantilla episodios/<nombre>
cd episodios/<nombre> && npm install
npm run dev        # arranca aunque todavía no haya VO
```

Renderiza tal cual, con dos bloques de ejemplo, para que se vea el
sistema funcionando antes de escribir nada.

## Qué trae ya resuelto

| Pieza | Archivo | Qué hace |
|---|---|---|
| Reloj del episodio | `src/shared/cues.ts` | Resuelve cada visual contra una palabra del VO y reparte los bloques |
| Medición de la voz | `src/shared/voice.tsx` | Energía, espectro y onda del VO, una vez por frame |
| Textura de fondo | `src/shared/Backdrop.tsx` | Trama que respira con la voz, retícula, reloj, folio |
| Pane sin rostro | `src/components/MotionPane.tsx` | La voz dibujada + el motivo del bloque |
| Subtítulos | `src/shared/Subtitles.tsx` | Sobrios, sin karaoke, banda según el modo |
| Verificación | `npm run cues` | Qué cue cayó en qué segundo y cuál no matcheó |

## Los tres pasos

**1 · El esqueleto, sin VO.** `src/shared/cues.ts` con un cue por estado
visual y un `planned` tentativo; los bloques en
`src/compositions/EpisodeMaster.tsx`; el copy en `src/Root.tsx`. Con
`VO = ''` todo cae a silencio y se puede componer igual.

**2 · Llega la grabación.** Va a `_entrada/vo.mp3`; después:

```bash
npm run ingest && npm run transcribe && npm run cues
```

`npm run cues` dice cuál matcheó y cuál quedó interpolado. Los que no
matchearon se corrigen cambiando el **`needle`**, nunca un frame. Poner
`VO = 'audio/vo.mp3'` en `src/Root.tsx`.

**3 · Render.** `npm run render` → `out/`.

## Lo que hay que entender antes de tocar

`useCue()` devuelve frames **relativos al bloque**. Los cues se resuelven
contra el audio completo, pero adentro de una `<Series.Sequence>` el frame
vuelve a cero: de eso se encarga `<CueScope>`, que envuelve cada bloque
con su frame de inicio. **Si un bloque sale en negro, mirá primero si está
adentro de su `CueScope`.**

Y **ningún bloque pinta su propio fondo**: el negro y la textura los pone
el `<Backdrop>`. Un `AbsoluteFill` opaco adentro de un bloque lo tapa
entero.

## Reglas del sistema de diseño

Están en `src/theme.ts`. Resumen:

- **Acento rojo: presupuesto cerrado** (en Criterio fueron 4 usos en 4:31).
  Marcá cada uso en el código con `USO n/N`. Uno de más es un bug.
- **Nada legible por debajo de `y = 1570`** — ahí va el caption de la
  plataforma. La banda de subtítulos va en 980 (con pane de abajo) o 1320
  (a pane completo).
- **Trazo mínimo 2px.** A 1080 de ancho, 1px titila tras la compresión.
- **`linear` solo en tres lugares**: el dash del acento, el grano y el
  reloj del episodio.
- **Sin karaoke, sin amarillo, sin stroke negro** en los subtítulos.
- El fondo no compite: nada del Backdrop por encima de 0.10 de opacidad.

## Transcripción

`npm run transcribe` usa faster-whisper con el `.venv` del repo
(`../../.venv`, modelo `large-v2` ya cacheado). Si no lo encuentra, cae al
Python del sistema y avisa. `npm run transcribe:whispercpp` es la
alternativa autocontenida, pero baja ~1.5 GB.
