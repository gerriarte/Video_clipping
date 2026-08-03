import React from 'react';
import { AbsoluteFill, Audio, Series, staticFile } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT } from '../../theme';
import { Grain, Vignette } from '../../shared/Texture';
import { Subtitles } from '../../shared/Subtitles';
import { BLOCK, CRITERIO_TOTAL } from '../../shared/cues';
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
 * El reparto de bloques ya no es un número escrito a mano: sale de dónde
 * cae en el audio la primera palabra de cada bloque (ver `shared/cues.ts`).
 *
 * Cada bloque va envuelto en <CueScope>, que le dice en qué frame absoluto
 * del episodio arranca. Sin eso los cues —que se resuelven contra el audio
 * completo— apuntarían a frames que adentro de la <Series.Sequence> no
 * existen, y el bloque se quedaría en negro.
 */
export const CriterioMaster: React.FC<z.infer<typeof criterioSchema>> = ({
  voSrc,
  c1,
  c2,
  c3,
  c4,
  c5,
}) => (
  <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
    <Audio src={staticFile(voSrc)} />

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

    {/* Sin A-roll el episodio va full: la banda de subtítulos baja para no
        pisarle el contenido al pane. Con A-roll, sacar el `band`. */}
    <Subtitles band={LAYOUT.subtitlesFull} />
    <Vignette />
    <Grain />
  </AbsoluteFill>
);
