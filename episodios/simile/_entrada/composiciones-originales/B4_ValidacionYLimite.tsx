import React from 'react';
import { AbsoluteFill, Img, Sequence, staticFile } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, SAFE, STROKE, TYPE } from '../../theme';
import { AnimPane, BrandBar } from '../../shared/FacePane';
import { DiagonalWipe } from '../../shared/DiagonalWipe';
import { FadeUp, Reveal, useSpringAt } from '../../shared/anim';
import { ArcGauge, ComparativeBars, PersonGrid } from '../../components/Gauges';
import { useCue } from '../../shared/useCue';

export const b4Schema = z.object({
  gaugeValue: z.number(),
  gaugeCaption: z.array(z.string()).length(2),
  finetuneFootnote: z.string(),
  clients: z.array(z.object({ name: z.string(), logo: z.string() })),
  disclaimer: z.string(),
  limitTop: z.string(),
  limitBottom: z.string(),
  limitClosing: z.string(),
});

/**
 * BLOQUE 4 · VALIDACIÓN Y LÍMITE — FULL — 2700f (2:20–3:50)
 *
 * El bloque de credibilidad. Máxima densidad de dato, mínima decoración.
 * Es el que sostiene la posición de autor: si acá algo se lee como
 * adorno, todo el episodio baja de registro.
 */
export const B4_ValidacionYLimite: React.FC<z.infer<typeof b4Schema>> = (props) => (
  <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
    <BrandBar episode="Episodio · Simile" />
    <AnimPane mode="full">
      <Sequence durationInFrames={720} name="A · Mil personas">
        <FaseMilPersonas />
      </Sequence>
      <Sequence from={720} durationInFrames={600} name="B · El 85%">
        <FaseGauge {...props} />
      </Sequence>
      <Sequence from={1320} durationInFrames={420} name="C · Finetuning">
        <FaseFinetuning {...props} />
      </Sequence>
      <Sequence from={1740} durationInFrames={360} name="D · Clientes">
        <FaseClientes {...props} />
      </Sequence>
      <Sequence from={2100} durationInFrames={600} name="E · El límite">
        <FaseLimite {...props} />
      </Sequence>
    </AnimPane>
  </AbsoluteFill>
);

// ── FASE A ────────────────────────────────────────────────────────
const FaseMilPersonas: React.FC = () => {
  const fGrid = 20;
  const fTwin = useCue('un agente por cada una', 400);
  const fLabel = 520;

  return (
    <AbsoluteFill style={{ paddingTop: 40 }}>
      <PersonGrid at={fGrid} twinAt={fTwin} />
      <FadeUp
        at={fLabel}
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 620,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <div style={{ background: COLOR.bg, padding: '28px 44px', textAlign: 'center' }}>
          <div style={{ ...TYPE.displayM, fontSize: 60 }}>1.000 personas → 1.000 agentes</div>
          <div style={{ ...TYPE.footnote, marginTop: 14 }}>Park et al., 2024</div>
        </div>
      </FadeUp>
      <DiagonalWipe at={0} duration={20} direction="out" />
    </AbsoluteFill>
  );
};

// ── FASE B ────────────────────────────────────────────────────────
const FaseGauge: React.FC<z.infer<typeof b4Schema>> = ({ gaugeValue, gaugeCaption }) => {
  const fGauge = useCue('ochenta y cinco', 60);
  const fCaption = useCue('inconsistencia', 300);

  return (
    <AbsoluteFill>
      {/* La grilla no desaparece: se desatura y queda como textura.
          Los mil agentes siguen ahí mientras se lee el 85%. */}
      <div style={{ position: 'absolute', inset: 0, opacity: 0.22 }}>
        <PersonGrid at={-2000} recedeAt={0} />
      </div>

      <div
        style={{
          position: 'absolute',
          left: (1080 - 720) / 2,
          top: 120,
        }}
      >
        <ArcGauge at={fGauge} value={gaugeValue} size={720} />
      </div>

      <div style={{ position: 'absolute', left: LAYOUT.margin, top: 940, width: 936 }}>
        {gaugeCaption.map((l, i) => (
          <FadeUp key={l} at={fCaption + i * 24} style={{ marginBottom: 8 }}>
            <div style={TYPE.body}>{l}</div>
          </FadeUp>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ── FASE C ────────────────────────────────────────────────────────
const FaseFinetuning: React.FC<z.infer<typeof b4Schema>> = ({ finetuneFootnote }) => {
  const fBars = 60;
  const fDelta = useCue('veintiseis', 240);
  const p = useSpringAt(fDelta, 24);

  return (
    <AbsoluteFill style={{ padding: `160px ${LAYOUT.margin}px` }}>
      <DiagonalWipe at={0} duration={24} direction="out" />
      <ComparativeBars
        at={fBars}
        rows={[
          { label: 'Modelo base', value: 62 },
          { label: 'Modelo finetuneado', value: 88 },
        ]}
      />
      <div
        style={{
          ...TYPE.displayL,
          marginTop: 20,
          opacity: p,
          transform: `translateX(${Math.round((1 - p) * 40)}px)`,
        }}
      >
        +26%
      </div>
      <FadeUp at={fDelta + 36} style={{ marginTop: 40 }}>
        <div style={TYPE.footnote}>{finetuneFootnote}</div>
      </FadeUp>
    </AbsoluteFill>
  );
};

// ── FASE D ────────────────────────────────────────────────────────
const FaseClientes: React.FC<z.infer<typeof b4Schema>> = ({ clients, disclaimer }) => {
  const fLogos = 20;
  const fDisclaimer = 300;

  return (
    <AbsoluteFill style={{ padding: `220px ${LAYOUT.margin}px` }}>
      <DiagonalWipe at={0} duration={24} direction="out" />
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 60,
          alignItems: 'center',
        }}
      >
        {clients.map((c, i) => (
          <FadeUp key={c.name} at={fLogos + i * 30} duration={18}>
            {/* Excepción a QuotedAsset: los logos van sin marco. Un
                borde alrededor de cada logo convertiría la grilla en
                un muro de cajas. Monocromo y opacidad hacen el trabajo. */}
            <Img
              src={staticFile(c.logo)}
              style={{
                width: '100%',
                maxHeight: 90,
                objectFit: 'contain',
                filter: 'grayscale(1) brightness(2)',
                opacity: 0.7,
              }}
            />
          </FadeUp>
        ))}
      </div>

      {/* Obligatorio. Sin este pie, cifras autorreportadas presentadas
          como hechos es exactamente el tipo de dato que se cae en los
          comentarios. */}
      <FadeUp at={fDisclaimer} style={{ marginTop: 80 }}>
        <div style={TYPE.footnote}>{disclaimer}</div>
      </FadeUp>
    </AbsoluteFill>
  );
};

// ── FASE E ────────────────────────────────────────────────────────
const FaseLimite: React.FC<z.infer<typeof b4Schema>> = ({
  limitTop,
  limitBottom,
  limitClosing,
}) => {
  const fTop = 60;
  const fBottom = useCue('revelado', 180);
  const fClosing = useCue('incertidumbre', 360);

  return (
    <AbsoluteFill>
      <DiagonalWipe at={0} duration={24} direction="out" />

      {/* Split VERTICAL, no diagonal. El corte acá es conceptual —dos
          categorías que no son la misma cosa— y merece otra sintaxis
          que la transición temporal. */}
      <div style={{ position: 'absolute', top: 120, left: LAYOUT.margin, width: 936 }}>
        <FadeUp at={fTop}>
          <div style={{ ...TYPE.label, marginBottom: 20 }}>{limitTop}</div>
          <div style={{ width: 936, height: 80, background: COLOR.bone }} />
        </FadeUp>
      </div>

      <div
        style={{
          position: 'absolute',
          top: 380,
          left: 0,
          width: 1080,
          height: STROKE,
          background: COLOR.hairline,
        }}
      />

      <div style={{ position: 'absolute', top: 460, left: LAYOUT.margin, width: 936 }}>
        <FadeUp at={fBottom}>
          <div style={{ ...TYPE.label, marginBottom: 20 }}>{limitBottom}</div>
          {/* USO 3/4 DEL ACENTO. El dash se desplaza: único movimiento
              continuo del episodio, y marca inestabilidad. */}
          <DashedBar at={fBottom} width={936 * 0.6} />
        </FadeUp>
      </div>

      <div style={{ position: 'absolute', top: 760, left: LAYOUT.margin, width: 936 }}>
        <FadeUp at={fClosing}>
          <div style={TYPE.body}>{limitClosing}</div>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};

const DashedBar: React.FC<{ at: number; width: number }> = ({ at, width }) => {
  const p = useSpringAt(at + 12, 30);
  return (
    <svg width={width} height={84}>
      <rect
        x={STROKE / 2}
        y={STROKE / 2}
        width={Math.max(0, width * p - STROKE)}
        height={80}
        fill="none"
        stroke={COLOR.accent}
        strokeWidth={STROKE}
        strokeDasharray="14 10"
      >
        <animate
          attributeName="stroke-dashoffset"
          from="0"
          to="-48"
          dur="2s"
          repeatCount="indefinite"
        />
      </rect>
    </svg>
  );
};
