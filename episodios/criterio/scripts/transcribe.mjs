/**
 * Corre la transcripción con el Python correcto.
 *
 *   npm run transcribe
 *
 * faster-whisper vive en el .venv del repo, no en el Python del sistema:
 * llamar a `python` a secas fallaba con ModuleNotFoundError. Esto busca el
 * venv del repo primero y cae al Python del sistema si no está.
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const candidates = [
  resolve('../../.venv/Scripts/python.exe'), // Windows, venv del repo
  resolve('../../.venv/bin/python'), // macOS / Linux, venv del repo
  resolve('.venv/Scripts/python.exe'),
  resolve('.venv/bin/python'),
];

const python = candidates.find((p) => existsSync(p)) ?? 'python';
if (python === 'python') {
  console.log('⚠️  No encontré el .venv del repo; uso el Python del sistema.');
  console.log('   Si falla con ModuleNotFoundError: pip install faster-whisper');
}

const args = process.argv.slice(2);
const res = spawnSync(
  python,
  ['scripts/transcribe_fw.py', ...(args.length ? args : ['public/audio/vo-criterio.mp3', 'public/captions.json'])],
  { stdio: 'inherit', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } },
);

process.exit(res.status ?? 1);
