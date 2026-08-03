/**
 * Verifica la sincronía sin abrir el Studio.
 *
 *   npm run cues
 *
 * Muestra, para cada palabra-cue, en qué momento del VO cayó y si matcheó
 * de verdad o quedó interpolada. Y avisa de los huecos: tramos largos sin
 * cambio de estado (la regla del proyecto es 150 frames / 5s).
 */
import { BLOCKS, EPISODE_TOTAL, RESOLVED, cueReport } from '../src/shared/cues';
import { CAPTIONS } from '../src/shared/captions';

const FPS = 30;
const tc = (f: number) => `${Math.floor(f / FPS / 60)}:${String(Math.floor((f / FPS) % 60)).padStart(2, '0')}`;

const voSecs = CAPTIONS.length ? CAPTIONS[CAPTIONS.length - 1].endMs / 1000 : 0;
console.log(
  CAPTIONS.length
    ? `\nVO: ${CAPTIONS.length} palabras · ${voSecs.toFixed(1)}s`
    : '\nVO: sin transcribir todavía — los cues caen en sus frames tentativos.',
);
console.log(`Episodio: ${EPISODE_TOTAL} frames (${tc(EPISODE_TOTAL)})\n`);

console.log('BLOQUES');
BLOCKS.forEach((b) => {
  console.log(
    `  ${b.key.toUpperCase()}  ${tc(b.start)} → ${tc(b.start + b.duration)}  (${b.duration}f)`,
  );
});

console.log('\nCUES');
let last = 0;
cueReport().forEach((c) => {
  const flag = c.source === 'audio' ? 'ok  ' : 'INT ';
  console.log(
    `  ${flag} ${c.block}  ${c.time.padEnd(6)} f=${String(c.frame).padStart(5)}  rel=${String(c.relative).padStart(5)}  "${c.needle}"`,
  );
  last = c.frame;
});

const missed = RESOLVED.filter((c) => c.source !== 'audio');
console.log(
  missed.length
    ? `\n⚠ ${missed.length} cue(s) sin matchear (interpolados): ${missed.map((c) => c.needle).join(', ')}`
    : `\n✓ Los ${RESOLVED.length} cues matchearon contra el audio.`,
);

// Huecos: cuánto aguanta la pantalla sin un cambio de estado.
const marks = [0, ...RESOLVED.map((c) => c.frame), EPISODE_TOTAL];
const gaps: string[] = [];
for (let i = 1; i < marks.length; i++) {
  const gap = marks[i] - marks[i - 1];
  if (gap > 150) gaps.push(`  ${tc(marks[i - 1])} → ${tc(marks[i])}  (${gap}f / ${(gap / FPS).toFixed(1)}s)`);
}
console.log(gaps.length ? `\n⚠ Tramos sin cue > 5s:\n${gaps.join('\n')}` : '\n✓ Ningún tramo sin cue mayor a 5s.');
console.log(`\n(último cue en ${tc(last)})\n`);
