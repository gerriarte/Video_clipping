/**
 * EL RELOJ DEL EPISODIO.
 *
 * Nada de lo que se ve está atado a un frame escrito a mano: cada estado
 * visual cuelga de una palabra del VO. Acá se resuelven todas las palabras
 * contra la transcripción y se reparten los cinco bloques.
 *
 * Si se regraba el VO: `npm run transcribe:criterio && npm run cues`. Si
 * cambió una formulación, se toca el `needle` de esta tabla — nunca un
 * frame de una composición.
 */
import { CANVAS } from '../theme';
import { CAPTIONS, findFrom, msToFrame } from './captions';

const FPS = CANVAS.fps;

export type BlockKey = 'c1' | 'c2' | 'c3' | 'c4' | 'c5';

/**
 * Las palabras que disparan cada estado, EN EL ORDEN EN QUE SE PRONUNCIAN.
 * El orden es parte del contrato: cada cue se busca desde donde terminó el
 * anterior, así una palabra repetida no le roba el disparo a la de después.
 *
 * `planned` es el reparto original de 9000 frames. Ya no manda el timing:
 * solo sirve para ubicar proporcionalmente un cue que no matchee.
 */
export const CUE_SCRIPT = [
  // ── C1 · Arranque ──────────────────────────────────────────
  { block: 'c1', id: 'c1.pair', needle: '10 años', planned: 60 },
  { block: 'c1', id: 'c1.gap', needle: '45', planned: 300 },
  { block: 'c1', id: 'c1.qual1', needle: 'impecable', planned: 600 },
  { block: 'c1', id: 'c1.qual2', needle: 'perfecto', planned: 654 },
  { block: 'c1', id: 'c1.qual3', needle: 'pulido', planned: 708 },
  { block: 'c1', id: 'c1.question', needle: 'descarta', planned: 900 },

  // ── C2 · Qué es esto en serio ──────────────────────────────
  { block: 'c2', id: 'c2.negation', needle: 'no es información', planned: 1410 },
  { block: 'c2', id: 'c2.definition', needle: 'error acumulado', planned: 1530 },
  { block: 'c2', id: 'c2.sup1', needle: 'decisión', planned: 1620 },
  { block: 'c2', id: 'c2.sup2', needle: 'equivocarte', planned: 1680 },
  { block: 'c2', id: 'c2.sup3', needle: 'cuerpo', planned: 1740 },
  { block: 'c2', id: 'c2.columns', needle: 'nunca perdió un cliente', planned: 1830 },
  { block: 'c2', id: 'c2.closing', needle: 'consecuencias', planned: 2370 },

  // ── C3 · Lo que cambió de precio ───────────────────────────
  { block: 'c3', id: 'c3.cross', needle: 'tendió a cero', planned: 2760 },
  { block: 'c3', id: 'c3.scarcity', needle: 'escaso', planned: 3120 },
  { block: 'c3', id: 'c3.trap', needle: 'trampa', planned: 3360 },
  { block: 'c3', id: 'c3.filter', needle: 'costumbre', planned: 3480 },
  { block: 'c3', id: 'c3.pass1', needle: 'datos incompletos', planned: 3540 },
  { block: 'c3', id: 'c3.pass2', needle: 'explicar', planned: 3588 },
  { block: 'c3', id: 'c3.pass3', needle: 'conviene', planned: 3636 },
  { block: 'c3', id: 'c3.closing', needle: 'disparó', planned: 4200 },

  // ── C4 · El absurdo ────────────────────────────────────────
  { block: 'c4', id: 'c4.life', needle: 'lo tira', planned: 4560 },
  { block: 'c4', id: 'c4.cut', needle: 'los 65', planned: 4860 },
  { block: 'c4', id: 'c4.pivot', needle: 'de vos', planned: 5220 },
  { block: 'c4', id: 'c4.tag1', needle: 'sueldos de guerra', planned: 5460 },
  { block: 'c4', id: 'c4.tag2', needle: 'remate', planned: 5532 },
  { block: 'c4', id: 'c4.verdict', needle: 'ingrediente equivocado', planned: 6300 },

  // ── C5 · La traba y la salida ──────────────────────────────
  { block: 'c5', id: 'c5.barrier', needle: 'identidad', planned: 6810 },
  { block: 'c5', id: 'c5.key', needle: '20 dólares', planned: 7050 },
  { block: 'c5', id: 'c5.mirror', needle: 'caro y lento', planned: 7290 },
  { block: 'c5', id: 'c5.mirror2', needle: 'era lo difícil', planned: 7380 },
  { block: 'c5', id: 'c5.halves', needle: 'desarmados', planned: 7650 },
  { block: 'c5', id: 'c5.left', needle: 'existe', planned: 7700 },
  { block: 'c5', id: 'c5.right', needle: 'existe', planned: 7750 },
  { block: 'c5', id: 'c5.merge', needle: 'pueden', planned: 7950 },
  { block: 'c5', id: 'c5.questions', needle: 'último trimestre', planned: 8430 },
  { block: 'c5', id: 'c5.q1', needle: 'producís', planned: 8490 },
  { block: 'c5', id: 'c5.q2', needle: 'ejecución', planned: 8580 },
  { block: 'c5', id: 'c5.verdict', needle: 'plata', planned: 8700 },
] as const satisfies readonly { block: BlockKey; id: string; needle: string; planned: number }[];

export type CueId = (typeof CUE_SCRIPT)[number]['id'];

const PLANNED_TOTAL = 9000;
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
  /** Cómo se ubicó: por audio, o interpolado entre vecinos que sí matchearon. */
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

  // 2) Los que no matchearon se ubican proporcionalmente entre los vecinos
  //    que sí. Un cue perdido corre su visual; no rompe el bloque entero.
  const audioFrames = CAPTIONS.length
    ? msToFrame(CAPTIONS[CAPTIONS.length - 1].endMs, FPS)
    : PLANNED_TOTAL;
  const scale = audioFrames / PLANNED_TOTAL;

  const filled: ResolvedCue[] = raw.map((cue, i) => {
    if (cue.frame !== null) {
      return { ...cue, frame: cue.frame, source: 'audio' };
    }

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

/** Frame en que termina la última palabra del VO, más la cola. */
export const VO_END =
  (CAPTIONS.length ? msToFrame(CAPTIONS[CAPTIONS.length - 1].endMs, FPS) : PLANNED_TOTAL) + TAIL;

export type Block = { key: BlockKey; start: number; duration: number };

/**
 * Los bloques no duran lo que decía el plan: duran lo que tarda el VO en
 * decirlos. Cada uno arranca un pelo antes de su primera palabra.
 */
const buildBlocks = (): Block[] => {
  const keys: BlockKey[] = ['c1', 'c2', 'c3', 'c4', 'c5'];

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
    // El último se estira hasta el final del VO, con margen por si la
    // composición se calcula con la duración del archivo de audio.
    duration: (i < keys.length - 1 ? starts[i + 1] : VO_END + 90) - starts[i],
  }));
};

export const BLOCKS: Block[] = buildBlocks();

export const BLOCK_START = Object.fromEntries(BLOCKS.map((b) => [b.key, b.start])) as Record<
  BlockKey,
  number
>;

export const BLOCK = Object.fromEntries(BLOCKS.map((b) => [b.key, b])) as Record<BlockKey, Block>;

export const CRITERIO_TOTAL = VO_END;

/** Para `npm run cues`: qué matcheó, qué no, y dónde cae cada cosa. */
export const cueReport = () =>
  RESOLVED.map((c) => ({
    ...c,
    time: `${Math.floor(c.frame / FPS / 60)}:${String(Math.floor((c.frame / FPS) % 60)).padStart(2, '0')}`,
    relative: c.frame - BLOCK_START[c.block],
  }));
