import React from 'react';
import { Composition } from 'remotion';
import { CANVAS } from './theme';
import { EPISODE_TOTAL } from './shared/cues';
import { EpisodeMaster, episodeSchema } from './compositions/EpisodeMaster';

// ═══════════════════════════════════════════════════════════════
// TODO EL COPY VIVE ACÁ.
// Corregir un texto no debería obligar a tocar animación.
// ═══════════════════════════════════════════════════════════════
/**
 * Vacío hasta que exista la grabación: el esqueleto se puede componer sin
 * VO y todo cae a silencio. Cuando `npm run ingest` deje el archivo en
 * public/audio/, poner 'audio/vo.mp3' acá y transcribir.
 */
const VO = '';

/**
 * A-roll. Vacío = el pane de abajo lo ocupa el motivo animado. En cuanto
 * existan los clips (van a _entrada/aroll/ y los copia `npm run ingest`)
 * se completa el path y el bloque vuelve al split con rostro.
 */
const AROLL = {
  b1: '', // video/aroll-b1.mp4
};

const B1 = {
  arollSrc: AROLL.b1,
  tesis: 'La tesis del episodio,\nen una línea.',
  dato: 'El dato que la sostiene.',
};

const B2 = {
  giro: 'El giro.',
  cierre: 'Lo que se lleva el espectador.',
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="EpisodeMaster"
    component={EpisodeMaster}
    schema={episodeSchema}
    durationInFrames={EPISODE_TOTAL}
    fps={CANVAS.fps}
    width={CANVAS.width}
    height={CANVAS.height}
    defaultProps={{ voSrc: VO, b1: B1, b2: B2 }}
  />
);
