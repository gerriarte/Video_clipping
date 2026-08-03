import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, TYPE } from '../../theme';
import { AnimPane, BrandBar, FacePane } from '../../shared/FacePane';
import { DiagonalWipe } from '../../shared/DiagonalWipe';
import { FadeUp, Reveal } from '../../shared/anim';
import { LoopDiamond } from '../../components/Loops';
import { useCue } from '../../shared/useCue';

export const b5Schema = z.object({
  arollSrc: z.string(),
  loopNodes: z.tuple([z.string(), z.string(), z.string(), z.string()]),
  overlayA: z.string(),
  overlayB: z.string(),
  anchor: z.string(),
  questions: z.array(z.string()).length(3),
});

/**
 * BLOQUE 5 · CIERRE — SPLIT — 2100f (3:50–5:00)
 *
 * 70 segundos en split: el bloque más largo a cámara. El pane superior
 * tiene que sostener con cambios cada 3–4s sin robarle atención al
 * rostro. Por eso el loop gira solo y los overlays entran con fondo
 * sólido: compiten poco, marcan tiempo.
 */
export const B5_Cierre: React.FC<z.infer<typeof b5Schema>> = (props) => (
  <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
    <BrandBar episode="Episodio · Simile" />

    <AnimPane mode="split">
      <Sequence durationInFrames={720} name="A · El reprecio">
        <FaseReprecio {...props} />
      </Sequence>
      <Sequence from={720} durationInFrames={480} name="B · Frase ancla">
        <FaseAncla {...props} />
      </Sequence>
      <Sequence from={1200} durationInFrames={900} name="C · Tres preguntas">
        <FasePreguntas {...props} />
      </Sequence>
    </AnimPane>

    <FacePane src={props.arollSrc} offsetY={-180} scale={1.15} />
  </AbsoluteFill>
);

// ── FASE A ────────────────────────────────────────────────────────
const FaseReprecio: React.FC<z.infer<typeof b5Schema>> = ({
  loopNodes,
  overlayA,
  overlayB,
}) => {
  const fLoop = 0;
  const fA = useCue('diferencial', 360);
  const fB = useCue('como lees', 540);

  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: LAYOUT.margin, top: 30 }}>
        <LoopDiamond at={fLoop} nodes={loopNodes} width={936} height={880} />
      </div>

      <Overlay at={fA} out={fB - 12} text={overlayA} />
      <Overlay at={fB} text={overlayB} />
    </AbsoluteFill>
  );
};

const Overlay: React.FC<{ at: number; out?: number; text: string }> = ({ at, out, text }) => (
  <FadeUp
    at={at}
    out={out}
    style={{
      position: 'absolute',
      left: LAYOUT.margin,
      top: 380,
      width: 900,
    }}
  >
    <div
      style={{
        background: COLOR.bg,
        padding: '36px 40px',
        ...TYPE.displayM,
        fontSize: 62,
      }}
    >
      {text}
    </div>
  </FadeUp>
);

// ── FASE B ────────────────────────────────────────────────────────
const FaseAncla: React.FC<z.infer<typeof b5Schema>> = ({ anchor }) => {
  const fAnchor = useCue('no gana', 60);
  const words = anchor.split(' ');

  return (
    <AbsoluteFill>
      <DiagonalWipe at={0} duration={24} direction="out" />
      <div
        style={{
          position: 'absolute',
          left: LAYOUT.margin,
          top: 180,
          width: 936,
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0 18px',
        }}
      >
        {/* Palabra por palabra, stagger de 14f. Después: 4 segundos de
            quietud absoluta. Es el punto de mayor densidad del episodio
            y necesita aire — si algo se mueve ahí, la frase no aterriza. */}
        {words.map((w, i) => (
          <Reveal key={`${w}-${i}`} at={fAnchor + i * 14} style={{ ...TYPE.displayL }}>
            {w}
          </Reveal>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ── FASE C ────────────────────────────────────────────────────────
const FasePreguntas: React.FC<z.infer<typeof b5Schema>> = ({ questions }) => {
  const fQ = [useCue('cuantas versiones', 0), useCue('cuanto costo', 240), useCue('costaran cero', 480)];

  return (
    <AbsoluteFill style={{ padding: `100px ${LAYOUT.margin}px` }}>
      {questions.map((q, i) => (
        <div key={q} style={{ display: 'flex', gap: 28, marginBottom: 56 }}>
          <FadeUp at={fQ[i]}>
            {/* El numeral existe porque las preguntas SÍ son una
                secuencia: cuántas → cuánto costó → cuántas darías.
                El orden carga el argumento. */}
            <div style={{ ...TYPE.footnote, paddingTop: 14 }}>
              {String(i + 1).padStart(2, '0')}
            </div>
          </FadeUp>
          <Reveal
            at={fQ[i]}
            style={{
              ...TYPE.displayM,
              // USO 4/4 DEL ACENTO: la tercera pregunta.
              color: i === 2 ? COLOR.accent : COLOR.bone,
              maxWidth: 820,
            }}
            tracking="-0.02em"
          >
            {q}
          </Reveal>
        </div>
      ))}
    </AbsoluteFill>
  );
};
