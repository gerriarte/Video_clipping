import React from 'react';
import { Easing, interpolate, random, useCurrentFrame } from 'remotion';
import { COLOR, STROKE, TABULAR, TYPE } from '../theme';
import { Counter, FadeUp, Reveal, useSpringAt } from '../shared/anim';

/**
 * RPMGauge — arco de 240°, variante vertical.
 * Sin rojo: este número es evidencia, no villano.
 */
export const ArcGauge: React.FC<{
  at: number;
  value: number;
  size?: number;
  suffix?: string;
}> = ({ at, value, size = 720, suffix = '%' }) => {
  const p = useSpringAt(at, 48);
  const r = size / 2 - 40;
  const cx = size / 2;
  const cy = size / 2;
  const sweep = 240;
  const start = 150;

  const polar = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };

  const a0 = polar(start);
  const a1 = polar(start + sweep);
  const arcLen = (sweep / 360) * 2 * Math.PI * r;

  const needleDeg = start + (sweep * value * p) / 100;
  const n = polar(needleDeg);

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size}>
        <path
          d={`M ${a0.x} ${a0.y} A ${r} ${r} 0 1 1 ${a1.x} ${a1.y}`}
          fill="none"
          stroke={COLOR.hairline}
          strokeWidth={STROKE}
        />
        <path
          d={`M ${a0.x} ${a0.y} A ${r} ${r} 0 1 1 ${a1.x} ${a1.y}`}
          fill="none"
          stroke={COLOR.bone}
          strokeWidth={STROKE * 2}
          strokeDasharray={arcLen}
          strokeDashoffset={arcLen * (1 - (value * p) / 100)}
          strokeLinecap="butt"
        />
        {/* Marcas cada 10 unidades */}
        {Array.from({ length: 11 }).map((_, i) => {
          const d = start + (sweep * i) / 10;
          const o = polar(d);
          const inner = {
            x: cx + (r - 18) * Math.cos((d * Math.PI) / 180),
            y: cy + (r - 18) * Math.sin((d * Math.PI) / 180),
          };
          return (
            <line
              key={i}
              x1={inner.x}
              y1={inner.y}
              x2={o.x}
              y2={o.y}
              stroke={COLOR.hairline}
              strokeWidth={STROKE}
            />
          );
        })}
        <line
          x1={cx}
          y1={cy}
          x2={n.x}
          y2={n.y}
          stroke={COLOR.bone}
          strokeWidth={STROKE * 2}
        />
        <circle cx={cx} cy={cy} r={10} fill={COLOR.bone} />
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          paddingTop: 120,
        }}
      >
        <div style={{ ...TYPE.displayXL, ...TABULAR }}>
          <Counter at={at} duration={48} to={value} format={(x) => Math.round(x).toString()} />
          {suffix}
        </div>
      </div>
    </div>
  );
};

/** Barras comparativas apiladas. */
export const ComparativeBars: React.FC<{
  at: number;
  rows: { label: string; value: number }[];
  width?: number;
  stagger?: number;
}> = ({ at, rows, width = 936, stagger = 60 }) => (
  <div style={{ width }}>
    {rows.map((r, i) => (
      <Bar key={r.label} {...r} at={at + i * stagger} width={width} />
    ))}
  </div>
);

const Bar: React.FC<{
  at: number;
  label: string;
  value: number;
  width: number;
}> = ({ at, label, value, width }) => {
  const p = useSpringAt(at + 12, 30);
  return (
    <div style={{ marginBottom: 44 }}>
      <FadeUp at={at}>
        <div style={{ ...TYPE.label, marginBottom: 16 }}>{label}</div>
      </FadeUp>
      <div
        style={{
          width: Math.round(width * (value / 100) * p),
          height: 80,
          background: COLOR.bone,
        }}
      />
    </div>
  );
};

/** Badge que cicla estados de confianza. El tercero es el único rojo. */
export const ConfidenceBadge: React.FC<{
  at: number;
  states: { text: string; accent?: boolean }[];
  hold?: number;
}> = ({ at, states, hold = 90 }) => {
  const frame = useCurrentFrame();
  const i = Math.min(states.length - 1, Math.floor((frame - at) / hold));
  if (frame < at) return null;
  const s = states[Math.max(0, i)];

  return (
    <div
      style={{
        display: 'inline-block',
        padding: '18px 34px',
        border: `${STROKE}px solid ${s.accent ? COLOR.accent : COLOR.bone}`,
        color: s.accent ? COLOR.accent : COLOR.bone,
        ...TYPE.label,
        fontSize: 34,
      }}
    >
      {s.text}
    </div>
  );
};

/**
 * Grilla de 1.000 personas → 1.000 agentes.
 * El gemelo desplazado lee como "duplicación", no como sombra: por eso
 * va en X e Y, no solo en Y, y a 45% de opacidad, no a 20%.
 */
export const PersonGrid: React.FC<{
  at: number;
  cols?: number;
  rows?: number;
  dot?: number;
  gap?: number;
  /** Frame en que aparecen los gemelos. */
  twinAt?: number;
  /** Frame en que la grilla se desatura y baja a segundo plano. */
  recedeAt?: number;
}> = ({ at, cols = 25, rows = 40, dot = 8, gap = 24, twinAt, recedeAt }) => {
  const frame = useCurrentFrame();
  const total = cols * rows;

  const twin = twinAt
    ? interpolate(frame, [twinAt, twinAt + 24], [0, 0.45], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 0;

  const recede = recedeAt
    ? interpolate(frame, [recedeAt, recedeAt + 30], [1, 0.22], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : 1;
  const scale = recedeAt
    ? interpolate(frame, [recedeAt, recedeAt + 30], [1, 0.85], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : 1;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, ${dot}px)`,
        gap,
        justifyContent: 'center',
        opacity: recede,
        transform: `scale(${scale})`,
        transformOrigin: 'center',
      }}
    >
      {Array.from({ length: total }).map((_, i) => {
        const on = frame >= at + i * 0.35;
        if (!on) return <div key={i} style={{ width: dot, height: dot }} />;
        return (
          <div key={i} style={{ width: dot, height: dot, position: 'relative' }}>
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: COLOR.bone,
                borderRadius: '50%',
              }}
            />
            {twin > 0 && (
              <div
                style={{
                  position: 'absolute',
                  left: 7,
                  top: 7,
                  width: dot,
                  height: dot,
                  background: COLOR.bone,
                  opacity: twin,
                  borderRadius: '50%',
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};

/**
 * Smallville: grilla isométrica + 25 agentes que se agrupan en clusters.
 * El random es determinístico (seed fijo) para que el render sea
 * reproducible entre pasadas.
 */
export const Smallville: React.FC<{
  at: number;
  clusterAt: number;
  highlightAt?: number;
  width?: number;
  height?: number;
}> = ({ at, clusterAt, highlightAt, width = 1080, height = 900 }) => {
  const frame = useCurrentFrame();
  const clusterP = useSpringAt(clusterAt, 36);

  const agents = Array.from({ length: 25 }).map((_, i) => {
    const x0 = 100 + random(`sv-x-${i}`) * (width - 200);
    const y0 = 80 + random(`sv-y-${i}`) * (height - 160);
    const cluster = i % 6;
    const cxT = 140 + (cluster % 3) * ((width - 280) / 2);
    const cyT = 180 + Math.floor(cluster / 3) * ((height - 360) / 1);
    return {
      i,
      cluster,
      x: x0 + (cxT - x0) * clusterP,
      y: y0 + (cyT - y0) * clusterP,
      on: frame >= at + i * 8,
    };
  });

  const highlighted = highlightAt !== undefined && frame >= highlightAt ? 2 : null;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {/* Grilla isométrica de fondo */}
      <g stroke={COLOR.hairline} strokeWidth={STROKE} opacity={0.45}>
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={`a${i}`} x1={-200 + i * 120} y1={height} x2={200 + i * 120} y2={0} />
        ))}
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={`b${i}`} x1={-200 + i * 120} y1={0} x2={200 + i * 120} y2={height} />
        ))}
      </g>

      {/* Vínculos dentro del cluster */}
      {clusterP > 0.4 &&
        agents.map((a) =>
          agents
            .filter((b) => b.i > a.i && b.cluster === a.cluster)
            .map((b) => (
              <line
                key={`${a.i}-${b.i}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={COLOR.bone}
                strokeWidth={STROKE}
                opacity={(clusterP - 0.4) * 0.4}
              />
            )),
        )}

      {agents.map((a) => (
        <circle
          key={a.i}
          cx={a.x}
          cy={a.y}
          r={10}
          fill={COLOR.bone}
          opacity={
            !a.on ? 0 : highlighted !== null ? (a.cluster === highlighted ? 1 : 0.4) : 1
          }
        />
      ))}
    </svg>
  );
};
