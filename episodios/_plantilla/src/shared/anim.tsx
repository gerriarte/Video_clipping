import React from 'react';
import {
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { SPRING, T, TABULAR } from '../theme';

/** Redondeo obligatorio en desplazamientos: el subpíxel emborrona bordes. */
export const px = (n: number) => Math.round(n);

/**
 * Revelado de display type.
 * Prohibido el fade de opacidad puro en tipografía display: siempre
 * máscara ascendente + translateY + apertura de tracking.
 */
export const Reveal: React.FC<{
  at: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
  duration?: number;
  /** tracking final, para animar desde -0.05em */
  tracking?: string;
  out?: number;
}> = ({ at, children, style, duration = T.enter, tracking = '-0.03em', out }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const p = spring({ frame: frame - at, fps, config: SPRING, durationInFrames: duration });
  const exit = out
    ? interpolate(frame, [out, out + T.exit], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.in(Easing.quad),
      })
    : 1;

  if (frame < at) return null;

  return (
    <div style={{ overflow: 'hidden', opacity: exit }}>
      <div
        style={{
          clipPath: `inset(${(1 - p) * 100}% 0 0 0)`,
          transform: `translateY(${px((1 - p) * 28)}px)`,
          letterSpacing: p < 1 ? `calc(${tracking} - ${(1 - p) * 0.02}em)` : tracking,
          ...style,
        }}
      >
        {children}
      </div>
    </div>
  );
};

/** Entrada de body text: opacidad + desplazamiento corto. */
export const FadeUp: React.FC<{
  at: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
  duration?: number;
  from?: 'bottom' | 'left';
  out?: number;
}> = ({ at, children, style, duration = 12, from = 'bottom', out }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = spring({ frame: frame - at, fps, config: SPRING, durationInFrames: duration });
  const exit = out
    ? interpolate(frame, [out, out + T.exit], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.in(Easing.quad),
      })
    : 1;

  if (frame < at) return null;

  const shift = from === 'bottom'
    ? `translateY(${px((1 - p) * 12)}px)`
    : `translateX(${px((1 - p) * -40)}px)`;

  return (
    <div style={{ opacity: p * exit, transform: shift, ...style }}>{children}</div>
  );
};

/** Contador numérico. Easing.out(cubic) + tabular-nums. */
export const Counter: React.FC<{
  at: number;
  duration: number;
  to: number;
  from?: number;
  format?: (n: number) => string;
  style?: React.CSSProperties;
}> = ({ at, duration, to, from = 0, format, style }) => {
  const frame = useCurrentFrame();
  const value = interpolate(frame, [at, at + duration], [from, to], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const fmt = format ?? ((n: number) => Math.round(n).toLocaleString('es-AR'));
  return <span style={{ ...TABULAR, ...style }}>{fmt(value)}</span>;
};

/** Trazo que se dibuja. strokeDashoffset animado, easing inOut. */
export const useDraw = (at: number, duration: number, length: number) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  return { strokeDasharray: length, strokeDashoffset: length * (1 - p) };
};

/** Pulso de escala. Una sola vez, máximo 1.06. Nunca desde 0. */
export const usePulse = (at: number, peak = 1.05, duration = 18) => {
  const frame = useCurrentFrame();
  return interpolate(
    frame,
    [at, at + duration / 2, at + duration],
    [1, peak, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) },
  );
};

/** Progreso 0→1 con spring, para lo que no encaje en los helpers de arriba. */
export const useSpringAt = (at: number, duration: number = T.enter) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - at, fps, config: SPRING, durationInFrames: duration });
};
