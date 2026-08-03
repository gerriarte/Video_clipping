import React, { useMemo } from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { createTikTokStyleCaptions } from '@remotion/captions';
import { CAPTIONS } from './captions';
import { COLOR, LAYOUT, TYPE } from '../theme';

/**
 * Subtítulos quemados.
 *
 * Deliberadamente sobrios: el karaoke palabra por palabra en amarillo es
 * la firma visual del contenido de volumen, y trabaja en contra de la
 * posición de autor. Acá el subtítulo es un servicio de accesibilidad,
 * no un recurso de retención.
 *
 * PROHIBIDO: amarillo, stroke negro, pop-in animado, resaltado por palabra.
 */
export const Subtitles: React.FC<{
  combineMs?: number;
  /** Banda donde se monta. Cambia entre split y full: ver LAYOUT. */
  band?: { y: number; height: number };
}> = ({ combineMs = 1400, band = LAYOUT.subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const timeMs = (frame / fps) * 1000;

  const pages = useMemo(() => {
    if (CAPTIONS.length === 0) return [];
    return createTikTokStyleCaptions({ captions: CAPTIONS, combineTokensWithinMilliseconds: combineMs })
      .pages;
  }, [combineMs]);

  const page = pages.find((p) => timeMs >= p.startMs && timeMs < p.startMs + p.durationMs);
  if (!page) return null;

  return (
    <AbsoluteFill
      style={{
        top: band.y,
        height: band.height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: `0 ${LAYOUT.margin}px`,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          ...TYPE.body,
          textAlign: 'center',
          color: COLOR.bone,
          textShadow: '0 2px 12px rgba(0,0,0,0.9), 0 0 32px rgba(0,0,0,0.7)',
          maxWidth: 880,
        }}
      >
        {page.text}
      </div>
    </AbsoluteFill>
  );
};
