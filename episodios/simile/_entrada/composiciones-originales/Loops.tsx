import React from 'react';
import { Easing, interpolate, useCurrentFrame } from 'remotion';
import { COLOR, STROKE, TABULAR, TYPE } from '../theme';
import { Reveal, useDraw, useSpringAt } from '../shared/anim';

/**
 * SeriesMap — variante ROMBO para 9:16.
 *
 * El loop circular horizontal desperdicia el alto del formato. En rombo,
 * los 4 nodos usan todo el pane y la lectura sigue siendo cíclica.
 *
 * El loop ACELERA: primera vuelta 240f, converge a 30f. Esa aceleración
 * es el argumento del bloque —el costo por vuelta se derrumba— así que
 * es contenido, no adorno.
 */
export const LoopDiamond: React.FC<{
  at: number;
  nodes: [string, string, string, string];
  width?: number;
  height?: number;
  firstLap?: number;
  lastLap?: number;
  laps?: number;
}> = ({ at, nodes, width = 936, height = 880, firstLap = 240, lastLap = 30, laps = 14 }) => {
  const frame = useCurrentFrame();
  const t = Math.max(0, frame - at);

  // Acumular vueltas con duración decreciente.
  let elapsed = 0;
  let lap = 0;
  let lapDuration = firstLap;
  while (lap < laps) {
    lapDuration = interpolate(lap, [0, laps - 1], [firstLap, lastLap], {
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });
    if (elapsed + lapDuration > t) break;
    elapsed += lapDuration;
    lap++;
  }
  const lapProgress = Math.min(1, (t - elapsed) / lapDuration);
  const angle = (lap + lapProgress) * Math.PI * 2 - Math.PI / 2;

  const cx = width / 2;
  const cy = height / 2;
  const rx = width / 2 - 60;
  const ry = height / 2 - 90;

  // Vértices del rombo: arriba, derecha, abajo, izquierda.
  const pts = [
    { x: cx, y: cy - ry },
    { x: cx + rx, y: cy },
    { x: cx, y: cy + ry },
    { x: cx - rx, y: cy },
  ];

  // Posición del marcador sobre el perímetro del rombo.
  const seg = ((angle + Math.PI / 2) / (Math.PI * 2)) % 1;
  const segIndex = Math.floor(seg * 4);
  const segT = seg * 4 - segIndex;
  const a = pts[segIndex];
  const b = pts[(segIndex + 1) % 4];
  const mx = a.x + (b.x - a.x) * segT;
  const my = a.y + (b.y - a.y) * segT;

  const perimeter = 4 * Math.hypot(rx, ry);
  const draw = useDraw(at, 36, perimeter);

  return (
    <div style={{ position: 'relative', width, height }}>
      <svg width={width} height={height} style={{ position: 'absolute', inset: 0 }}>
        <polygon
          points={pts.map((p) => `${p.x},${p.y}`).join(' ')}
          fill="none"
          stroke={COLOR.hairline}
          strokeWidth={STROKE}
          {...draw}
        />
        <circle cx={mx} cy={my} r={9} fill={COLOR.bone} />
      </svg>

      {pts.map((p, i) => (
        <div
          key={nodes[i]}
          style={{
            position: 'absolute',
            left: p.x,
            top: p.y,
            transform: 'translate(-50%, -50%)',
            background: COLOR.bg,
            padding: '14px 22px',
            border: `${STROKE}px solid ${COLOR.hairline}`,
            whiteSpace: 'nowrap',
          }}
        >
          <Reveal at={at + 12 + i * 12} style={{ ...TYPE.label }} tracking="0.08em">
            {nodes[i]}
          </Reveal>
        </div>
      ))}

      {/* Contador de vueltas. Es el dato del bloque: cuántas veces
          podés dar la vuelta cuando cada vuelta cuesta casi cero. */}
      <div style={{ position: 'absolute', right: 0, top: 0, textAlign: 'right' }}>
        <div style={{ ...TYPE.footnote }}>VUELTAS</div>
        <div style={{ ...TYPE.displayL, ...TABULAR, fontSize: 84 }}>
          {String(Math.max(1, lap + 1)).padStart(2, '0')}
        </div>
      </div>
    </div>
  );
};

/**
 * Ciclo del agente generativo — columna descendente con retorno lateral.
 * El circular no entra bien en 1080 de ancho con 5 labels legibles.
 */
export const AgentLoop: React.FC<{
  at: number;
  nodes: string[];
  stagger?: number;
  /** Frame en que el circuito pulsa una vez recorriendo el loop. */
  pulseAt?: number;
  width?: number;
}> = ({ at, nodes, stagger = 90, pulseAt, width = 720 }) => {
  const frame = useCurrentFrame();
  const nodeH = 110;
  const gap = 40;
  const closeAt = at + nodes.length * stagger;
  const returnP = useSpringAt(closeAt, 36);

  const totalH = nodes.length * nodeH + (nodes.length - 1) * gap;

  const pulsePos = pulseAt
    ? interpolate(frame, [pulseAt, pulseAt + 120], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : null;

  return (
    <div style={{ position: 'relative', width: width + 200, height: totalH }}>
      {nodes.map((n, i) => {
        const nodeAt = at + i * stagger;
        const y = i * (nodeH + gap);
        const isPulsing =
          pulsePos !== null &&
          pulsePos > i / (nodes.length + 1) &&
          pulsePos < (i + 1.2) / (nodes.length + 1);

        return (
          <React.Fragment key={n}>
            <div
              style={{
                position: 'absolute',
                top: y,
                left: 0,
                width,
                height: nodeH,
                border: `${STROKE}px solid ${isPulsing ? COLOR.bone : COLOR.hairline}`,
                display: 'flex',
                alignItems: 'center',
                paddingLeft: 32,
                background: COLOR.bg,
              }}
            >
              <Reveal at={nodeAt} style={{ ...TYPE.displayM, fontSize: 52 }} tracking="-0.02em">
                {n}
              </Reveal>
            </div>
            {i < nodes.length - 1 && (
              <Arrow at={nodeAt + 24} x={60} y={y + nodeH} length={gap} />
            )}
          </React.Fragment>
        );
      })}

      {/* Retorno: sale por la derecha del último nodo, sube y vuelve al
          primero. Cerrar el circuito visualmente es lo que convierte
          cinco cajas en un agente. */}
      <svg
        width={width + 200}
        height={totalH}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      >
        <path
          d={`M ${width} ${totalH - nodeH / 2} H ${width + 120} V ${nodeH / 2} H ${width}`}
          fill="none"
          stroke={COLOR.bone}
          strokeWidth={STROKE}
          strokeDasharray={1000}
          strokeDashoffset={1000 * (1 - returnP)}
        />
      </svg>
    </div>
  );
};

const Arrow: React.FC<{ at: number; x: number; y: number; length: number }> = ({
  at,
  x,
  y,
  length,
}) => {
  const draw = useDraw(at, 12, length);
  return (
    <svg
      width={20}
      height={length}
      style={{ position: 'absolute', top: y, left: x }}
    >
      <line
        x1={10}
        y1={0}
        x2={10}
        y2={length}
        stroke={COLOR.bone}
        strokeWidth={STROKE}
        {...draw}
      />
    </svg>
  );
};
