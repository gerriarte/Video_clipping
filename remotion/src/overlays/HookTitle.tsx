/**
 * El gancho: la frase que sostiene al que pasa scrolleando.
 *
 * Va arriba por defecto, no abajo: abajo está la interfaz de la app (ver
 * SAFE_BOTTOM). Y no espera a que termine de entrar para ser legible — la
 * animación dura menos de medio segundo porque el primer segundo del clip es
 * justamente el que decide si alguien se queda.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import type { HookOverlay } from "./types";
import { ACCENT, easeOut, envelope, FONT, SAFE_BOTTOM, SAFE_TOP, TEXT_SHADOW } from "./theme";

/** Cuánto dura la entrada, en segundos. Corta a propósito. */
const IN_SECONDS = 0.35;

export const HookTitle: React.FC<{ hook: HookOverlay; fallbackText: string }> = ({
  hook,
  fallbackText,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const texto = (hook.text || fallbackText || "").trim();
  if (!hook.on || !texto) return null;

  const desde = Math.round(hook.start * fps);
  const dur = Math.max(1, Math.round(hook.dur * fps));
  const vis = envelope(frame, desde, dur, Math.round(0.25 * fps));
  if (vis <= 0) return null;

  // Progreso de la entrada, independiente del fade de salida.
  const entrada = Math.min(1, Math.max(0, (frame - desde) / (IN_SECONDS * fps)));
  const e = easeOut(entrada);

  // El cuerpo se mide contra el ANCHO: así el mismo texto pesa parecido en
  // 1080x1920 y en 1920x1080, en vez de achicarse en el formato horizontal.
  const size = width * 0.072;

  let transform = "none";
  let mostrado = texto;
  if (hook.style === "pop") {
    transform = `scale(${0.86 + 0.14 * e})`;
  } else if (hook.style === "slide") {
    transform = `translateY(${(1 - e) * height * 0.035}px)`;
  } else if (hook.style === "type") {
    // Se escribe sola. El cursor se va cuando terminó.
    const n = Math.ceil(texto.length * entrada);
    mostrado = texto.slice(0, n) + (entrada < 1 ? "▌" : "");
  }

  const justify =
    hook.position === "top" ? "flex-start"
    : hook.position === "bottom" ? "flex-end"
    : "center";

  // Un velo detrás del texto. La sombra sola alcanza sobre una imagen oscura,
  // pero este material tiene un mural blanco de fondo: ahí el texto blanco se
  // pierde. El degradado arranca del borde y se va a nada, así no se nota como
  // una caja y la cara nunca queda tapada por un bloque.
  const velo =
    hook.position === "top"
      ? "linear-gradient(to bottom, rgba(6,8,12,.72) 0%, rgba(6,8,12,.45) 45%, rgba(6,8,12,0) 100%)"
      : hook.position === "bottom"
      ? "linear-gradient(to top, rgba(6,8,12,.72) 0%, rgba(6,8,12,.45) 45%, rgba(6,8,12,0) 100%)"
      : "radial-gradient(ellipse at center, rgba(6,8,12,.62) 0%, rgba(6,8,12,0) 72%)";

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: justify,
        alignItems: "center",
        paddingTop: height * (SAFE_TOP + 0.03),
        paddingBottom: height * (SAFE_BOTTOM + 0.03),
        paddingLeft: width * 0.06,
        paddingRight: width * 0.06,
        pointerEvents: "none",
      }}
    >
      <AbsoluteFill
        style={{
          background: velo,
          opacity: vis,
          // Solo la franja donde vive el texto, no la pantalla entera.
          height: hook.position === "center" ? "100%" : "38%",
          top: hook.position === "bottom" ? "62%" : 0,
        }}
      />
      <div
        style={{
          opacity: hook.style === "type" ? vis : vis * (0.3 + 0.7 * e),
          transform,
          textAlign: "center",
          fontFamily: FONT,
          fontWeight: 900,
          fontSize: size,
          lineHeight: 1.12,
          letterSpacing: "-0.02em",
          color: "#fff",
          textShadow: TEXT_SHADOW,
          textWrap: "balance",
        }}
      >
        {mostrado}
        {/* La barra de acento crece con la entrada: da el golpe sin tapar nada. */}
        <div
          style={{
            height: Math.max(3, height * 0.005),
            width: `${Math.round(e * 100)}%`,
            margin: `${size * 0.32}px auto 0`,
            background: ACCENT,
            borderRadius: 99,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
