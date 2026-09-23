/**
 * Quién está hablando: nombre y rol, abajo a un costado.
 *
 * "Lower third" es un nombre heredado de la tele, donde iba en el tercio
 * inferior. En vertical eso queda debajo de la interfaz de la app, así que acá
 * se apoya más arriba — justo por encima de SAFE_BOTTOM.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { LowerThirdOverlay } from "./types";
import { ACCENT, easeOut, envelope, FONT, SAFE_BOTTOM, TEXT_SHADOW } from "./theme";

const IN_SECONDS = 0.45;

export const LowerThird: React.FC<{ lower: LowerThirdOverlay }> = ({ lower }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const nombre = (lower.name || "").trim();
  if (!lower.on || !nombre) return null;

  const desde = Math.round(lower.start * fps);
  const dur = Math.max(1, Math.round(lower.dur * fps));
  const vis = envelope(frame, desde, dur, Math.round(0.3 * fps));
  if (vis <= 0) return null;

  const entrada = Math.min(1, Math.max(0, (frame - desde) / (IN_SECONDS * fps)));
  const e = easeOut(entrada);

  const izq = lower.side === "left";
  const nombreSize = width * 0.038;
  const rolSize = width * 0.024;

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        alignItems: izq ? "flex-start" : "flex-end",
        paddingBottom: height * (SAFE_BOTTOM + 0.02),
        paddingLeft: width * 0.055,
        paddingRight: width * 0.055,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          flexDirection: izq ? "row" : "row-reverse",
          // Entra deslizándose desde su propio lado, no desde el centro.
          transform: `translateX(${(1 - e) * width * 0.06 * (izq ? -1 : 1)}px)`,
          opacity: vis * e,
        }}
      >
        {/* El bloque de acento: es lo que hace que se lea como una placa y no
            como texto suelto encima del video. */}
        <div
          style={{
            width: Math.max(4, width * 0.008),
            background: ACCENT,
            borderRadius: 99,
          }}
        />
        <div
          style={{
            padding: `${height * 0.008}px ${width * 0.028}px`,
            background: "rgba(10,12,16,0.62)",
            backdropFilter: "blur(6px)",
            borderRadius: izq ? "0 10px 10px 0" : "10px 0 0 10px",
            textAlign: izq ? "left" : "right",
            fontFamily: FONT,
          }}
        >
          <div
            style={{
              fontWeight: 900,
              fontSize: nombreSize,
              lineHeight: 1.15,
              color: "#fff",
              letterSpacing: "-0.01em",
              textShadow: TEXT_SHADOW,
              whiteSpace: "nowrap",
            }}
          >
            {nombre}
          </div>
          {lower.role.trim() && (
            <div
              style={{
                fontWeight: 700,
                fontSize: rolSize,
                lineHeight: 1.3,
                marginTop: height * 0.002,
                color: "rgba(255,255,255,0.78)",
                whiteSpace: "nowrap",
              }}
            >
              {lower.role}
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
