import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";

const { fontFamily: inter } = loadInter();

/** Escena de cierre: 8 s = 240 frames a 30 fps. Sin audio: la música y la voz
 *  en off se montan aparte. Todo el dibujo es CSS, sin imágenes externas. */
export const CIERRE_DURATION = 240;
export const CIERRE_FPS = 30;

// ── Sincronización con la voz en off ─────────────────────────────────────────
// Estos son los únicos valores a tocar cuando llegue el audio final: cada uno
// es el frame en que ENTRA el elemento (la animación dura ~24 frames desde ahí).

/** Frame de entrada del logotipo. */
export const LOGO_IN = 0;

/** Frame de entrada de cada cláusula, en orden. */
export const CLAUSE_IN = [45, 90, 130, 170] as const;

/** Frame de entrada del remate final. */
export const CLOSER_IN = 200;

/** Fade-out global: frame en que arranca. `null` lo desactiva y la escena queda
 *  estática hasta el final. */
export const FADE_OUT_IN: number | null = 230;

// ── Paleta ───────────────────────────────────────────────────────────────────
// Azul corporativo plano con tipografía clara: alto contraste, sin gradientes.
const BG     = "#0067B1";
const INK    = "#FFFFFF";  // logo y remate
const MUTED  = "#B9D5EA";  // las tres primeras cláusulas
const ACCENT = "#FFD000";  // la cuarta cláusula: el golpe final
const RULE   = "rgba(255,255,255,0.30)";  // filete bajo el logotipo

const CLAUSES = [
  "La inteligencia artificial interpreta.",
  "Las reglas validan.",
  "El auditor confirma.",
  "Y Oracle recibe información limpia.",
] as const;

/** Duración de cada entrada, en frames. */
const ENTER_FRAMES = 24;

/** Desplazamiento vertical de entrada (translateY de RISE a 0). */
const RISE = 12;

export const CierreOutro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  /** Progreso 0→1 de una entrada que arranca en `start`. Spring sobreamortiguado
   *  (damping alto): sube suave y asienta sin rebote ni oscilación. */
  const enter = (start: number) =>
    spring({
      frame:            Math.max(0, frame - start),
      fps,
      durationInFrames: ENTER_FRAMES,
      config:           { damping: 200, mass: 0.6 },
    });

  const logo = enter(LOGO_IN);

  // Remate: fade más marcado (curva propia, no spring) + leve scale.
  const closerFade = interpolate(
    frame,
    [CLOSER_IN, CLOSER_IN + 18],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
  );
  const closerScale = interpolate(enter(CLOSER_IN), [0, 1], [0.96, 1]);

  // Fade-out global sobre el contenido (el fondo se mantiene limpio).
  const fadeOut =
    FADE_OUT_IN === null
      ? 1
      : interpolate(frame, [FADE_OUT_IN, CIERRE_DURATION], [1, 0], {
          extrapolateLeft:  "clamp",
          extrapolateRight: "clamp",
        });

  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill
        style={{
          display:        "flex",
          flexDirection:  "column",
          alignItems:     "center",
          justifyContent: "center",
          fontFamily:     inter,
          opacity:        fadeOut,
          padding:        "0 120px",
        }}
      >
        {/* ── BEAT 1: logotipo ─────────────────────────────────────────────── */}
        <div
          style={{
            display:       "flex",
            flexDirection: "column",
            alignItems:    "center",
            opacity:       logo,
            transform:     `translateY(${((1 - logo) * RISE).toFixed(2)}px)`,
          }}
        >
          <div
            style={{
              fontSize:      104,
              fontWeight:    600,
              color:         INK,
              letterSpacing: -1.5,
              lineHeight:    1.05,
            }}
          >
            Bodega Viva
          </div>

          {/* Filete: separa el logotipo del tagline sin cargar la composición. */}
          <div
            style={{
              width:      132,
              height:     1,
              background: RULE,
              margin:     "26px 0 20px",
            }}
          />

          <div
            style={{
              fontSize:      24,
              fontWeight:    500,
              color:         MUTED,
              letterSpacing: 4.5,
              textTransform: "uppercase",
            }}
          >
            Toma física de inventarios
          </div>
        </div>

        {/* ── BEAT 2: las cuatro cláusulas ─────────────────────────────────── */}
        <div
          style={{
            display:       "flex",
            flexDirection: "column",
            alignItems:    "center",
            gap:           20,
            marginTop:     92,
          }}
        >
          {CLAUSES.map((text, i) => {
            const p    = enter(CLAUSE_IN[i]);
            const last = i === CLAUSES.length - 1;

            return (
              <div
                key={text}
                style={{
                  fontSize:      last ? 50 : 44,
                  fontWeight:    last ? 600 : 400,
                  color:         last ? ACCENT : MUTED,
                  letterSpacing: last ? -0.5 : -0.2,
                  lineHeight:    1.25,
                  textAlign:     "center",
                  opacity:       p,
                  transform:     `translateY(${((1 - p) * RISE).toFixed(2)}px)`,
                }}
              >
                {text}
              </div>
            );
          })}
        </div>

        {/* ── BEAT 3: remate ───────────────────────────────────────────────── */}
        <div
          style={{
            marginTop:     78,
            fontSize:      82,
            fontWeight:    700,
            color:         INK,
            letterSpacing: -1.8,
            lineHeight:    1.1,
            textAlign:     "center",
            opacity:       closerFade,
            transform:     `scale(${closerScale.toFixed(4)})`,
          }}
        >
          desde la primera vez.
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
