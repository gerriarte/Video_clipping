import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { COLOR, WIPE_ANGLE } from '../theme';

/**
 * Wipe diagonal — ÚNICA sintaxis de transición del episodio.
 * Un solo ángulo (WIPE_ANGLE) en los 5 minutos. Sin variantes.
 *
 * `direction: 'in'`  cubre la pantalla
 * `direction: 'out'` la descubre
 */
export const DiagonalWipe: React.FC<{
  at: number;
  duration?: number;
  direction?: 'in' | 'out';
  feather?: number;
  color?: string;
}> = ({ at, duration = 24, direction = 'in', feather = 60, color = COLOR.bg }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + duration], direction === 'in' ? [0, 1] : [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  if (p <= 0) return null;

  // El gradiente viaja de -20% a 120% para que el borde emplumado entre
  // y salga completamente fuera de cuadro.
  const pos = interpolate(p, [0, 1], [-20, 120]);
  const featherPct = (feather / 1920) * 100;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${180 - WIPE_ANGLE}deg, ${color} ${pos}%, ${color} ${pos}%, transparent ${pos + featherPct}%)`,
        pointerEvents: 'none',
      }}
    />
  );
};

/**
 * Máscara diagonal para revelar un elemento (no toda la pantalla).
 * Devuelve un clipPath listo para aplicar.
 */
export const useDiagonalMask = (at: number, duration = 18) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const slant = Math.tan((WIPE_ANGLE * Math.PI) / 180) * 100;
  const y = interpolate(p, [0, 1], [100 + slant, 0]);
  return {
    clipPath: `polygon(0% ${y + slant}%, 100% ${y}%, 100% 200%, 0% 200%)`,
    opacity: p > 0 ? 1 : 0,
  };
};
