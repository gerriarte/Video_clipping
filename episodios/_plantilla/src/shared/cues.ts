/**
 * EL RELOJ DEL EPISODIO.  ← ESTE ES EL ARCHIVO QUE SE EDITA POR EPISODIO
 *
 * Nada de lo que se ve está atado a un frame escrito a mano: cada estado
 * visual cuelga de una palabra del VO. Acá se resuelven todas las palabras
 * contra la transcripción y se reparten los bloques.
 *
 * Flujo: `npm run ingest` → `npm run transcribe` → `npm run cues`.
 * Si cambió una formulación al grabar, se toca el `needle` de esta tabla
 * — nunca un frame de una composición.
 *
 * Sin captions.json (o vacío) todo cae en los frames `planned` y el
 * episodio se puede previsualizar igual.
 */
import { CANVAS } from '../theme';
import { CAPTIONS, findFrom, msToFrame } from './captions';

const FPS = CANVAS.fps;

/** Un id por bloque del episodio. Se renombran a gusto. */
export type BlockKey = 'b1' | 'b2';

/**
 * Las palabras que disparan cada estado, EN EL ORDEN EN QUE SE PRONUNCIAN.
 * El orden es parte del contrato: cada cue se busca desde donde terminó el
 * anterior, así una palabra repetida no le roba el disparo a la de después.
 *
 * `planned` es un reparto tentativo en frames. No manda el timing: solo
 * ubica proporcionalmente un cue que no matchee (y sostiene el preview
 * antes de que exista el VO).
 */
export const CUE_SCRIPT = [
  { block: 'b1', id: 'b1.tesis', needle: 'REEMPLAZAR', planned: 60 },
  { block: 'b1', id: 'b1.dato', needle: 'REEMPLAZAR', planned: 420 },
  { block: 'b2', id: 'b2.giro', needle: 'REEMPLAZAR', planned: 900 },
  { block: 'b2', id: 'b2.cierre', needle: 'REEMPLAZAR', planned: 1500 },
] as const satisfies readonly { block: BlockKey; id: string; needle: string; planned: number }[];

export type CueId = (typeof CUE_SCRIPT)[number]['id'];

/** Duración tentativa del episodio en frames, mientras no haya VO. */
const PLANNED_TOTAL = 1800;
/** Aire mínimo entre dos cues: por debajo, una <Sequence> quedaría en cero. */
const MIN_GAP = 18;
/** Cuánto antes de su primera palabra arranca cada bloque. */
const LEAD = 18;
/** Cola después de la última palabra del VO. */
const TAIL = 72;

export type ResolvedCue = {
  block: BlockKey;
  id: CueId;
  needle: string;
  planned: number;
  frame: number;
  source: 'audio' | 'interpolado';
};

const resolve = (): ResolvedCue[] => {
  const raw = CUE_SCRIPT.map((c) => ({ ...c, frame: null as number | null }));

  // 1) Matcheo hacia adelante contra la transcripción.
  let cursor = 0;
  raw.forEach((cue) => {
    const idx = findFrom(cue.needle, cursor);
    if (idx >= 0) {
      cue.frame = msToFrame(CAPTIONS[idx].startMs, FPS);
      cursor = idx + 1;
    }
  });

  // 2) Lo que no matcheó se ubica proporcionalmente entre los vecinos que
  //    sí. Un cue perdido corre su visual; no rompe el bloque entero.
  const audioFrames = CAPTIONS.length
    ? msToFrame(CAPTIONS[CAPTIONS.length - 1].endMs, FPS)
    : PLANNED_TOTAL;
  const scale = audioFrames / PLANNED_TOTAL;

  const filled: ResolvedCue[] = raw.map((cue, i) => {
    if (cue.frame !== null) return { ...cue, frame: cue.frame, source: 'audio' };

    let prev: (typeof raw)[number] | null = null;
    for (let j = i - 1; j >= 0; j--) if (raw[j].frame !== null) { prev = raw[j]; break; }
    let next: (typeof raw)[number] | null = null;
    for (let j = i + 1; j < raw.length; j++) if (raw[j].frame !== null) { next = raw[j]; break; }

    let frame: number;
    if (prev && next) {
      const t = (cue.planned - prev.planned) / (next.planned - prev.planned);
      frame = Math.round(prev.frame! + t * (next.frame! - prev.frame!));
    } else if (prev) {
      frame = Math.round(prev.frame! + (cue.planned - prev.planned) * scale);
    } else if (next) {
      frame = Math.round(next.frame! * (cue.planned / next.planned));
    } else {
      frame = Math.round(cue.planned * scale);
    }
    return { ...cue, frame, source: 'interpolado' };
  });

  // 3) Monotonía y aire mínimo: dos cues en el mismo frame dejan una
  //    <Sequence> de duración cero y Remotion tira error.
  for (let i = 1; i < filled.length; i++) {
    if (filled[i].frame < filled[i - 1].frame + MIN_GAP) {
      filled[i] = { ...filled[i], frame: filled[i - 1].frame + MIN_GAP };
    }
  }

  return filled;
};

export const RESOLVED: ResolvedCue[] = resolve();

/** id → frame absoluto del episodio. */
export const CUE_FRAMES: Record<string, number> = Object.fromEntries(
  RESOLVED.map((c) => [c.id, c.frame]),
);

export const VO_END =
  (CAPTIONS.length ? msToFrame(CAPTIONS[CAPTIONS.length - 1].endMs, FPS) : PLANNED_TOTAL) + TAIL;

export type Block = { key: BlockKey; start: number; duration: number };

/**
 * Los bloques no duran lo que decía el plan: duran lo que tarda el VO en
 * decirlos. Cada uno arranca un pelo antes de su primera palabra.
 */
const buildBlocks = (): Block[] => {
  const keys = [...new Set(CUE_SCRIPT.map((c) => c.block))] as BlockKey[];

  const starts = keys.map((key, i) => {
    if (i === 0) return 0;
    const first = RESOLVED.find((c) => c.block === key);
    return Math.max(0, (first?.frame ?? 0) - LEAD);
  });

  for (let i = 1; i < starts.length; i++) {
    if (starts[i] <= starts[i - 1]) starts[i] = starts[i - 1] + MIN_GAP * 2;
  }

  return keys.map((key, i) => ({
    key,
    start: starts[i],
    duration: (i < keys.length - 1 ? starts[i + 1] : VO_END + 90) - starts[i],
  }));
};

export const BLOCKS: Block[] = buildBlocks();

export const BLOCK_START = Object.fromEntries(BLOCKS.map((b) => [b.key, b.start])) as Record<
  BlockKey,
  number
>;

export const BLOCK = Object.fromEntries(BLOCKS.map((b) => [b.key, b])) as Record<BlockKey, Block>;

export const EPISODE_TOTAL = VO_END;

/** Para `npm run cues`: qué matcheó, qué no, y dónde cae cada cosa. */
export const cueReport = () =>
  RESOLVED.map((c) => ({
    ...c,
    time: `${Math.floor(c.frame / FPS / 60)}:${String(Math.floor((c.frame / FPS) % 60)).padStart(2, '0')}`,
    relative: c.frame - BLOCK_START[c.block],
  }));
