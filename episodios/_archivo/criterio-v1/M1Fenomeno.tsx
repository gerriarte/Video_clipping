/**
 * M1 — FENÓMENO   ·   frames 0–1350   ·   0:00–0:45
 *
 * Beat: dos hechos que juntos no cierran.
 *
 * FRAME GUIDES (locales a la Sequence)
 *   0        bg + retícula
 *   15–48    barrido diagonal: se abre el split
 *   42–78    mitad A — "10 AÑOS DE EXPERIENCIA" entra por máscara
 *   90–114   "filtra +45" entra por blur→focus
 *   150–…    mitad B — el bloque de output IA se autocompleta solo
 *   990–1035 las dos mitades se apagan un punto
 *   1020–…   la pregunta central
 *   1020–1350 push-in lento hasta el corte
 *
 * En 9:16 el corte a 45° divide arriba/abajo, no izquierda/derecha. La mitad A
 * ocupa el grueso de la zona superior (arriba-izquierda) y la B el de la
 * inferior (abajo-derecha): nunca se tocan ni hay línea que las conecte. La
 * pregunta entra justo sobre la costura, cruzando las dos.
 *
 * Sin rojo. Sin la palabra "criterio" todavía.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS, CONTENT_W, EASE, FONT, TRACKING, TYPE, ZONE, bone } from "./theme";
import {
  Backdrop,
  BlurFocus,
  DiagonalWipe,
  PushIn,
  SPLIT_BOTTOM,
  SPLIT_Y_LEFT,
  Typeline,
  diagonalClipTop,
  ramp,
} from "./primitives";
import { KineticText } from "./KineticText";
import { M1, SAFE_X, frames } from "./timing";
import type { CriterioProps } from "./schema";

export const M1Fenomeno: React.FC<{ data: CriterioProps["m1"] }> = ({ data }) => {
  const frame = useCurrentFrame();

  // La zona de arriba se descubre con el mismo filo a 45° que usa el barrido:
  // el clip viaja desde fuera del frame hasta su posición de reposo.
  const openA = ramp(frame, M1.splitWipe, [-260, SPLIT_Y_LEFT], EASE.inOut);
  // La zona de abajo entra un toque después. No hay línea que las una.
  const openB = ramp(
    frame,
    { from: M1.splitWipe.from + frames(0.33), to: M1.splitWipe.to + frames(0.47) },
    [0, 1],
    EASE.inOut
  );

  // Cuando llega la pregunta, las dos mitades ceden protagonismo sin irse.
  // 0.16 y no más: tienen que seguir ahí (el beat es que conviven), pero el
  // centro necesita quedar vacío o la pregunta pelea con el bloque de la IA.
  const recede = ramp(frame, M1.halvesRecede, [1, 0.16]);

  return (
    <AbsoluteFill>
      <Backdrop>
        <PushIn span={M1.pushIn} to={1.045}>
          {/* ── ZONA A · el hecho humano ──────────────────────────────── */}
          <AbsoluteFill style={{ clipPath: diagonalClipTop(openA), opacity: recede }}>
            <div style={{ position: "absolute", left: SAFE_X, top: ZONE.top, width: CONTENT_W }}>
              <KineticText
                text={data.headline}
                span={M1.headline}
                variant="display"
                travel={34}
              />

              <BlurFocus span={M1.kicker} blur={16} style={{ marginTop: 40 }}>
                <div
                  style={{
                    fontFamily: FONT.body,
                    fontWeight: 500,
                    fontSize: TYPE.label,
                    letterSpacing: TRACKING.label,
                    textTransform: "uppercase",
                    color: COLORS.boneDim,
                  }}
                >
                  {data.kicker}
                </div>
              </BlurFocus>
            </div>
          </AbsoluteFill>

          {/* ── ZONA B · el output de la máquina ──────────────────────── */}
          {/* Mono a propósito: la zona A es tipografía con peso humano, la B es
              salida de terminal. El contraste hace el argumento. */}
          <AbsoluteFill style={{ clipPath: SPLIT_BOTTOM, opacity: openB * recede }}>
            {/* El bloque cuelga del pie: la zona de abajo del split tiene su
                masa hacia la derecha, y así ocupa el tercio inferior en vez de
                flotar contra el centro. */}
            <div style={{ position: "absolute", left: 232, bottom: 168, width: 800 }}>
              {data.aiLines.map((line, i) => {
                const from = M1.linesStart + i * M1.lineStagger;
                return (
                  <Typeline
                    key={i}
                    text={line}
                    span={{ from, to: from + M1.lineDuration }}
                    style={{
                      fontFamily: FONT.mono,
                      fontSize: 32,
                      lineHeight: 1.95,
                      color: bone(0.38),
                      whiteSpace: "pre",
                    }}
                  />
                );
              })}
            </div>
          </AbsoluteFill>

          {/* ── LA PREGUNTA · sobre la costura de las dos zonas ────────── */}
          <AbsoluteFill
            style={{
              alignItems: "center",
              justifyContent: "center",
              padding: `0 ${SAFE_X}px`,
            }}
          >
            <KineticText
              text={data.question}
              span={M1.question}
              variant="display"
              align="center"
              travel={40}
            />
          </AbsoluteFill>
        </PushIn>
      </Backdrop>

      {/* El barrido que abre el movimiento, por encima de todo. */}
      <DiagonalWipe span={M1.splitWipe} color={COLORS.bone} band={200} />
    </AbsoluteFill>
  );
};
