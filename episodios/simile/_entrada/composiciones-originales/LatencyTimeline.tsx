import React from 'react';
import { Easing, interpolate, useCurrentFrame } from 'remotion';
import { COLOR, LAYOUT, STROKE, TYPE } from '../theme';
import { Reveal, useDraw } from '../shared/anim';

/**
 * Variante VERTICAL del LatencyTimeline de la serie.
 *
 * En horizontal esto era una barra de progreso con 5 bloques. A 1080px
 * de ancho una barra de 5 segmentos deja cada label ilegible, así que
 * el eje rota: columna de filas, label a la izquierda, trazo a la derecha.
 * El tiempo se lee hacia abajo, que además es la dirección natural del
 * scroll y del formato.
 */
export const LatencyTimelineVertical: React.FC<{
  steps: { label: string; at: number }[];
  /** Frame en que el conjunto se comprime para hacer lugar abajo. */
  collapseAt?: number;
  rowHeight?: number;
}> = ({ steps, collapseAt, rowHeight = 120 }) => {
  const frame = useCurrentFrame();

  const collapse = collapseAt
    ? interpolate(frame, [collapseAt, collapseAt + 24], [1, 0.55], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : 1;
  const dim = collapseAt
    ? interpolate(frame, [collapseAt, collapseAt + 24], [1, 0.4], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 1;

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: LAYOUT.margin,
        width: LAYOUT.contentWidth,
        transform: `scaleY(${collapse})`,
        transformOrigin: 'top left',
        opacity: dim,
      }}
    >
      {steps.map((s, i) => (
        <Row key={s.label} {...s} height={rowHeight} index={i} />
      ))}
    </div>
  );
};

const Row: React.FC<{ label: string; at: number; height: number; index: number }> = ({
  label,
  at,
  height,
  index,
}) => {
  const lineLength = 520;
  const draw = useDraw(at + 6, 24, lineLength);

  return (
    <div
      style={{
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderTop: index === 0 ? 'none' : `${STROKE}px solid ${COLOR.hairline}`,
      }}
    >
      <Reveal at={at} style={{ ...TYPE.displayM }} tracking="-0.02em">
        {label}
      </Reveal>
      <svg width={lineLength} height={STROKE} style={{ flexShrink: 0 }}>
        {/* El trazo se dibuja de derecha a izquierda: el tiempo avanza
            hacia el label, no desde él. */}
        <line
          x1={lineLength}
          y1={STROKE / 2}
          x2={0}
          y2={STROKE / 2}
          stroke={COLOR.bone}
          strokeWidth={STROKE}
          {...draw}
        />
      </svg>
    </div>
  );
};
