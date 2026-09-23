/**
 * Lo que el formato se queda y lo que tira, dibujado sobre la foto del tramo.
 *
 * Hoy los botones de formato son abstractos: "split" no te dice nada hasta que
 * renderizás. Acá el recorte se ve encima de la foto real, así que la elección
 * deja de ser a ciegas.
 */
import React from "react";
import type { FormatDef } from "./types";
import type { Tokens } from "./theme";

export interface Box {
  /** Todo en fracción del ancho/alto de la foto (0–1). */
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Los rectángulos que el formato conserva de la imagen fuente.
 *
 * Un formato más angosto que la fuente recorta a los costados y conserva todo
 * el alto; uno más ancho recorta arriba y abajo. El "split" son DOS recortes
 * (uno por host) que después se apilan: en la fuente pueden solaparse, y está
 * bien — cada mitad muestra a una persona distinta.
 */
export function cropBoxes(
  fmt: FormatDef | undefined,
  sourceAspect: number,
  centersX: number[],
): Box[] {
  if (!fmt || !fmt.crop || !isFinite(sourceAspect) || sourceAspect <= 0) {
    return []; // no recorta nada: se ve el plano entero
  }

  const centers = centersX.filter((c) => isFinite(c));
  const box = (aspect: number, cx: number): Box => {
    const w = Math.min(1, aspect / sourceAspect);
    const h = Math.min(1, sourceAspect / aspect);
    const x = Math.min(Math.max(cx - w / 2, 0), 1 - w);
    const y = Math.min(Math.max(0.5 - h / 2, 0), 1 - h);
    return { x, y, w, h };
  };

  if (fmt.key === "split") {
    // Dos mitades apiladas: cada una es la mitad del alto del lienzo final.
    const half = fmt.aspect * 2;
    if (centers.length >= 2) {
      const sorted = [...centers].sort((a, b) => a - b);
      return [box(half, sorted[0]), box(half, sorted[sorted.length - 1])];
    }
    return [box(half, 0.33), box(half, 0.67)];
  }

  const cx = centers.length
    ? centers.reduce((a, b) => a + b, 0) / centers.length
    : 0.5;
  return [box(fmt.aspect, cx)];
}

interface OverlayProps {
  id: number;
  fmt: FormatDef | undefined;
  /** Posicion horizontal de cada cara detectada (0-1); vacio = centrado. */
  centersX: number[];
  sourceAspect: number;
  t: Tokens;
}

export const CropOverlay: React.FC<OverlayProps> = ({ id, fmt, centersX, sourceAspect, t }) => {
  const boxes = cropBoxes(fmt, sourceAspect, centersX || []);
  if (!boxes.length) {
    return (
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <div style={chipStyle(t)}>plano completo</div>
      </div>
    );
  }
  const maskId = `crop-mask-${id}`;
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    >
      <defs>
        <mask id={maskId}>
          <rect x="0" y="0" width="100" height="100" fill="white" />
          {boxes.map((b, i) => (
            <rect key={i} x={b.x * 100} y={b.y * 100} width={b.w * 100} height={b.h * 100} fill="black" />
          ))}
        </mask>
      </defs>
      {/* lo que se descarta, apagado */}
      <rect x="0" y="0" width="100" height="100" fill="rgba(6,8,12,0.62)" mask={`url(#${maskId})`} />
      {boxes.map((b, i) => (
        <rect
          key={i}
          x={b.x * 100}
          y={b.y * 100}
          width={b.w * 100}
          height={b.h * 100}
          fill="none"
          stroke={t.primary}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  );
};

const chipStyle = (t: Tokens): React.CSSProperties => ({
  position: "absolute",
  left: 8,
  bottom: 8,
  padding: "2px 7px",
  borderRadius: 999,
  fontSize: 10,
  letterSpacing: 0.2,
  background: "rgba(6,8,12,0.66)",
  color: "rgba(255,255,255,0.82)",
  border: "1px solid rgba(255,255,255,0.16)",
});

/**
 * El icono del formato: un rectángulo con la proporción real, dibujado.
 *
 * Reemplaza a los emojis (📱 ⬛ 🖥 ⧉) que se veían distinto en cada máquina y
 * rompían la altura de la fila de botones.
 */
export const FormatGlyph: React.FC<{ fmt: FormatDef; color: string }> = ({ fmt, color }) => {
  const H = 13;
  const w = Math.max(5, Math.min(22, Math.round(H * fmt.aspect)));
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width: w,
        height: H,
        border: `1.5px solid ${color}`,
        borderRadius: 2,
        position: "relative",
        flex: "0 0 auto",
      }}
    >
      {fmt.key === "split" && (
        <span
          style={{
            position: "absolute",
            left: -1.5,
            right: -1.5,
            top: "50%",
            height: 1.5,
            background: color,
          }}
        />
      )}
      {fmt.key === "9:16-full" && (
        <>
          <span style={{ position: "absolute", left: -1.5, right: -1.5, top: 2, height: 1.5, background: color, opacity: 0.55 }} />
          <span style={{ position: "absolute", left: -1.5, right: -1.5, bottom: 2, height: 1.5, background: color, opacity: 0.55 }} />
        </>
      )}
    </span>
  );
};
