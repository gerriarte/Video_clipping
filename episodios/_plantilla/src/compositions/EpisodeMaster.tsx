import React from 'react';
import { AbsoluteFill, Audio, Sequence, Series, staticFile, useCurrentFrame } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, TYPE } from '../theme';
import { Backdrop, BackdropTop } from '../shared/Backdrop';
import { Subtitles } from '../shared/Subtitles';
import { VoiceProvider } from '../shared/voice';
import { VoiceRibbon } from '../shared/VoiceTrace';
import { AnimPane, BrandBar, FacePane } from '../shared/FacePane';
import { DiagonalWipe } from '../shared/DiagonalWipe';
import { Reveal } from '../shared/anim';
import { MotionPane, type Motif } from '../components/MotionPane';
import { BLOCK, BLOCKS, EPISODE_TOTAL } from '../shared/cues';
import { CueScope, useCue } from '../shared/useCue';

// ═══════════════════════════════════════════════════════════════
// ESQUELETO DE EPISODIO
//
// Dos bloques de ejemplo que muestran las tres piezas del sistema:
// el cue que dispara el visual, el pane de abajo sin rostro, y el
// reparto de bloques que sale del audio. Reemplazar por los bloques
// reales del episodio; la maquinaria no se toca.
// ═══════════════════════════════════════════════════════════════

const EP = 'Episodio · REEMPLAZAR';

/** Con A-roll, el rostro; sin A-roll, el motivo animado con la voz. */
const BottomPane: React.FC<{ arollSrc?: string; motif: Motif }> = ({ arollSrc, motif }) =>
  arollSrc ? (
    <FacePane src={arollSrc} offsetY={-180} scale={1.15} />
  ) : (
    <MotionPane motif={motif} />
  );

export const b1Schema = z.object({
  arollSrc: z.string().optional(),
  tesis: z.string(),
  dato: z.string(),
});

/** Bloque en SPLIT: placa arriba, pane de abajo con el motivo. */
export const B1: React.FC<z.infer<typeof b1Schema>> = ({ arollSrc, tesis, dato }) => {
  const fTesis = useCue('b1.tesis', 60);
  const fDato = useCue('b1.dato', 420);

  return (
    <AbsoluteFill>
      <BrandBar episode={EP} />
      <AnimPane mode="split">
        <Sequence durationInFrames={fDato - 12} name="tesis">
          <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
            <Reveal at={fTesis} style={{ ...TYPE.displayXL }}>
              {tesis}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
        <Sequence from={fDato - 12} name="dato">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
            <Reveal at={24} style={{ ...TYPE.displayL }}>
              {dato}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
      </AnimPane>
      <BottomPane arollSrc={arollSrc} motif="filter" />
    </AbsoluteFill>
  );
};

export const b2Schema = z.object({
  giro: z.string(),
  cierre: z.string(),
});

/** Bloque a pane COMPLETO: el visual ocupa el alto entero. */
export const B2: React.FC<z.infer<typeof b2Schema>> = ({ giro, cierre }) => {
  const fGiro = useCue('b2.giro', 900);
  const fCierre = useCue('b2.cierre', 1500);

  return (
    <AbsoluteFill>
      <BrandBar episode={EP} />
      <AnimPane mode="full">
        <Sequence durationInFrames={fCierre - fGiro} name="giro">
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 200, width: 936 }}>
            <Reveal at={24} style={{ ...TYPE.displayXL }}>
              {giro}
            </Reveal>
          </div>
        </Sequence>
        <Sequence from={fCierre - fGiro} name="cierre">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
            <Reveal at={24} style={{ ...TYPE.displayL }}>
              {cierre}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
      </AnimPane>
    </AbsoluteFill>
  );
};

export const episodeSchema = z.object({
  voSrc: z.string(),
  b1: b1Schema,
  b2: b2Schema,
});

export { EPISODE_TOTAL };

/** Tramos a pane completo: ahí baja la banda de subtítulos. */
const fullRanges = (): [number, number][] => [[BLOCK.b2.start, EPISODE_TOTAL]];

const useStage = () => {
  const frame = useCurrentFrame();
  const blockIndex = Math.max(
    0,
    BLOCKS.findIndex((b) => frame >= b.start && frame < b.start + b.duration),
  );
  const isFull = fullRanges().some(([a, b]) => frame >= a && frame < b);
  return { blockIndex, isFull };
};

/**
 * Cada bloque va envuelto en <CueScope>, que le dice en qué frame absoluto
 * del episodio arranca. Sin eso los cues —que se resuelven contra el audio
 * completo— apuntarían a frames que adentro de la <Series.Sequence> no
 * existen, y el bloque se quedaría en negro.
 *
 * Y ningún bloque pinta su propio fondo: el negro y la textura los pone el
 * <Backdrop>. Un AbsoluteFill opaco adentro de un bloque lo tapa entero.
 */
const Episode: React.FC<z.infer<typeof episodeSchema>> = ({ b1, b2 }) => {
  const { blockIndex, isFull } = useStage();

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <Backdrop total={EPISODE_TOTAL} blockIndex={blockIndex} blockCount={BLOCKS.length} />

      <Series>
        <Series.Sequence durationInFrames={BLOCK.b1.duration} name="B1">
          <CueScope start={BLOCK.b1.start}>
            <B1 {...b1} />
          </CueScope>
        </Series.Sequence>
        <Series.Sequence durationInFrames={BLOCK.b2.duration} name="B2">
          <CueScope start={BLOCK.b2.start}>
            <B2 {...b2} />
          </CueScope>
        </Series.Sequence>
      </Series>

      {isFull ? <VoiceRibbon /> : null}
      <Subtitles band={isFull ? LAYOUT.subtitlesFull : LAYOUT.subtitles} />
      <BackdropTop />
    </AbsoluteFill>
  );
};

export const EpisodeMaster: React.FC<z.infer<typeof episodeSchema>> = (props) => (
  <VoiceProvider src={props.voSrc}>
    {props.voSrc ? <Audio src={staticFile(props.voSrc)} /> : null}
    <Episode {...props} />
  </VoiceProvider>
);
