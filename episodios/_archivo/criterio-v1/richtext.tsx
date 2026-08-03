/**
 * Marcadores de énfasis en línea.
 *
 * Permiten que el copy viva entero en schema.ts sin partir cada frase en
 * fragmentos before/accent/after. Sintaxis:
 *   *palabra*   → rojo (palabra-activación · REGLA DEL ROJO)
 *   _palabra_   → énfasis por peso tipográfico, sin color
 *   ~palabra~   → apagada a boneDim, casi fantasma
 * `\n` corta línea.
 *
 * El parseo va ANTES del corte por renglón, así una marca puede cruzar un
 * salto de línea (`*ejecutar\nrápido*`). Al revés — cortar primero y parsear
 * después — cada mitad queda con un asterisco suelto y se imprime literal, lo
 * que obligaba a que toda frase enfatizada entrara en un solo renglón.
 */
import React from "react";
import { COLORS } from "./theme";

type Kind = "plain" | "red" | "weight" | "ghost";

export interface Token {
  kind: Kind;
  text: string;
}

const TOKEN_RE = /(\*[^*]+\*|_[^_]+_|~[^~]+~)/g;

const classify = (chunk: string): Token => {
  if (chunk.startsWith("*") && chunk.endsWith("*") && chunk.length > 2)
    return { kind: "red", text: chunk.slice(1, -1) };
  if (chunk.startsWith("_") && chunk.endsWith("_") && chunk.length > 2)
    return { kind: "weight", text: chunk.slice(1, -1) };
  if (chunk.startsWith("~") && chunk.endsWith("~") && chunk.length > 2)
    return { kind: "ghost", text: chunk.slice(1, -1) };
  return { kind: "plain", text: chunk };
};

/**
 * Parsea el texto completo y lo reparte en renglones conservando el énfasis.
 * Devuelve un array de renglones; cada renglón es un array de tokens.
 */
export const parseLines = (text: string): Token[][] => {
  const lines: Token[][] = [[]];
  for (const chunk of text.split(TOKEN_RE)) {
    if (chunk === "") continue;
    const { kind, text: body } = classify(chunk);
    const parts = body.split("\n");
    parts.forEach((part, i) => {
      if (i > 0) lines.push([]);
      if (part !== "") lines[lines.length - 1].push({ kind, text: part });
    });
  }
  return lines;
};

/** Texto plano de un renglón. Es lo que se mide para ajustar el cuerpo. */
export const lineText = (line: Token[]) => line.map((t) => t.text).join("");

const styleFor = (kind: Kind, baseWeight: number): React.CSSProperties => {
  switch (kind) {
    case "red":
      return { color: COLORS.red };
    case "weight":
      // Sin color: el énfasis es puramente tipográfico. Si la base ya está en
      // el tope de la familia (Archivo Black es 900 y no hay más arriba),
      // subir el peso no hace nada — el énfasis pasa a ser de escala.
      return baseWeight >= 800
        ? { fontSize: "1.09em", letterSpacing: "-0.02em" }
        : { fontWeight: 800, letterSpacing: "-0.01em" };
    case "ghost":
      return { color: COLORS.boneDim };
    default:
      return {};
  }
};

/** Un renglón ya parseado. */
export const RichTokens: React.FC<{
  line: Token[];
  baseWeight?: number;
  style?: React.CSSProperties;
}> = ({ line, baseWeight = 400, style }) => (
  <div style={style}>
    {line.map((t, i) => (
      <span key={i} style={styleFor(t.kind, baseWeight)}>
        {t.text}
      </span>
    ))}
  </div>
);

/** Texto con marcadores, en una o varias líneas. */
export const RichLine: React.FC<{
  text: string;
  baseWeight?: number;
  style?: React.CSSProperties;
  lineStyle?: React.CSSProperties;
}> = ({ text, baseWeight = 400, style, lineStyle }) => (
  <div style={style}>
    {parseLines(text).map((line, i) => (
      <RichTokens key={i} line={line} baseWeight={baseWeight} style={lineStyle} />
    ))}
  </div>
);

/** ¿La cadena tiene alguna palabra-activación en rojo? Útil para auditar. */
export const hasRed = (text: string) => /\*[^*]+\*/.test(text);
