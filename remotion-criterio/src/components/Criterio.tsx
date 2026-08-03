import React from 'react';
import { Easing, interpolate, useCurrentFrame } from 'remotion';
import { COLOR, STROKE, TABULAR, TYPE } from '../theme';
import { Counter, FadeUp, Reveal, useDraw, useSpringAt } from '../shared/anim';

/**
 * ContradictionPair — dos condiciones que no cierran.
 *
 * El error obvio acá sería una balanza. Una balanza dice "una pesa más",
 * y el argumento no es ese: es que las dos son verdad al mismo tiempo y
 * no pueden serlo. Por eso son dos bloques paralelos con un trazo que
 * intenta unirlos y NO cierra: queda un hueco visible en el medio.
 */
export const ContradictionPair: React.FC<{
  at: number;
  top: { label: string; value: string };
  bottom: { label: string; value: string; accent?: boolean };
  gapAt: number;
  width?: number;
}> = ({ at, top, bottom, gapAt, width = 936 }) => {
  const gap = useSpringAt(gapAt, 24);
  const linkLen = 180;
  const draw = useDraw(at + 40, 24, linkLen);

  return (
    <div style={{ width, position: 'relative' }}>
      <Panel at={at} {...top} />

      {/* El vínculo se dibuja, y después se parte por el medio. */}
      <svg width={width} height={linkLen} style={{ display: 'block' }}>
        <line
          x1={60}
          y1={0}
          x2={60}
          y2={linkLen}
          stroke={COLOR.bone}
          strokeWidth={STROKE}
          {...draw}
        />
        <rect
          x={40}
          y={linkLen / 2 - 20 * gap}
          width={40}
          height={40 * gap}
          fill={COLOR.bg}
        />
      </svg>

      <Panel at={at + 60} {...bottom} />
    </div>
  );
};

const Panel: React.FC<{
  at: number;
  label: string;
  value: string;
  accent?: boolean;
}> = ({ at, label, value, accent }) => (
  <div
    style={{
      border: `${STROKE}px solid ${accent ? COLOR.accent : COLOR.hairline}`,
      padding: '36px 40px',
    }}
  >
    <FadeUp at={at}>
      <div style={{ ...TYPE.label, color: accent ? COLOR.accent : COLOR.muted }}>{label}</div>
    </FadeUp>
    <Reveal at={at + 12} style={{ ...TYPE.displayM, color: accent ? COLOR.accent : COLOR.bone, marginTop: 18 }}>
      {value}
    </Reveal>
  </div>
);

/**
 * AccumulationContrast — información vs. error.
 *
 * Es el visual central del episodio y tenía que hacer una sola cosa:
 * mostrar que una columna se llena sola y la otra solo se llena cuando
 * algo se rompe.
 *
 * Izquierda: contador continuo, sin techo, sin costo.
 * Derecha: marcas discretas. Cada una entra de golpe y deja una muesca.
 * La asimetría de RITMO es el argumento, no la altura de las barras.
 */
export const AccumulationContrast: React.FC<{
  at: number;
  leftLabel: string;
  rightLabel: string;
  leftFoot: string;
  rightFoot: string;
  scars?: number;
  /**
   * Frames que dura el tramo. El VO decide cuánto se ve esto, así que el
   * ritmo de las dos columnas se estira o se comprime para terminar
   * adentro: si no, la izquierda se corta a media carga y la asimetría
   * —que es el argumento— no se llega a leer.
   */
  span?: number;
  width?: number;
  height?: number;
}> = ({
  at,
  leftLabel,
  rightLabel,
  leftFoot,
  rightFoot,
  scars = 7,
  span,
  width = 936,
  height = 720,
}) => {
  const frame = useCurrentFrame();
  const t = Math.max(0, frame - at);
  const colW = (width - 80) / 2;
  const lines = 90;
  const lineStep = span ? Math.max(1, (span * 0.72 - 20) / lines) : 3;
  const scarStep = span ? Math.max(6, (span * 0.82 - 60) / scars) : 42;

  return (
    <div style={{ width, position: 'relative' }}>
      <div style={{ display: 'flex', gap: 80 }}>
        {/* Información: flujo continuo, ilegible de tan denso. */}
        <div style={{ width: colW }}>
          <FadeUp at={at}>
            <div style={{ ...TYPE.label, marginBottom: 20 }}>{leftLabel}</div>
          </FadeUp>
          <div
            style={{
              height,
              border: `${STROKE}px solid ${COLOR.hairline}`,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {Array.from({ length: lines }).map((_, i) => {
              const on = t > 20 + i * lineStep;
              return (
                <div
                  key={i}
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    bottom: i * 8,
                    height: STROKE,
                    background: COLOR.bone,
                    opacity: on ? 0.55 : 0,
                  }}
                />
              );
            })}
          </div>
          <FadeUp at={at + 60} style={{ marginTop: 18 }}>
            <div style={TYPE.footnote}>{leftFoot}</div>
          </FadeUp>
        </div>

        {/* Error: pocas marcas, cada una a un costo. */}
        <div style={{ width: colW }}>
          <FadeUp at={at + 30}>
            <div style={{ ...TYPE.label, marginBottom: 20 }}>{rightLabel}</div>
          </FadeUp>
          <div
            style={{
              height,
              border: `${STROKE}px solid ${COLOR.hairline}`,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {Array.from({ length: scars }).map((_, i) => {
              const scarAt = at + 60 + i * scarStep;
              const p = interpolate(frame, [scarAt, scarAt + 6], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              });
              return (
                <div
                  key={i}
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    bottom: i * (height / scars) + 20,
                    height: 10,
                    background: COLOR.bone,
                    transform: `scaleX(${p})`,
                    transformOrigin: 'left center',
                  }}
                />
              );
            })}
          </div>
          <FadeUp at={at + 90} style={{ marginTop: 18 }}>
            <div style={TYPE.footnote}>{rightFoot}</div>
          </FadeUp>
        </div>
      </div>
    </div>
  );
};

/**
 * PriceCross — ejecución a cero, criterio hacia arriba.
 *
 * El cruce de curvas es un cliché de deck, pero acá el cruce ES la tesis
 * literal del bloque, así que se gana el lugar. Lo que lo saca del
 * cliché: sin ejes decorativos, sin grilla, sin gradiente, sin puntos
 * de dato. Dos trazos y el punto donde se cortan.
 */
export const PriceCross: React.FC<{
  at: number;
  labelDown: string;
  labelUp: string;
  width?: number;
  height?: number;
}> = ({ at, labelDown, labelUp, width = 936, height = 620 }) => {
  const down = useDraw(at, 60, 1200);
  const up = useDraw(at + 30, 60, 1200);
  const cross = useSpringAt(at + 78, 18);

  const cx = width * 0.52;
  const cy = height * 0.5;

  return (
    <div style={{ position: 'relative', width, height }}>
      <svg width={width} height={height}>
        <path
          d={`M 0 ${height * 0.12} C ${width * 0.4} ${height * 0.2}, ${width * 0.5} ${height * 0.72}, ${width} ${height * 0.94}`}
          fill="none"
          stroke={COLOR.bone}
          strokeWidth={STROKE * 2}
          {...down}
        />
        <path
          d={`M 0 ${height * 0.88} C ${width * 0.42} ${height * 0.84}, ${width * 0.56} ${height * 0.24}, ${width} ${height * 0.06}`}
          fill="none"
          stroke={COLOR.bone}
          strokeWidth={STROKE * 2}
          {...up}
        />
        <circle cx={cx} cy={cy} r={12 * cross} fill={COLOR.bone} />
      </svg>

      {/* Las etiquetas van FUERA de la caja del gráfico: adentro caían
          justo sobre el final de cada curva. */}
      <FadeUp
        at={at + 66}
        style={{ position: 'absolute', right: 0, bottom: -56, textAlign: 'right' }}
      >
        <div style={{ ...TYPE.label }}>{labelDown}</div>
      </FadeUp>
      <FadeUp at={at + 96} style={{ position: 'absolute', right: 0, top: -46, textAlign: 'right' }}>
        <div style={{ ...TYPE.label }}>{labelUp}</div>
      </FadeUp>
    </div>
  );
};

/**
 * HabitFilter — el filtro entre costumbre y criterio.
 *
 * Sin este visual el bloque queda vendiendo "la experiencia vale", que
 * es justo lo que el guion NO dice. El filtro es el matiz: entran años,
 * y solo pasa lo que sobrevive al cambio de cancha.
 */
export const HabitFilter: React.FC<{
  at: number;
  rejected: string;
  passes: string[];
  /** Frame de cada línea que pasa el filtro. Sin esto, van escalonadas. */
  passAts?: number[];
  width?: number;
}> = ({ at, rejected, passes, passAts, width = 936 }) => {
  const gate = useSpringAt(at + 24, 24);

  return (
    <div style={{ width }}>
      {/* USO DEL ACENTO: costumbre. Es el villano del bloque —lo que
          se disfraza de criterio y no lo es. */}
      <FadeUp at={at}>
        <div
          style={{
            border: `${STROKE}px dashed ${COLOR.accent}`,
            padding: '28px 34px',
            ...TYPE.displayM,
            // Después del spread: displayM trae el color hueso y se comía
            // el acento, que es justo lo que este bloque tiene que marcar.
            color: COLOR.accent,
            fontSize: 56,
            display: 'inline-block',
          }}
        >
          {rejected}
        </div>
      </FadeUp>

      <svg width={width} height={120} style={{ display: 'block', margin: '20px 0' }}>
        <line
          x1={0}
          y1={60}
          x2={width * gate}
          y2={60}
          stroke={COLOR.hairline}
          strokeWidth={STROKE}
        />
        {[0.2, 0.4, 0.6, 0.8].map((f) => (
          <line
            key={f}
            x1={width * f}
            y1={30}
            x2={width * f}
            y2={90}
            stroke={COLOR.hairline}
            strokeWidth={STROKE}
            opacity={gate}
          />
        ))}
      </svg>

      {passes.map((p, i) => (
        <FadeUp key={p} at={passAts?.[i] ?? at + 60 + i * 48} from="left" style={{ marginBottom: 22 }}>
          <div style={{ ...TYPE.body, fontSize: 44 }}>{p}</div>
        </FadeUp>
      ))}
    </div>
  );
};

/**
 * ProductiveLife — la línea de vida productiva con el tramo descartado.
 *
 * El dato del guion es que el mercado saca de juego a alguien con veinte
 * o treinta años productivos por delante. Una barra con un tramo cortado
 * lo dice sin adjetivos.
 */
export const ProductiveLife: React.FC<{
  at: number;
  cutAt: number;
  width?: number;
}> = ({ at, cutAt, width = 936 }) => {
  const bar = useSpringAt(at, 36);
  const cut = useSpringAt(cutAt, 24);
  const barH = 96;
  const cutFrom = 0.62; // ~45 años sobre una línea de 20 a 85

  return (
    <div style={{ width, position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={TYPE.footnote}>20</div>
        <div style={TYPE.footnote}>45</div>
        <div style={TYPE.footnote}>65</div>
        <div style={TYPE.footnote}>85</div>
      </div>

      <div style={{ position: 'relative', height: barH, width }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: barH,
            width: Math.round(width * bar),
            background: COLOR.bone,
          }}
        />
        {/* USO DEL ACENTO: el tramo que el mercado descarta. */}
        <div
          style={{
            position: 'absolute',
            left: Math.round(width * cutFrom),
            top: 0,
            height: barH,
            width: Math.round(width * (1 - cutFrom) * cut),
            background: COLOR.bg,
            border: `${STROKE}px dashed ${COLOR.accent}`,
            boxSizing: 'border-box',
          }}
        />
      </div>

      <FadeUp at={cutAt + 24} style={{ marginTop: 24 }}>
        <div style={{ ...TYPE.label, color: COLOR.accent }}>
          Descartado
        </div>
      </FadeUp>
    </div>
  );
};

/** Dos etiquetas de precio enfrentadas. El absurdo, sin adjetivos. */
export const PriceTags: React.FC<{
  at: number;
  rows: { what: string; price: string; note: string }[];
  /** Frame de cada fila. Cada precio entra cuando el VO lo nombra. */
  ats?: number[];
  width?: number;
}> = ({ at, rows, ats, width = 936 }) => (
  <div style={{ width }}>
    {rows.map((r, i) => (
      <FadeUp key={r.what} at={ats?.[i] ?? at + i * 72} style={{ marginBottom: 48 }}>
        <div
          style={{
            borderTop: `${STROKE}px solid ${COLOR.hairline}`,
            paddingTop: 26,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            gap: 32,
          }}
        >
          <div style={{ maxWidth: 500 }}>
            <div style={{ ...TYPE.displayM, fontSize: 50 }}>{r.what}</div>
            <div style={{ ...TYPE.footnote, marginTop: 12 }}>{r.note}</div>
          </div>
          <div style={{ ...TYPE.displayM, ...TABULAR, fontSize: 50 }}>{r.price}</div>
        </div>
      </FadeUp>
    ))}
  </div>
);

/**
 * TwoHalves — la firma del episodio.
 *
 * Dos círculos que nunca se tocaron y ahora sí. El solape es lo único
 * en todo el video que se lee como salida, y por eso se lleva el cuarto
 * y último uso del acento: rojo = activación.
 *
 * Deliberadamente NO es un diagrama de Venn con etiqueta en el medio.
 * El área compartida se pinta sola y se queda vacía: lo que va ahí lo
 * pone el espectador.
 */
export const TwoHalves: React.FC<{
  at: number;
  mergeAt: number;
  left: string;
  right: string;
  /** Frames de cada etiqueta: entran cuando el VO nombra cada mitad. */
  leftAt?: number;
  rightAt?: number;
  width?: number;
  height?: number;
}> = ({ at, mergeAt, left, right, leftAt, rightAt, width = 936, height = 620 }) => {
  const appear = useSpringAt(at, 24);
  const merge = useSpringAt(mergeAt, 36);

  const r = 220;
  const spread = interpolate(merge, [0, 1], [1.0, 0.42]);
  const cyBase = height / 2;
  const lx = width / 2 - r * spread;
  const rx = width / 2 + r * spread;

  return (
    <div style={{ position: 'relative', width, height }}>
      <svg width={width} height={height}>
        <defs>
          <clipPath id="halves-left">
            <circle cx={lx} cy={cyBase} r={r * appear} />
          </clipPath>
        </defs>
        <circle
          cx={lx}
          cy={cyBase}
          r={r * appear}
          fill="none"
          stroke={COLOR.bone}
          strokeWidth={STROKE * 2}
        />
        <circle
          cx={rx}
          cy={cyBase}
          r={r * appear}
          fill="none"
          stroke={COLOR.bone}
          strokeWidth={STROKE * 2}
        />
        {/* El solape: se pinta solo cuando los círculos ya se tocaron. */}
        <g clipPath="url(#halves-left)">
          <circle
            cx={rx}
            cy={cyBase}
            r={r * appear}
            fill={COLOR.accent}
            opacity={merge * 0.9}
          />
        </g>
      </svg>

      <FadeUp
        at={leftAt ?? at + 24}
        style={{ position: 'absolute', left: 0, top: cyBase + r - 20, width: 340 }}
      >
        <div style={{ ...TYPE.label }}>{left}</div>
      </FadeUp>
      <FadeUp
        at={rightAt ?? at + 48}
        style={{
          position: 'absolute',
          right: 0,
          top: cyBase + r - 20,
          width: 340,
          textAlign: 'right',
        }}
      >
        <div style={{ ...TYPE.label }}>{right}</div>
      </FadeUp>
    </div>
  );
};

/** Contador de coste mensual. Una sola cifra, sin adorno. */
export const PriceKey: React.FC<{ at: number; amount: number; caption: string }> = ({
  at,
  amount,
  caption,
}) => (
  <div>
    <Reveal at={at} style={{ ...TYPE.displayXL, ...TABULAR }}>
      <Counter at={at} duration={30} to={amount} format={(n) => `USD ${Math.round(n)}`} />
    </Reveal>
    <FadeUp at={at + 24} style={{ marginTop: 24 }}>
      <div style={TYPE.footnote}>{caption}</div>
    </FadeUp>
  </div>
);
