import React from 'react';
import { AbsoluteFill, random, staticFile, useCurrentFrame } from 'remotion';

/**
 * Grano. Sin esto el negro plano se lee digital y barato, y además
 * el banding en los gradientes se hace visible tras la compresión
 * de la plataforma.
 *
 * El desplazamiento es determinístico (random con seed por frame),
 * así el render es reproducible.
 */
export const Grain: React.FC<{ opacity?: number; tile?: number }> = ({
  opacity = 0.035,
  tile = 512,
}) => {
  const frame = useCurrentFrame();
  const x = Math.round(random(`grain-x-${frame}`) * tile);
  const y = Math.round(random(`grain-y-${frame}`) * tile);

  return (
    <AbsoluteFill
      style={{
        backgroundImage: `url(${staticFile('assets/grain-512.png')})`,
        backgroundRepeat: 'repeat',
        backgroundSize: `${tile}px ${tile}px`,
        backgroundPosition: `${x}px ${y}px`,
        mixBlendMode: 'overlay',
        opacity,
        pointerEvents: 'none',
      }}
    />
  );
};

/** Viñeta estática. Empuja la atención al centro sin que se note. */
export const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        'radial-gradient(ellipse 75% 55% at 50% 45%, transparent 40%, rgba(0,0,0,0.55) 100%)',
      pointerEvents: 'none',
    }}
  />
);
