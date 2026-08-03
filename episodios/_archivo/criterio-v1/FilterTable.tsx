/**
 * FilterTable — "el filtro" de M3.
 *
 * En 9:16 las dos columnas no van lado a lado: a 1080 px de ancho, dos
 * columnas de 500 parten las frases en tres renglones y se pierde la
 * oposición. Van apiladas — bloque SE DEPRECIÓ arriba, SE APRECIÓ abajo — y se
 * construyen intercaladas fila por fila, que es donde está el argumento: cada
 * cosa que se apreció es respuesta a la que se depreció.
 */
import React from "react";
import { random, useCurrentFrame } from "remotion";
import { COLORS, FONT, TYPE, bone } from "./theme";
import { Kicker, MaskReveal, ramp, type Span } from "./primitives";
import { frames } from "./timing";

export interface FilterTableTiming {
  head: Span;
  rowsStart: number;
  rowStagger: number;
  rowDuration: number;
  /** Cuánto tarda en tacharse una fila después de entrar. */
  strikeDelay: number;
  /** Cuánto después de la fila depreciada entra su par apreciada. */
  pairDelay: number;
}

/** Fila que se deprecia: entra, se apaga y se tacha, con un glitch corto. */
const DepreciatedRow: React.FC<{ text: string; delay: number; t: FilterTableTiming }> = ({
  text,
  delay,
  t,
}) => {
  const frame = useCurrentFrame();
  const enter: Span = { from: delay, to: delay + t.rowDuration };
  const strikeFrom = delay + t.strikeDelay;
  const strike = ramp(frame, { from: strikeFrom, to: strikeFrom + frames(0.53) });
  const fade = ramp(
    frame,
    { from: strikeFrom + frames(0.13), to: strikeFrom + frames(0.73) },
    [1, 0.34]
  );

  // ~0.27 s de jitter horizontal justo al tacharse. Determinista, y muestreado
  // por tiempo (no por frame) para que a 60 fps no se vuelva vibración fina.
  const g = frame - strikeFrom;
  const glitchSpan = frames(0.27);
  const glitch =
    g >= 0 && g < glitchSpan
      ? (random(`gl${delay}${Math.floor((g / glitchSpan) * 8)}`) - 0.5) * 9
      : 0;

  return (
    // inline-block: la caja mide lo que mide el texto, así el tachado no se
    // pasa de largo cuando la frase es más corta que la columna.
    <div
      style={{
        position: "relative",
        display: "inline-block",
        transform: `translateX(${glitch.toFixed(2)}px)`,
      }}
    >
      <MaskReveal span={enter} travel={16}>
        <div
          style={{
            fontFamily: FONT.body,
            fontWeight: 400,
            fontSize: TYPE.body,
            color: bone(0.45 * fade + 0.1),
            opacity: fade,
            // Una línea por fila: ROW_STEP asume alto fijo.
            whiteSpace: "nowrap",
          }}
        >
          {text}
        </div>
      </MaskReveal>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: "52%",
          height: 2,
          width: `${(strike * 100).toFixed(2)}%`,
          backgroundColor: bone(0.35),
        }}
      />
    </div>
  );
};

/** Fila que se aprecia: entra y se solidifica. Termina en bone pleno. */
const AppreciatedRow: React.FC<{ text: string; delay: number; t: FilterTableTiming }> = ({
  text,
  delay,
  t,
}) => {
  const frame = useCurrentFrame();
  const enter: Span = { from: delay, to: delay + t.rowDuration };
  const solid = ramp(frame, {
    from: delay + t.rowDuration,
    to: delay + t.rowDuration + frames(0.67),
  });

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <MaskReveal span={enter} travel={16}>
        <div
          style={{
            fontFamily: FONT.body,
            fontWeight: 400 + Math.round(solid * 300),
            fontSize: TYPE.body,
            color: bone(0.5 + solid * 0.5),
            whiteSpace: "nowrap",
          }}
        >
          {text}
        </div>
      </MaskReveal>
      {/* Se fija: una regla al pie, al ancho exacto de la frase. */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: "126%",
          height: 1,
          width: `${(solid * 100).toFixed(2)}%`,
          backgroundColor: bone(0.18),
        }}
      />
    </div>
  );
};

/** Paso entre filas. Generoso: en vertical hay alto de sobra y el aire entre
 *  argumentos es parte de la lectura. */
const ROW_STEP = 168;

export const FilterTable: React.FC<{
  headDepreciated: string;
  headAppreciated: string;
  depreciated: string[];
  appreciated: string[];
  timing: FilterTableTiming;
  /** Ancho útil. OBLIGATORIO que sea explícito: las filas son inline-block
   *  (para que el tachado mida lo que mide el texto) y sin un ancho fijado
   *  arriba, el shrink-to-fit las colapsa y las frases parten en tres
   *  renglones que se pisan entre sí. */
  width?: number;
}> = ({ headDepreciated, headAppreciated, depreciated, appreciated, timing, width = 912 }) => {
  // Si una lista es más corta manda la más larga: el hueco queda vacío en vez
  // de romper el layout.
  const rowCount = Math.max(depreciated.length, appreciated.length);
  const blockH = rowCount * ROW_STEP;

  const block = (
    head: string,
    headColor: string,
    headSpan: FilterTableTiming["head"],
    rows: string[],
    render: (text: string, delay: number) => React.ReactNode,
    delayOffset: number
  ) => (
    <div style={{ width }}>
      <MaskReveal span={headSpan}>
        <Kicker color={headColor}>{head}</Kicker>
      </MaskReveal>
      <div style={{ position: "relative", width, height: blockH, marginTop: 64 }}>
        {rows.map((text, i) => (
          <div key={i} style={{ position: "absolute", top: i * ROW_STEP, left: 0, width }}>
            {render(text, timing.rowsStart + i * timing.rowStagger + delayOffset)}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 156, width }}>
      {block(
        headDepreciated,
        COLORS.boneDim,
        timing.head,
        depreciated,
        (text, delay) => <DepreciatedRow text={text} delay={delay} t={timing} />,
        0
      )}
      {block(
        headAppreciated,
        COLORS.bone,
        { from: timing.head.from + frames(0.33), to: timing.head.to + frames(0.33) },
        appreciated,
        (text, delay) => <AppreciatedRow text={text} delay={delay} t={timing} />,
        timing.pairDelay
      )}
    </div>
  );
};
