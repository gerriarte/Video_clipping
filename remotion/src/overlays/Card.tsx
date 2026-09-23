/**
 * La placa de intro y la de cierre.
 *
 * Yo había dejado esto afuera con un argumento: una placa a pantalla completa
 * en un clip de 60 s se come justo los segundos donde se decide si alguien se
 * queda. El argumento sigue siendo cierto — así que la placa **no tapa el
 * video**: lo oscurece lo que se le diga (`dim`) y el movimiento sigue abajo.
 * Con `dim` en 1 se puede hacer la placa opaca de toda la vida, pero el default
 * deja ver.
 *
 * La de intro cuenta desde el frame 0; la de cierre se ancla al FINAL del clip,
 * que es lo que uno quiere decir cuando dice "los últimos 3 segundos".
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { CardOverlay } from "./types";
import { ACCENT, easeOut, envelope, FONT, SAFE_BOTTOM, SAFE_TOP, TEXT_SHADOW } from "./theme";

const IN_SECONDS = 0.4;

export const Card: React.FC<{ card: CardOverlay; where: "intro" | "outro" }> = ({
  card,
  where,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();

  const titulo = (card.title || "").trim();
  if (!card.on || !titulo) return null;

  const dur = Math.max(1, Math.round(card.dur * fps));
  // La de cierre se ancla al final: si el clip dura menos de lo que pide la
  // placa, arranca en 0 en vez de en un frame negativo.
  const desde = where === "intro" ? 0 : Math.max(0, durationInFrames - dur);
  const vis = envelope(frame, desde, dur, Math.round(0.3 * fps));
  if (vis <= 0) return null;

  const entrada = Math.min(1, Math.max(0, (frame - desde) / (IN_SECONDS * fps)));
  const e = easeOut(entrada);
  const dim = Math.min(1, Math.max(0, card.dim));

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ background: "#05070b", opacity: dim * vis }} />
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          paddingTop: height * SAFE_TOP,
          paddingBottom: height * SAFE_BOTTOM,
          paddingLeft: width * 0.09,
          paddingRight: width * 0.09,
          textAlign: "center",
          fontFamily: FONT,
          opacity: vis,
          transform: `scale(${0.94 + 0.06 * e})`,
        }}
      >
        <div
          style={{
            fontWeight: 900,
            fontSize: width * 0.082,
            lineHeight: 1.1,
            letterSpacing: "-0.025em",
            color: "#fff",
            textShadow: TEXT_SHADOW,
            textWrap: "balance",
          }}
        >
          {titulo}
        </div>
        <div
          style={{
            height: Math.max(3, height * 0.005),
            width: `${Math.round(e * 42)}%`,
            margin: `${height * 0.018}px 0`,
            background: ACCENT,
            borderRadius: 99,
          }}
        />
        {card.subtitle.trim() && (
          <div
            style={{
              fontWeight: 700,
              fontSize: width * 0.036,
              lineHeight: 1.35,
              color: "rgba(255,255,255,0.86)",
              textShadow: TEXT_SHADOW,
              textWrap: "balance",
            }}
          >
            {card.subtitle}
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
