/**
 * KineticText — el componente de texto del episodio.
 *
 * Junta las cuatro decisiones que se repiten en cada movimiento: qué fuente y
 * escala usar, CUÁNTO puede agrandarse para llenar el ancho, cómo entra
 * (máscara vertical o blur→focus, nunca un fade solo) y cómo se marcan las
 * palabras con énfasis. Todo el copy del video pasa por acá.
 *
 * AJUSTE AL ANCHO: por defecto mide cada renglón con `fitText` y usa el cuerpo
 * más grande que entra, con el tamaño de la variante como techo. Todos los
 * renglones comparten un único cuerpo — el del más largo — porque si cada uno
 * se ajustara solo, un bloque de tres líneas saldría con tres tamaños
 * distintos y dejaría de leerse como una unidad.
 */
import React from "react";
import { fitText } from "@remotion/layout-utils";
import { COLORS, CONTENT_W, FONT, TRACKING, TYPE } from "./theme";
import { frames } from "./timing";
import { BlurFocus, MaskReveal, type Span } from "./primitives";
import { RichTokens, lineText, parseLines } from "./richtext";

export type TextVariant = "hero" | "display" | "body" | "kicker";

const VARIANT: Record<
  TextVariant,
  { family: string; size: number; weight: number; lineHeight: number; tracking: string; upper: boolean }
> = {
  hero: {
    family: FONT.display,
    size: TYPE.hero,
    weight: 900,
    lineHeight: 1.0,
    tracking: TRACKING.display,
    upper: false,
  },
  display: {
    family: FONT.display,
    size: TYPE.h1,
    weight: 900,
    lineHeight: 1.04,
    tracking: TRACKING.display,
    upper: false,
  },
  body: {
    family: FONT.body,
    size: TYPE.body,
    weight: 400,
    lineHeight: 1.36,
    tracking: TRACKING.body,
    upper: false,
  },
  kicker: {
    family: FONT.body,
    size: TYPE.label,
    weight: 600,
    lineHeight: 1.3,
    tracking: TRACKING.label,
    upper: true,
  },
};

/**
 * El cuerpo más grande con el que TODOS los renglones entran en `maxWidth`.
 * El +9% cubre el énfasis por escala de `_palabra_`, que agranda esa palabra
 * después de medir.
 */
const EMPHASIS_HEADROOM = 1.09;

export const KineticText: React.FC<{
  text: string;
  span: Span;
  out?: Span;
  variant?: TextVariant;
  /** Techo del cuerpo. Por defecto, el de la variante. */
  size?: number;
  /** Ancho contra el que se ajusta. Por defecto, el ancho útil del frame. */
  maxWidth?: number;
  /** false = usa `size` tal cual, sin medir. */
  fit?: boolean;
  color?: string;
  align?: "left" | "center" | "right";
  /** Máscara vertical por defecto; blur→focus para lo que "aparece de la nada". */
  entry?: "mask" | "blur";
  direction?: "up" | "down";
  travel?: number;
  /** Retardo entre un renglón y el siguiente, en frames. 0 = todos juntos.
   *  Por defecto ~0.17 s, derivado del fps. */
  stagger?: number;
  style?: React.CSSProperties;
}> = ({
  text,
  span,
  out,
  variant = "display",
  size,
  maxWidth = CONTENT_W,
  fit = true,
  color = COLORS.bone,
  align = "left",
  entry = "mask",
  direction = "up",
  travel = 28,
  stagger = frames(0.17),
  style,
}) => {
  const v = VARIANT[variant];
  const lines = parseLines(text);
  const ceiling = size ?? v.size;

  const hasEmphasis = /_[^_]+_/.test(text);
  const budget = hasEmphasis ? maxWidth / EMPHASIS_HEADROOM : maxWidth;

  const fontSize = fit
    ? Math.min(
        ceiling,
        ...lines.map(
          (line) =>
            fitText({
              text: lineText(line),
              withinWidth: budget,
              fontFamily: v.family,
              fontWeight: v.weight,
              letterSpacing: v.tracking,
              textTransform: v.upper ? "uppercase" : "none",
            }).fontSize
        )
      )
    : ceiling;

  const typeStyle: React.CSSProperties = {
    fontFamily: v.family,
    fontWeight: v.weight,
    fontSize,
    lineHeight: v.lineHeight,
    letterSpacing: v.tracking,
    textTransform: v.upper ? "uppercase" : "none",
    color,
    textAlign: align,
    whiteSpace: "nowrap",
  };

  if (entry === "blur") {
    return (
      <BlurFocus span={span} out={out} style={style}>
        <div style={typeStyle}>
          {lines.map((line, i) => (
            <RichTokens key={i} line={line} baseWeight={v.weight} />
          ))}
        </div>
      </BlurFocus>
    );
  }

  // Una máscara por renglón. Sin esto, un texto de tres líneas se descubre
  // como un bloque único de abajo hacia arriba y el último renglón aparece
  // antes que el primero, que se lee al revés.
  return (
    <div style={style}>
      {lines.map((line, i) => (
        <MaskReveal
          key={i}
          span={{ from: span.from + i * stagger, to: span.to + i * stagger }}
          out={out}
          direction={direction}
          travel={travel}
        >
          <RichTokens line={line} baseWeight={v.weight} style={typeStyle} />
        </MaskReveal>
      ))}
    </div>
  );
};
