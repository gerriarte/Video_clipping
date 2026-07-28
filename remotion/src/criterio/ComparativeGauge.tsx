/**
 * ComparativeGauge — dos medidores que se cruzan.
 *
 * Componente del design system: no sabe nada de "Criterio" en particular, solo
 * hereda theme.ts. En M4 compara "sueldos de guerra (junior)" contra "criterio
 * a precio de remate": dos barras que arrancan invertidas y se cruzan en algún
 * punto de la animación. El cruce es el argumento — por eso se marca.
 */
import React from "react";
import { Easing, useCurrentFrame } from "remotion";
import { COLORS, FONT, TRACKING, TYPE, bone } from "./theme";
import { Kicker, MaskReveal, ramp, type Span } from "./primitives";
import { frames } from "./timing";

export interface GaugeSeries {
  label: string;
  /** Aclaración chica bajo la etiqueta. */
  note?: string;
  /** Valor al inicio de la animación, en unidades reales. */
  from: number;
  /** Valor al final. */
  to: number;
  color?: string;
}

const TICKS = 10;

/**
 * Una fila del medidor: etiqueta ARRIBA de la pista, después pista, relleno y
 * lectura numérica. En 9:16 no hay lugar para una columna de etiquetas al
 * costado — se comería un tercio del ancho útil.
 */
const GaugeRow: React.FC<{
  sr: GaugeSeries;
  value: number;
  scaleMax: number;
  entry: Span;
  delay: number;
  trackW: number;
  barHeight: number;
  ticksAt: "top" | "bottom";
  format: (n: number) => string;
}> = ({ sr, value, scaleMax, entry, delay, trackW, barHeight, ticksAt, format }) => {
  const frame = useCurrentFrame();
  const own: Span = { from: entry.from + delay, to: entry.to + delay };
  const grow = ramp(frame, own);
  const w = grow * Math.max(0, Math.min(1, value / scaleMax)) * trackW;
  const color = sr.color ?? COLORS.bone;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <MaskReveal span={own} travel={14}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <Kicker color={color} style={{ letterSpacing: TRACKING.label }}>
            {sr.label}
          </Kicker>
          {sr.note ? (
            <div style={{ fontFamily: FONT.body, fontSize: 30, color: COLORS.boneDim }}>
              {sr.note}
            </div>
          ) : null}
        </div>
      </MaskReveal>

      <div style={{ position: "relative", width: trackW, height: barHeight }}>
        {/* Pista vacía: se dibuja de izquierda a derecha. */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            border: `1px solid ${bone(0.1)}`,
            clipPath: `inset(0 ${(1 - grow) * 100}% 0 0)`,
          }}
        />
        {Array.from({ length: TICKS - 1 }, (_, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              left: ((i + 1) / TICKS) * trackW,
              top: ticksAt === "top" ? 0 : barHeight - 10,
              width: 1,
              height: 10,
              backgroundColor: bone(0.14),
              opacity: grow,
            }}
          />
        ))}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            height: barHeight,
            width: w,
            backgroundColor: color,
            opacity: 0.92,
          }}
        />
        {/* Lectura numérica, siempre mono, pegada al extremo de la barra. */}
        <div
          style={{
            position: "absolute",
            left: w + 24,
            top: barHeight / 2 - 26,
            fontFamily: FONT.mono,
            fontSize: 46,
            fontWeight: 500,
            color,
            opacity: ramp(frame, { from: own.to, to: own.to + frames(0.27) }),
            whiteSpace: "nowrap",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {format(value)}
        </div>
      </div>
    </div>
  );
};

export const ComparativeGauge: React.FC<{
  series: [GaugeSeries, GaugeSeries];
  /** Tope de la escala, en las mismas unidades que from/to. */
  scaleMax: number;
  /** Cuándo se dibujan las pistas vacías. */
  entry: Span;
  /** Cuándo se mueven los valores. */
  fill: Span;
  format?: (n: number) => string;
  width?: number;
  barHeight?: number;
  /** Etiqueta del marcador de cruce. Si falta, el cruce no se rotula. */
  crossLabel?: string;
}> = ({
  series,
  scaleMax,
  entry,
  fill,
  format = (n) => Math.round(n).toLocaleString("es-AR"),
  width = 912,
  barHeight = 88,
  crossLabel,
}) => {
  const frame = useCurrentFrame();
  const [a, b] = series;

  // Lineal a propósito. Con la curva expo-out del resto del episodio las barras
  // llegan al 80% de su valor en el primer cuarto del tiempo y el cruce pasa
  // volando — y el cruce es el argumento. Lineal también hace que el frame del
  // cruce se pueda calcular exacto, sin invertir la curva.
  const t = ramp(frame, fill, [0, 1], Easing.linear);
  const valueOf = (sr: GaugeSeries) => sr.from + (sr.to - sr.from) * t;

  // Progreso en el que las dos series valen lo mismo. Si el denominador es 0
  // las rectas son paralelas y no hay cruce que marcar.
  const denom = a.to - a.from - (b.to - b.from);
  const tCross = denom === 0 ? -1 : (b.from - a.from) / denom;
  const hasCross = tCross > 0 && tCross < 1;
  const crossValue = hasCross ? a.from + (a.to - a.from) * tCross : 0;
  const crossFrame = fill.from + tCross * (fill.to - fill.from);
  const crossIn = hasCross
    ? ramp(frame, { from: crossFrame, to: crossFrame + frames(0.33) })
    : 0;

  const trackW = width;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 132, position: "relative" }}>
      <GaugeRow
        sr={a}
        value={valueOf(a)}
        scaleMax={scaleMax}
        entry={entry}
        delay={0}
        trackW={trackW}
        barHeight={barHeight}
        ticksAt="top"
        format={format}
      />
      <GaugeRow
        sr={b}
        value={valueOf(b)}
        scaleMax={scaleMax}
        entry={entry}
        delay={frames(0.2)}
        trackW={trackW}
        barHeight={barHeight}
        ticksAt="bottom"
        format={format}
      />

      {/* Marcador de cruce: la línea vertical donde las dos series valen igual. */}
      {hasCross && crossIn > 0 ? (
        <div
          style={{
            position: "absolute",
            left: (crossValue / scaleMax) * trackW,
            top: -20,
            bottom: -46,
            width: 1,
            backgroundColor: bone(0.55 * crossIn),
          }}
        >
          {crossLabel ? (
            <div
              style={{
                position: "absolute",
                bottom: -30,
                left: 12,
                fontFamily: FONT.body,
                fontWeight: 600,
                fontSize: TYPE.label - 4,
                letterSpacing: TRACKING.label,
                textTransform: "uppercase",
                color: bone(0.55 * crossIn),
                whiteSpace: "nowrap",
              }}
            >
              {crossLabel}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};
