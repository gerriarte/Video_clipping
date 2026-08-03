/**
 * DataStat — el tratamiento de los números duros.
 *
 * Los números no entran como el texto: hard cut (aparecen enteros, sin
 * máscara ni blur), escala grande, monoespaciado y cifras tabulares para que
 * el ancho no baile mientras cuentan. El conteo es lo que los vuelve
 * incómodos; el número quieto no dice nada.
 */
import React from "react";
import { useCurrentFrame } from "remotion";
import { COLORS, EASE, FONT, TYPE, bone } from "./theme";
import { Kicker, MaskReveal, ramp, type Span } from "./primitives";
import { frames } from "./timing";

export const DataStat: React.FC<{
  value: number;
  unit: string;
  label: string;
  /** Nota de fuente al pie. Vacío = no se muestra. */
  source?: string;
  /** Rango en el que el número cuenta desde 0 hasta `value`. */
  count: Span;
  /** Cuándo entra la etiqueta de abajo. */
  labelSpan: Span;
  color?: string;
  size?: number;
}> = ({
  value,
  unit,
  label,
  source,
  count,
  labelSpan,
  color = COLORS.red,
  size = TYPE.data,
}) => {
  const frame = useCurrentFrame();
  const n = Math.round(ramp(frame, count, [0, value], EASE.out));

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 20 }}>
        <div
          style={{
            fontFamily: FONT.mono,
            fontWeight: 600,
            fontSize: size,
            lineHeight: 1,
            letterSpacing: "-0.04em",
            color,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {n}
        </div>
        <div
          style={{
            fontFamily: FONT.body,
            fontWeight: 500,
            fontSize: Math.round(size * 0.22),
            color: bone(0.7),
          }}
        >
          {unit}
        </div>
      </div>

      <MaskReveal span={labelSpan} style={{ marginTop: 28 }}>
        <Kicker color={COLORS.boneDim} style={{ textAlign: "center" }}>
          {label}
        </Kicker>
      </MaskReveal>

      {source ? (
        <MaskReveal
          span={{ from: labelSpan.to + frames(0.2), to: labelSpan.to + frames(0.87) }}
          style={{ marginTop: 16 }}
        >
          <div
            style={{
              fontFamily: FONT.body,
              fontSize: 17,
              color: bone(0.28),
              textAlign: "center",
            }}
          >
            {source}
          </div>
        </MaskReveal>
      ) : null}
    </div>
  );
};
