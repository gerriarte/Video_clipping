/**
 * Toma lo que hay en _entrada/ y lo deja donde el proyecto lo espera.
 *
 *   npm run ingest        (copia + transcribe + verifica cues)
 *
 * El VO vive en _entrada/ —es material de entrada, no un asset del
 * proyecto— y Remotion solo puede leer de public/. Esto es el puente, y
 * evita tener el mismo mp3 dos veces en git.
 */
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const pairs = [
  { from: '_entrada/vo.mp3', to: 'public/audio/vo-criterio.mp3', required: true },
];

/** Carpetas que se copian enteras si tienen algo adentro. */
const dirs = [
  { from: '_entrada/aroll', to: 'public/video' },
  { from: '_entrada/assets', to: 'public/assets' },
];

let copied = 0;

for (const { from, to, required } of pairs) {
  if (!existsSync(from)) {
    if (required) {
      console.error(`✗ Falta ${from}. Ver ../COMO-ENTREGAR.md`);
      process.exit(1);
    }
    continue;
  }
  mkdirSync(to.split('/').slice(0, -1).join('/'), { recursive: true });
  copyFileSync(from, to);
  console.log(`→ ${from}  →  ${to}`);
  copied++;
}

for (const { from, to } of dirs) {
  if (!existsSync(from)) continue;
  const files = readdirSync(from).filter((f) => statSync(join(from, f)).isFile());
  if (!files.length) continue;
  mkdirSync(to, { recursive: true });
  for (const f of files) {
    copyFileSync(join(from, f), join(to, f));
    console.log(`→ ${from}/${f}  →  ${to}/${f}`);
    copied++;
  }
}

console.log(`\n✓ ${copied} archivo(s). Ahora: npm run transcribe && npm run cues`);
