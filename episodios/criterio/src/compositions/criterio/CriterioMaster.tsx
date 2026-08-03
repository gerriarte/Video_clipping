import React from 'react';
import { AbsoluteFill, Audio, Series, staticFile, useCurrentFrame } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT } from '../../theme';
import { Backdrop, BackdropTop } from '../../shared/Backdrop';
import { Subtitles } from '../../shared/Subtitles';
import { VoiceProvider } from '../../shared/voice';
import { VoiceRibbon } from '../../shared/VoiceTrace';
import { BLOCK, BLOCKS, CRITERIO_TOTAL, CUE_FRAMES } from '../../shared/cues';
import { CueScope } from '../../shared/useCue';
import { C1_Arranque, C2_QueEs, C3_Precio, c1Schema, c2Schema, c3Schema } from './C1_C2_C3';
import { C4_Absurdo, C5_Salida, c4Schema, c5Schema } from './C4_C5';

export const criterioSchema = z.object({
  voSrc: z.string(),
  c1: c1Schema,
  c2: c2Schema,
  c3: c3Schema,
  c4: c4Schema,
  c5: c5Schema,
});

export { CRITERIO_TOTAL };

/**
 * Cuánta trama de fondo pide cada bloque. Los que ya tienen un visual
 * denso —las columnas del C2, las curvas del C3— piden menos: el fondo
 * está para que el cuadro no se muera, no para competir.
 */
const DENSITY: Record<string, number> = { c1: 1, c2: 0.45, c3: 0.6, c4: 0.9, c5: 0.7 };

/**
 * Tramos que corren a pane completo (sin pane de abajo). Ahí la banda de
 * subtítulos baja, porque el contenido ocupa el alto que en split ocupa
 * el rostro.
 */
const fullRanges = (): [number, number][] => [
  [BLOCK.c2.start, BLOCK.c4.start],
  [CUE_FRAMES['c5.halves'] - 12, CUE_FRAMES['c5.q1'] - 24],
];

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
 * El reparto de bloques no es un número escrito a mano: sale de dónde
 * cae en el audio la primera palabra de cada bloque (ver `shared/cues.ts`).
 *
 * Cada bloque va envuelto en <CueScope>, que le dice en qué frame
 * absoluto del episodio arranca. Sin eso los cues —que se resuelven
 * contra el audio completo— apuntarían a frames que adentro de la
 * <Series.Sequence> no existen, y el bloque se quedaría en negro.
 */
const Episode: React.FC<z.infer<typeof criterioSchema>> = ({ c1, c2, c3, c4, c5 }) => {
  const { blockIndex, isFull } = useStage();

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <Backdrop
        total={CRITERIO_TOTAL}
        blockIndex={blockIndex}
        blockCount={BLOCKS.length}
        density={DENSITY[BLOCKS[blockIndex]?.key ?? 'c1'] ?? 1}
      />

      <Series>
        <Series.Sequence durationInFrames={BLOCK.c1.duration} name="C1 · Arranque">
          <CueScope start={BLOCK.c1.start}>
            <C1_Arranque {...c1} />
          </CueScope>
        </Series.Sequence>
        <Series.Sequence durationInFrames={BLOCK.c2.duration} name="C2 · Qué es">
          <CueScope start={BLOCK.c2.start}>
            <C2_QueEs {...c2} />
          </CueScope>
        </Series.Sequence>
        <Series.Sequence durationInFrames={BLOCK.c3.duration} name="C3 · Precio">
          <CueScope start={BLOCK.c3.start}>
            <C3_Precio {...c3} />
          </CueScope>
        </Series.Sequence>
        <Series.Sequence durationInFrames={BLOCK.c4.duration} name="C4 · Absurdo">
          <CueScope start={BLOCK.c4.start}>
            <C4_Absurdo {...c4} />
          </CueScope>
        </Series.Sequence>
        <Series.Sequence durationInFrames={BLOCK.c5.duration} name="C5 · Salida">
          <CueScope start={BLOCK.c5.start}>
            <C5_Salida {...c5} />
          </CueScope>
        </Series.Sequence>
      </Series>

      {/* A pane completo no hay pane de abajo, y los últimos 400px del
          cuadro quedaban muertos. La voz sigue ahí: va como cinta al pie,
          en la franja que la UI de la plataforma tapa. */}
      {isFull ? <VoiceRibbon /> : null}

      <Subtitles band={isFull ? LAYOUT.subtitlesFull : LAYOUT.subtitles} />
      <BackdropTop />
    </AbsoluteFill>
  );
};

export const CriterioMaster: React.FC<z.infer<typeof criterioSchema>> = (props) => (
  <VoiceProvider src={props.voSrc}>
    {props.voSrc ? <Audio src={staticFile(props.voSrc)} /> : null}
    <Episode {...props} />
  </VoiceProvider>
);
