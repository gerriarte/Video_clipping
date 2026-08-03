import React from 'react';
import { AbsoluteFill, Audio, Series, staticFile } from 'remotion';
import { z } from 'zod';
import { COLOR } from '../../theme';
import { Grain, Vignette } from '../../shared/Texture';
import { Subtitles } from '../../shared/Subtitles';
import { B1_Apertura, b1Schema } from './B1_Apertura';
import { B2_DatoYAgentes, b2Schema } from './B2_DatoYAgentes';
import { B3_Escepticismo, b3Schema } from './B3_Escepticismo';
import { B4_ValidacionYLimite, b4Schema } from './B4_ValidacionYLimite';
import { B5_Cierre, b5Schema } from './B5_Cierre';

export const masterSchema = z.object({
  voSrc: z.string(),
  b1: b1Schema,
  b2: b2Schema,
  b3: b3Schema,
  b4: b4Schema,
  b5: b5Schema,
});

export const BLOCK_FRAMES = {
  b1: 750,
  b2: 2850,
  b3: 600,
  b4: 2700,
  b5: 2100,
} as const;

export const TOTAL_FRAMES = Object.values(BLOCK_FRAMES).reduce((a, b) => a + b, 0); // 9000

/**
 * Master del episodio. 9000 frames a 30fps = 5:00 exactos.
 *
 * Grano, viñeta y subtítulos viven acá y no por composición: si cada
 * bloque los montara por su cuenta, la textura saltaría en cada corte.
 */
export const EpisodeMaster: React.FC<z.infer<typeof masterSchema>> = ({
  voSrc,
  b1,
  b2,
  b3,
  b4,
  b5,
}) => (
  <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
    <Audio src={staticFile(voSrc)} />

    <Series>
      <Series.Sequence durationInFrames={BLOCK_FRAMES.b1} name="B1 · Apertura">
        <B1_Apertura {...b1} />
      </Series.Sequence>
      <Series.Sequence durationInFrames={BLOCK_FRAMES.b2} name="B2 · Dato y agentes">
        <B2_DatoYAgentes {...b2} />
      </Series.Sequence>
      <Series.Sequence durationInFrames={BLOCK_FRAMES.b3} name="B3 · Escepticismo">
        <B3_Escepticismo {...b3} />
      </Series.Sequence>
      <Series.Sequence durationInFrames={BLOCK_FRAMES.b4} name="B4 · Validación y límite">
        <B4_ValidacionYLimite {...b4} />
      </Series.Sequence>
      <Series.Sequence durationInFrames={BLOCK_FRAMES.b5} name="B5 · Cierre">
        <B5_Cierre {...b5} />
      </Series.Sequence>
    </Series>

    <Subtitles />
    <Vignette />
    <Grain />
  </AbsoluteFill>
);
