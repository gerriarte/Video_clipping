import React from 'react';
import { Easing, interpolate, random, useCurrentFrame } from 'remotion';
import { CANVAS, COLOR, LAYOUT, STROKE, WIPE_ANGLE } from '../theme';
import { useVoice } from '../shared/voice';
import { VoiceTrace } from '../shared/VoiceTrace';

/**
 * EL PANE DE ABAJO, SIN ROSTRO.
 *
 * Ocupa exactamente el lugar del A-roll (misma caja, misma costura,
 * misma entrada por máscara diagonal), así que el día que existan los
 * clips a cámara esto se reemplaza y la composición no se entera.
 *
 * Qué se ve: la voz. Literalmente —el trazo central es la forma de onda
 * del VO en ese instante— con el motivo del bloque alrededor. La
 * alternativa era relleno abstracto girando, que es exactamente el
 * lenguaje del contenido de volumen que este episodio no es.
 */

const PANE = LAYOUT.facePane; // { y: 1100, height: 820 }
const W = CANVAS.width;

export type Motif = 'filter' | 'discard' | 'converge';

/**
 * C1 · El filtro. Un flujo de marcas que cruza el cuadro y, al pasar
 * cierto punto, se apaga. Es el argumento del bloque hecho movimiento:
 * lo que llega no se rompe, se descarta.
 */
const FilterStream: React.FC<{ height: number }> = ({ height }) => {
  const frame = useCurrentFrame();
  const { bands, energy } = useVoice();
  const count = 44;
  const step = W / count;
  const cut = W * 0.62;
  const speed = 1.1 + energy * 1.6;

  return (
    <>
      {Array.from({ length: count }).map((_, i) => {
        const seed = random(`fs-${i}`);
        const x = (((i * step - frame * speed) % (W + step)) + W + step) % (W + step);
        const band = bands.length ? bands[i % bands.length] : 0;
        const h = 40 + seed * 90 + band * 320;
        const passed = x < cut;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: Math.round(x),
              top: Math.round(height / 2 - h / 2),
              width: STROKE,
              height: Math.round(h),
              background: COLOR.bone,
              opacity: passed ? 0.09 : 0.4 + seed * 0.22,
            }}
          />
        );
      })}
      {/* El corte. Punteado, como el filtro del C3: es la misma idea. */}
      <div
        style={{
          position: 'absolute',
          left: Math.round(cut),
          top: 60,
          bottom: 60,
          width: STROKE,
          background: `repeating-linear-gradient(to bottom, ${COLOR.bone} 0 10px, transparent 10px 20px)`,
          opacity: 0.22,
        }}
      />
    </>
  );
};

/**
 * C4 · El descarte. Una retícula de marcas por la que pasa una onda que
 * las voltea. Detrás de la onda se recuperan: el mercado no lo hace una
 * vez, lo hace todo el tiempo.
 */
const DiscardGrid: React.FC<{ height: number }> = ({ height }) => {
  const frame = useCurrentFrame();
  const { energy } = useVoice();
  const cols = 26;
  const rows = 7;
  const cw = W / cols;
  const rh = (height - 140) / rows;
  const sweep = ((frame * (2.2 + energy * 3)) % (W * 1.7)) - W * 0.35;
  const base = 14;

  return (
    <>
      {Array.from({ length: rows }).map((_, r) =>
        Array.from({ length: cols }).map((_, c) => {
          const x = c * cw + cw / 2;
          const y = 70 + r * rh + rh / 2;
          const seed = random(`dg-${r}-${c}`);
          // Distancia a la onda. Adentro la marca se achica hasta
          // desaparecer; atrás vuelve. Desplazarlas en vez de sacarlas
          // convertía la retícula en ruido: lo que hay que leer es que
          // faltan, no que se movieron.
          const d = (x + seed * 50 - sweep) / 200;
          const gone = Math.exp(-d * d * 2.2);
          const size = base * (1 - gone * 0.9);
          return (
            <div
              key={`${r}-${c}`}
              style={{
                position: 'absolute',
                left: Math.round(x - size / 2),
                top: Math.round(y - size / 2),
                width: Math.round(size),
                height: Math.round(size),
                border: `${STROKE}px solid ${COLOR.bone}`,
                opacity: 0.3 * (1 - gone * 0.85),
              }}
            />
          );
        }),
      )}
    </>
  );
};

/**
 * C5 · La convergencia. Dos familias de marcas que vienen de los bordes
 * y se encuentran en el eje. Prepara los dos círculos que llegan
 * después, sin adelantarlos.
 */
const ConvergeField: React.FC<{ height: number }> = ({ height }) => {
  const frame = useCurrentFrame();
  const { energy } = useVoice();
  const per = 14;
  const center = W / 2;

  return (
    <>
      {Array.from({ length: per * 2 }).map((_, i) => {
        const fromLeft = i < per;
        const k = i % per;
        const seed = random(`cf-${i}`);
        const cycle = (frame * (0.9 + energy * 1.4) + k * 90 + seed * 300) % 620;
        const t = cycle / 620;
        const dist = interpolate(t, [0, 1], [center - 40, 0], {
          easing: Easing.out(Easing.quad),
        });
        const x = fromLeft ? center - dist : center + dist;
        const y = 70 + seed * (height - 140);
        const len = 26 + seed * 40;
        // Se apagan al llegar: el encuentro es el punto, no el choque.
        const opacity = interpolate(t, [0, 0.75, 1], [0, 0.34 + seed * 0.2, 0]);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: Math.round(fromLeft ? x - len : x),
              top: Math.round(y),
              width: Math.round(len),
              height: STROKE,
              background: COLOR.bone,
              opacity,
            }}
          />
        );
      })}
      <div
        style={{
          position: 'absolute',
          left: Math.round(center),
          top: 50,
          bottom: 50,
          width: STROKE,
          background: COLOR.bone,
          opacity: 0.09,
        }}
      />
    </>
  );
};

const MOTIF = {
  filter: FilterStream,
  discard: DiscardGrid,
  converge: ConvergeField,
} as const;

export const MotionPane: React.FC<{
  motif: Motif;
  /** Frame en que el pane entra (revelado por máscara diagonal). */
  enterAt?: number;
  /** Frame en que el pane sale. */
  exitAt?: number;
}> = ({ motif, enterAt = 0, exitAt }) => {
  const frame = useCurrentFrame();
  const Motif = MOTIF[motif];

  const enter = interpolate(frame, [enterAt, enterAt + 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const exit = exitAt
    ? interpolate(frame, [exitAt, exitAt + 20], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : 1;
  const p = Math.min(enter, exit);
  if (p <= 0) return null;

  // Misma máscara diagonal que el pane de rostro: el corte del episodio
  // es siempre el mismo ángulo.
  const slant = Math.tan((WIPE_ANGLE * Math.PI) / 180) * 100;
  const y = interpolate(p, [0, 1], [100 + slant, 0]);

  return (
    <>
      <div
        style={{
          position: 'absolute',
          top: LAYOUT.seamY,
          left: 0,
          width: W,
          height: STROKE,
          background: COLOR.seam,
          opacity: p,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: PANE.y,
          left: 0,
          width: W,
          height: PANE.height,
          overflow: 'hidden',
          clipPath: `polygon(0% ${y + slant}%, 100% ${y}%, 100% 200%, 0% 200%)`,
        }}
      >
        <Motif height={PANE.height} />
        <VoiceTrace height={PANE.height} />
      </div>
    </>
  );
};
