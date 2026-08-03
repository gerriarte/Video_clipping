import React from 'react';
import { AbsoluteFill } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, TYPE } from '../../theme';
import { AnimPane, BrandBar, FacePane } from '../../shared/FacePane';
import { LatencyTimelineVertical } from '../../components/LatencyTimeline';
import { QuotedAsset } from '../../shared/QuotedAsset';
import { Reveal, usePulse } from '../../shared/anim';
import { useCue } from '../../shared/useCue';

export const b1Schema = z.object({
  arollSrc: z.string(),
  steps: z.array(z.string()).length(5),
  punchline: z.string(),
  assetSrc: z.string(),
  assetSource: z.string(),
});

/**
 * BLOQUE 1 · APERTURA — SPLIT — 750f (0:00–0:25)
 *
 * La latencia del research. Termina SIN resolver: la captura de la
 * ronda entra tapando parcialmente el conjunto y corta. La tensión
 * abierta es lo que sostiene el paso al bloque 2.
 */
export const B1_Apertura: React.FC<z.infer<typeof b1Schema>> = ({
  arollSrc,
  steps,
  punchline,
  assetSrc,
  assetSource,
}) => {
  // Los frames son FALLBACK. La transcripción manda.
  const fStep0 = useCue('brief', 90);
  const fStep1 = useCue('reclutar', 150);
  const fStep2 = useCue('campo', 210);
  const fStep3 = useCue('analisis', 270);
  const fStep4 = useCue('decision', 330);
  const fCollapse = useCue('costo real', 450);
  const fPunch = useCue('seis semanas', 540);
  const fAsset = useCue('nadie da muchas', 660);

  const pulse = usePulse(fPunch + 18, 1.05, 18);

  const cues = [fStep0, fStep1, fStep2, fStep3, fStep4];

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode="Episodio · Simile" />

      <AnimPane mode="split">
        <LatencyTimelineVertical
          steps={steps.map((label, i) => ({ label, at: cues[i] }))}
          collapseAt={fCollapse}
        />

        {/* El punchline ocupa el espacio que libera la compresión de la
            timeline. Las filas no desaparecen: quedan en muted como
            contexto de lo que acaba de costar seis semanas. */}
        <div
          style={{
            position: 'absolute',
            left: LAYOUT.margin,
            bottom: 120,
            transform: `scale(${pulse})`,
            transformOrigin: 'left bottom',
          }}
        >
          <Reveal at={fPunch} style={{ ...TYPE.displayXL, color: COLOR.accent, whiteSpace: 'pre-line' }}>
            {punchline}
          </Reveal>
        </div>

        <QuotedAsset
          at={fAsset}
          src={assetSrc}
          source={assetSource}
          scale={0.66}
          rotate={-1.5}
          style={{ position: 'absolute', left: LAYOUT.margin, bottom: -40 }}
        />
      </AnimPane>

      <FacePane src={arollSrc} offsetY={-180} scale={1.15} />
    </AbsoluteFill>
  );
};
