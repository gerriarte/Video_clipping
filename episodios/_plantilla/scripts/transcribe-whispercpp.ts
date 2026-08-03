/**
 * Genera public/captions.json a partir del VO.
 *
 * Este script es la pieza central del flujo: las animaciones se anclan
 * a palabras, no a frames. Cuando regrabes el VO definitivo, corrés
 * esto de nuevo y todo el episodio se reacomoda solo.
 *
 *   npx tsx scripts/transcribe.ts
 */
import path from 'path';
import fs from 'fs';
import { execSync } from 'child_process';
import {
  downloadWhisperModel,
  installWhisperCpp,
  toCaptions,
  transcribe,
} from '@remotion/install-whisper-cpp';

const WHISPER_VERSION = '1.5.5';
const MODEL = 'medium'; // multilingüe: el VO es en español
const to = path.join(process.cwd(), 'whisper.cpp');

// npx tsx scripts/transcribe.ts public/audio/vo.mp3 public/captions.json
const SOURCE = process.argv[2] ?? 'public/audio/vo.mp3';
const OUT = process.argv[3] ?? 'public/captions.json';
const WAV = 'public/audio/_vo-16k.wav';

const main = async () => {
  await installWhisperCpp({ to, version: WHISPER_VERSION });
  await downloadWhisperModel({ model: MODEL, folder: to });

  // Whisper.cpp exige 16 kHz mono.
  console.log('→ Convirtiendo a 16 kHz mono…');
  execSync(`ffmpeg -i "${SOURCE}" -ar 16000 -ac 1 "${WAV}" -y`, { stdio: 'inherit' });

  console.log('→ Transcribiendo…');
  const whisperCppOutput = await transcribe({
    model: MODEL,
    whisperPath: to,
    whisperCppVersion: WHISPER_VERSION,
    inputPath: path.join(process.cwd(), WAV),
    tokenLevelTimestamps: true,
    language: 'es',
  });

  const { captions } = toCaptions({ whisperCppOutput });
  fs.writeFileSync(OUT, JSON.stringify(captions, null, 2));

  const dur = captions.length ? captions[captions.length - 1].endMs / 1000 : 0;
  console.log(`✓ ${captions.length} tokens → ${OUT}`);
  console.log(`  Duración del VO: ${dur.toFixed(1)}s (${Math.ceil(dur * 30)} frames a 30fps)`);
  console.log(`  Objetivo: 300.0s / 9000 frames`);
};

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
