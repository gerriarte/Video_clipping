import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, SAFE, STROKE, TABULAR, TYPE } from '../../theme';
import { AnimPane, BrandBar } from '../../shared/FacePane';
import { DiagonalWipe } from '../../shared/DiagonalWipe';
import { QuoteCard, QuotedAsset } from '../../shared/QuotedAsset';
import { Counter, FadeUp, Reveal } from '../../shared/anim';
import { AgentLoop } from '../../components/Loops';
import { ConfidenceBadge, Smallville } from '../../components/Gauges';
import { useCue } from '../../shared/useCue';

export const b2Schema = z.object({
  founders: z.array(z.object({ name: z.string(), note: z.string() })).length(3),
  headline: z.string(),
  headlineSource: z.string(),
  smallvilleAsset: z.string(),
  smallvilleSource: z.string(),
  agentNodes: z.array(z.string()).length(5),
  bridge: z.string(),
});

/**
 * BLOQUE 2 · DATO Y AGENTES — FULL — 2850f (0:25–2:00)
 *
 * El bloque más largo. Regla de densidad aplicada con rigor: 22 estados
 * en 95 segundos, ninguno por encima de 150 frames sin cambio.
 */
export const B2_DatoYAgentes: React.FC<z.infer<typeof b2Schema>> = (props) => (
  <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
    <BrandBar episode="Episodio · Simile" />
    <AnimPane mode="full">
      <Sequence durationInFrames={540} name="A · La ronda">
        <FaseRonda {...props} />
      </Sequence>
      <Sequence from={540} durationInFrames={960} name="B · Smallville">
        <FaseSmallville {...props} />
      </Sequence>
      <Sequence from={1500} durationInFrames={900} name="C · Arquitectura">
        <FaseArquitectura {...props} />
      </Sequence>
      <Sequence from={2400} durationInFrames={450} name="D · Puente">
        <FasePuente {...props} />
      </Sequence>
    </AnimPane>
  </AbsoluteFill>
);

// ── FASE A ────────────────────────────────────────────────────────
const FaseRonda: React.FC<z.infer<typeof b2Schema>> = ({
  founders,
  headline,
  headlineSource,
}) => {
  const fCounter = useCue('doscientos', 20);
  const fLines = fCounter + 40;
  const fQuote = useCue('ocho mil millones', 200);
  const fFounders = useCue('joon', 340);

  return (
    <AbsoluteFill style={{ padding: `40px ${LAYOUT.margin}px` }}>
      <Reveal at={fCounter} style={{ ...TYPE.displayXL, ...TABULAR }}>
        <Counter
          at={fCounter}
          duration={180}
          to={200_000_000}
          format={(n) => `USD ${Math.round(n).toLocaleString('es-AR')}`}
        />
      </Reveal>

      {/* El contador no corre solo: mientras avanza, entran las tres
          líneas de contexto. Un número subiendo 6 segundos sin nada
          alrededor viola la regla de densidad. */}
      <div style={{ marginTop: 56 }}>
        {[
          'Valuación post-money: USD 2.000 millones',
          'Co-liderada por Greenoaks e Index Ventures',
          '5 meses desde el lanzamiento',
        ].map((l, i) => (
          <FadeUp key={l} at={fLines + i * 40} out={fQuote - 12} style={{ marginBottom: 20 }}>
            <div style={TYPE.body}>{l}</div>
          </FadeUp>
        ))}
      </div>

      <QuoteCard
        at={fQuote}
        quote={headline}
        source={headlineSource}
        style={{ position: 'absolute', left: LAYOUT.margin, top: 640 }}
      />

      {/* Fundadores como cards apiladas, no como lista. El trazo vertical
          que las une + "STANFORD" rotado es lo que convierte tres nombres
          en una procedencia. */}
      <div style={{ position: 'absolute', left: LAYOUT.margin, top: 980 }}>
        <div style={{ position: 'relative', paddingLeft: 56 }}>
          <FadeUp at={fFounders + 200}>
            <div
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: 0,
                width: STROKE,
                background: COLOR.bone,
              }}
            />
            <div
              style={{
                ...TYPE.label,
                position: 'absolute',
                left: -78,
                top: 200,
                transform: 'rotate(-90deg)',
                transformOrigin: 'center',
              }}
            >
              Stanford
            </div>
          </FadeUp>

          {founders.map((f, i) => (
            <FadeUp
              key={f.name}
              at={fFounders + i * 60}
              from="left"
              duration={18}
              style={{
                height: 160,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                borderTop: i === 0 ? 'none' : `${STROKE}px solid ${COLOR.hairline}`,
                width: 900,
              }}
            >
              <div style={{ ...TYPE.displayM, fontSize: 60 }}>{f.name}</div>
              <div style={{ ...TYPE.footnote, marginTop: 10 }}>{f.note}</div>
            </FadeUp>
          ))}
        </div>
      </div>

      <DiagonalWipe at={516} duration={24} />
    </AbsoluteFill>
  );
};

// ── FASE B ────────────────────────────────────────────────────────
const FaseSmallville: React.FC<z.infer<typeof b2Schema>> = ({
  smallvilleAsset,
  smallvilleSource,
}) => {
  const fStart = 24;
  const fCluster = useCue('veinticinco', 336);
  const fHighlight = useCue('fiesta', 516);
  const fAsset = useCue('smallville', 636);
  const fLabel = 816;

  return (
    <AbsoluteFill>
      {/* El pueblo, la etiqueta del cluster y la figura del paper viven
          en su propia Sequence: cuando entra la card tipográfica final,
          todo esto ya salió de pantalla. Si convivieran, la card se
          leería como superposición y no como conclusión. */}
      <Sequence durationInFrames={fLabel - 12} name="pueblo">
      <div style={{ position: 'absolute', top: 60, left: 0 }}>
        <Smallville at={fStart} clusterAt={fCluster} highlightAt={fHighlight} />
      </div>

      <FadeUp at={fHighlight + 24} style={{ position: 'absolute', top: 700, left: LAYOUT.margin }}>
        <div
          style={{
            ...TYPE.label,
            background: COLOR.bg,
            padding: '14px 22px',
            border: `${STROKE}px solid ${COLOR.hairline}`,
            display: 'inline-block',
          }}
        >
          Una fiesta que nadie organizó
        </div>
      </FadeUp>

      <QuotedAsset
        at={fAsset}
        src={smallvilleAsset}
        source={smallvilleSource}
        scale={0.7}
        rotate={1.5}
        style={{ position: 'absolute', left: LAYOUT.margin, top: 860 }}
      />
      </Sequence>

      <Sequence from={fLabel - 12} name="etiqueta">
        <DiagonalWipe at={0} duration={24} />
        <AbsoluteFill
          style={{
            justifyContent: 'center',
            alignItems: 'flex-start',
            paddingLeft: LAYOUT.margin,
            top: 0,
            height: SAFE.bottom,
          }}
        >
          {/* Fenómeno primero, etiqueta después: recién acá el pueblo
              tiene nombre. */}
          <Reveal at={24} style={{ ...TYPE.displayXL }}>
            Agentes
            <br />
            generativos
          </Reveal>
          <FadeUp at={48} style={{ marginTop: 28 }}>
            <div style={TYPE.footnote}>UIST, 2023 · arXiv 2304.03442</div>
          </FadeUp>
        </AbsoluteFill>
      </Sequence>

      <DiagonalWipe at={0} duration={24} direction="out" />
      <DiagonalWipe at={936} duration={24} />
    </AbsoluteFill>
  );
};

// ── FASE C ────────────────────────────────────────────────────────
const FaseArquitectura: React.FC<z.infer<typeof b2Schema>> = ({ agentNodes }) => {
  const fNodes = useCue('memoria', 60);
  const fPulse = fNodes + 5 * 90 + 36;
  const fConfidence = useCue('confianza', 600);

  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: 60,
          left: LAYOUT.margin,
          transform: `scale(${1})`,
        }}
      >
        <AgentLoop at={fNodes} nodes={agentNodes} pulseAt={fPulse} />
      </div>

      <div style={{ position: 'absolute', top: 940, left: LAYOUT.margin, width: 936 }}>
        <FadeUp at={fConfidence}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingBottom: 28,
              borderBottom: `${STROKE}px solid ${COLOR.hairline}`,
            }}
          >
            <div style={TYPE.label}>Resultado</div>
            <div style={{ width: 480, height: 40, background: COLOR.bone }} />
          </div>
        </FadeUp>

        <FadeUp at={fConfidence + 60}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: 28,
            }}
          >
            <div style={TYPE.label}>Confianza</div>
            {/* USO 2/4 DEL ACENTO: el tercer estado, "Media". */}
            <ConfidenceBadge
              at={fConfidence + 60}
              hold={90}
              states={[
                { text: 'Alta' },
                { text: 'Moderada-alta' },
                { text: 'Media', accent: true },
              ]}
            />
          </div>
        </FadeUp>
      </div>

      <DiagonalWipe at={0} duration={24} direction="out" />
    </AbsoluteFill>
  );
};

// ── FASE D ────────────────────────────────────────────────────────
const FasePuente: React.FC<z.infer<typeof b2Schema>> = ({ bridge }) => {
  const fBridge = 150;
  return (
    <AbsoluteFill>
      <DiagonalWipe at={0} duration={24} />
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: `0 ${LAYOUT.margin}px`,
          height: SAFE.bottom,
        }}
      >
        <Reveal at={fBridge} style={{ ...TYPE.displayL }}>
          {bridge}
        </Reveal>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
