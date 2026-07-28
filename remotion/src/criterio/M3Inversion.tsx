/**
 * M3 — LA INVERSIÓN   ·   frames 2700–4500   ·   1:30–2:30
 *
 * Beat: los precios se movieron, y el filtro que eso deja.
 *
 * FRAME GUIDES (locales a la Sequence)
 *   15–54      ejes + etiquetas EJECUCIÓN / CRITERIO
 *   60–210     la curva de EJECUCIÓN colapsa hacia cero
 *   96–252     la curva de CRITERIO se dispara y cruza a la otra
 *   240–270    toque de rojo en el tope de CRITERIO
 *   285–324    la regla al pie
 *   450–486    el data-moment se va
 *   492–528    cabeceras SE DEPRECIÓ / SE APRECIÓ
 *   552–…      filas, de a una, cada 108 frames
 *   1440–1482  la tabla se va
 *   1488–1542  sello del movimiento
 *
 * ROJO: solo el tope de la curva de CRITERIO. Nada más.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS, CONTENT_W, FONT, TYPE, ZONE, bone, red } from "./theme";
import { Backdrop, Kicker, MaskReveal, ramp, type Span } from "./primitives";
import { KineticText } from "./KineticText";
import { FilterTable, type FilterTableTiming } from "./FilterTable";
import { M3, SAFE_X, WIDTH, frames } from "./timing";
import type { CriterioProps } from "./schema";

// ═══ DATA-MOMENT · las dos curvas de precio ══════════════════════════════════

/**
 * Caja del gráfico. Ocupa el ancho útil y casi todo el alto entre las etiquetas:
 * en vertical el gráfico tiene que ser alto, no ancho, o queda como una franja
 * perdida en el medio del frame.
 */
const PLOT = { x1: 150, y1: 420, x2: 930, y2: 1500 };

/** Lo abundante se abarata: arranca arriba y termina pegado al piso. */
const EXEC_PATH = "M 150 486 C 400 546, 590 1300, 930 1462";
/** El valor migra a lo escaso: arranca abajo y se va del techo. */
const CRIT_PATH = "M 150 1436 C 424 1408, 620 830, 930 440";
/** Punto final de CRIT_PATH: donde va el toque de rojo. */
const CRIT_PEAK = { x: 930, y: 440 };

/**
 * Traza un path progresivamente. `pathLength={1}` normaliza la longitud, así
 * no hay que medir el path en runtime ni depender del DOM.
 */
const DrawnPath: React.FC<{
  d: string;
  span: Span;
  color: string;
  width?: number;
}> = ({ d, span, color, width = 5 }) => {
  const frame = useCurrentFrame();
  const p = ramp(frame, span);
  if (p <= 0) return null;
  return (
    <path
      d={d}
      pathLength={1}
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      strokeDasharray={1}
      strokeDashoffset={1 - p}
    />
  );
};

const PriceChart: React.FC<{ data: CriterioProps["m3"]; alive: number }> = ({ data, alive }) => {
  const frame = useCurrentFrame();
  const axes = ramp(frame, M3.axes);
  const peak = ramp(frame, M3.critPeak);

  return (
    <AbsoluteFill style={{ opacity: alive }}>
      <svg width={WIDTH} height={1920}>
        {/* Ejes: presencia mínima, solo para que las curvas tengan suelo. */}
        <line
          x1={PLOT.x1}
          y1={PLOT.y2}
          x2={PLOT.x1 + (PLOT.x2 - PLOT.x1) * axes}
          y2={PLOT.y2}
          stroke={bone(0.14)}
          strokeWidth={1}
        />
        <line
          x1={PLOT.x1}
          y1={PLOT.y2}
          x2={PLOT.x1}
          y2={PLOT.y2 - (PLOT.y2 - PLOT.y1) * axes}
          stroke={bone(0.14)}
          strokeWidth={1}
        />

        <DrawnPath d={EXEC_PATH} span={M3.execCurve} color={COLORS.boneDim} width={4} />
        <DrawnPath d={CRIT_PATH} span={M3.critCurve} color={COLORS.bone} width={5} />

        {/* El único rojo del movimiento: el tope de CRITERIO. */}
        {peak > 0 ? (
          <>
            <circle cx={CRIT_PEAK.x} cy={CRIT_PEAK.y} r={34 * peak} fill={red(0.14 * peak)} />
            <circle cx={CRIT_PEAK.x} cy={CRIT_PEAK.y} r={9 * peak} fill={COLORS.red} />
          </>
        ) : null}
      </svg>

      {/* Etiquetas al extremo de cada curva, contra los bordes del alto. */}
      <div style={{ position: "absolute", left: SAFE_X, top: ZONE.top }}>
        <MaskReveal span={{ from: M3.critCurve.to - frames(0.47), to: M3.critCurve.to + frames(0.4) }}>
          <Kicker color={COLORS.bone}>{data.risingLabel}</Kicker>
        </MaskReveal>
      </div>
      <div style={{ position: "absolute", left: SAFE_X, top: 1552 }}>
        <MaskReveal span={{ from: M3.execCurve.to - frames(0.47), to: M3.execCurve.to + frames(0.4) }}>
          <Kicker color={COLORS.boneDim}>{data.fallingLabel}</Kicker>
        </MaskReveal>
      </div>

      {/* La regla. Al pie del frame: es una nota, no un titular. */}
      <div style={{ position: "absolute", left: SAFE_X, top: 1668, width: CONTENT_W }}>
        <MaskReveal span={M3.rule}>
          <div
            style={{
              fontFamily: FONT.body,
              fontWeight: 400,
              fontSize: TYPE.label,
              lineHeight: 1.7,
              letterSpacing: "0.04em",
              color: COLORS.boneDim,
              whiteSpace: "pre-line",
            }}
          >
            {data.rule}
          </div>
        </MaskReveal>
      </div>
    </AbsoluteFill>
  );
};

// ═══ MOVIMIENTO ══════════════════════════════════════════════════════════════

const TABLE_TIMING: FilterTableTiming = {
  head: M3.tableHead,
  rowsStart: M3.rowsStart,
  rowStagger: M3.rowStagger,
  rowDuration: M3.rowDuration,
  strikeDelay: M3.rowStrikeDelay,
  // La derecha entra medio beat después: la apreciación es respuesta a la
  // depreciación, no simultánea.
  pairDelay: frames(0.53),
};

export const M3Inversion: React.FC<{ data: CriterioProps["m3"] }> = ({ data }) => {
  const frame = useCurrentFrame();

  const chartAlive = 1 - ramp(frame, M3.chartOut);
  const tableAlive = 1 - ramp(frame, M3.tableOut);

  return (
    <AbsoluteFill>
      <Backdrop>
        {chartAlive > 0.001 ? <PriceChart data={data} alive={chartAlive} /> : null}

        {/* ── EL FILTRO ─────────────────────────────────────────────── */}
        <AbsoluteFill
          style={{
            opacity: tableAlive,
            alignItems: "flex-start",
            justifyContent: "center",
            padding: `0 ${SAFE_X}px`,
          }}
        >
          <FilterTable
            headDepreciated={data.headLeft}
            headAppreciated={data.headRight}
            depreciated={data.depreciated}
            appreciated={data.appreciated}
            timing={TABLE_TIMING}
          />
        </AbsoluteFill>

        {/* ── SELLO ─────────────────────────────────────────────────── */}
        <AbsoluteFill
          style={{ alignItems: "center", justifyContent: "center", padding: `0 ${SAFE_X}px` }}
        >
          <KineticText
            text={data.seal}
            span={M3.seal}
            variant="display"
            align="center"
            travel={34}
          />
        </AbsoluteFill>
      </Backdrop>
    </AbsoluteFill>
  );
};
