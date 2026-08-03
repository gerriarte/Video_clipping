import captionsRaw from '../../public/captions.json';

export type Caption = {
  text: string;
  startMs: number;
  endMs: number;
  timestampMs: number | null;
  confidence: number | null;
};

export const CAPTIONS = captionsRaw as Caption[];

/** Minúsculas, sin tildes ni puntuación: el matcheo no debe depender de eso. */
export const norm = (s: string) =>
  s
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\w\s]/g, '');

const NORMALIZED = CAPTIONS.map((c) => norm(c.text));

/**
 * Índice del primer caption donde arranca `needle`, buscando desde `from`.
 *
 * Busca hacia adelante y nunca hacia atrás: el guion se pronuncia en orden,
 * así que una palabra que también aparece antes no puede robarle el cue a
 * la de después. (Sin esto, `identidad` del C5 matchearía con cualquier
 * mención suelta anterior y el bloque entero se iría al principio.)
 */
export const findFrom = (needle: string, from = 0): number => {
  const target = norm(needle);
  if (!target || CAPTIONS.length === 0) return -1;

  const words = target.split(/\s+/);

  for (let i = Math.max(0, from); i <= CAPTIONS.length - 1; i++) {
    if (words.length === 1) {
      if (NORMALIZED[i].includes(target)) return i;
      continue;
    }
    if (i + words.length > CAPTIONS.length) break;
    const window = NORMALIZED.slice(i, i + words.length);
    // Solo "la palabra del audio contiene la del cue" —nunca al revés—: si
    // se acepta el revés, un "a" suelto matchea con "años" y el cue se va
    // veinte segundos antes de donde va.
    if (window.every((w, j) => w.includes(words[j]))) return i;
  }
  return -1;
};

export const msToFrame = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

/** Frame en que termina la última palabra del VO. */
export const captionsDurationInFrames = (fps: number): number | null => {
  if (CAPTIONS.length === 0) return null;
  return Math.ceil((CAPTIONS[CAPTIONS.length - 1].endMs / 1000) * fps);
};
