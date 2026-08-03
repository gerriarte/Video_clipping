import React from 'react';
import { AbsoluteFill } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, TYPE } from '../../theme';
import { AnimPane, BrandBar, FacePane } from '../../shared/FacePane';
import { Reveal } from '../../shared/anim';
import { useCue } from '../../shared/useCue';

export const b3Schema = z.object({
  arollSrc: z.string(),
  lineA: z.string(),
  lineB: z.string(),
  question: z.string(),
});

/**
 * BLOQUE 3 · ESCEPTICISMO — SPLIT — 600f (2:00–2:20)
 *
 * Deliberadamente austero. Acá el rostro carga el peso y el pane
 * superior casi no compite: es el único momento del episodio donde
 * el silencio visual es la decisión.
 *
 * El signo de interrogación es el CARÁCTER TIPOGRÁFICO de Archivo
 * Black a 280px, no un icono ni un emoji. Sale parcialmente del canvas
 * por la derecha: la pregunta no entra entera, que es el punto.
 */
export const B3_Escepticismo: React.FC<z.infer<typeof b3Schema>> = ({
  arollSrc,
  lineA,
  lineB,
  question,
}) => {
  const fMark = 0;
  const fLineA = useCue('suena bien', 180);
  const fLineB = useCue('equivocada', 270);
  const fQuestion = useCue('valido', 420);

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode="Episodio · Simile" />

      <AnimPane mode="split">
        <div
          style={{
            position: 'absolute',
            right: -60,
            top: -80,
            ...TYPE.displayXL,
            fontSize: 420,
            color: COLOR.hairline,
            lineHeight: 1,
          }}
        >
          ?
        </div>

        <div style={{ position: 'absolute', left: LAYOUT.margin, top: 180 }}>
          <Reveal at={fLineA} out={fQuestion - 24} style={{ ...TYPE.displayM }}>
            {lineA}
          </Reveal>
          <div style={{ height: 24 }} />
          <Reveal at={fLineB} out={fQuestion - 24} style={{ ...TYPE.displayM }}>
            {lineB}
          </Reveal>
        </div>

        <div style={{ position: 'absolute', left: LAYOUT.margin, top: 180, width: 900 }}>
          <Reveal at={fQuestion} style={{ ...TYPE.displayL }}>
            {question}
          </Reveal>
        </div>
      </AnimPane>

      <FacePane src={arollSrc} offsetY={-180} scale={1.15} />
    </AbsoluteFill>
  );
};
