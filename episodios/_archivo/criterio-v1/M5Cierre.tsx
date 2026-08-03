/**
 * M5 — TRABA Y SALIDA   ·   frames 6750–9000   ·   3:45–5:00
 *
 * Beat: identidad como traba + remate mecánico + pregunta al espectador.
 *
 * FRAME GUIDES (locales a la Sequence)
 *   30–78      cara A — cómo se ve el que tiene criterio
 *   126–174    cara B — el prejuicio, enfrentada a la anterior
 *   222–258    la llave USD 20/mes aparece entre las dos
 *   258–486    la llave titila. Nadie la agarra: queda suspendida
 *   486–522    la traba se va
 *   534–588    las dos mitades entran desalineadas y separadas
 *   690        ENCAJE — spring seco, las mitades se deslizan y cierran
 *   696–732    destello rojo en el punto de encaje, y se apaga
 *   726–768    "por primera vez, en la misma persona"
 *   996–1056   cierre conceptual full-screen
 *   1380–…     tres preguntas al espectador, una cada 150 frames
 *   1920–1980  remate — activación final en rojo
 *   2166–2208  wordmark
 *   2220–2250  frame final estático (~1 s). Nada se mueve acá
 *
 * ROJO: la llave (tenue), el destello del encaje (un pico corto) y la palabra
 * "ARMADO" del remate. Nada más.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS, CONTENT_W, FONT, SPRING, TRACKING, TYPE, ZONE, bone, red } from "./theme";
import { Backdrop, MaskReveal, PushIn, ramp, useDamped } from "./primitives";
import { KineticText } from "./KineticText";
import { M5, SAFE_X, frames } from "./timing";
import type { CriterioProps } from "./schema";

// ═══ LA TRABA ════════════════════════════════════════════════════════════════

/**
 * La llave. Dibujo mínimo: un anillo y un paletón. Titila con una onda
 * cuadrada (no un seno) — el parpadeo tiene que leerse como "disponible,
 * sin tomar", no como una respiración.
 */
const Key: React.FC<{ label: string; alive: number }> = ({ label, alive }) => {
  const frame = useCurrentFrame();
  const appear = ramp(frame, M5.keyIn);

  // Onda cuadrada: encendida la primera mitad del período, apagada la segunda.
  // El piso es 0.55 y no 0: apagada del todo la llave desaparece, y el punto
  // es que está ahí todo el tiempo y nadie la agarra.
  const phase = (frame - M5.keyIn.to) % M5.keyBlinkPeriod;
  const lit = frame >= M5.keyIn.to && phase >= 0 && phase < M5.keyBlinkPeriod * 0.55;
  const glow = lit ? 1 : 0.55;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 22,
        opacity: appear * alive,
      }}
    >
      <svg width={348} height={143} viewBox="0 0 190 78">
        {/* Anillo */}
        <circle
          cx={30}
          cy={39}
          r={20}
          fill="none"
          stroke={red(0.78 * glow)}
          strokeWidth={5}
          strokeDasharray={126}
          strokeDashoffset={126 * (1 - appear)}
        />
        {/* Caña */}
        <line
          x1={50}
          y1={39}
          x2={50 + 118 * appear}
          y2={39}
          stroke={red(0.78 * glow)}
          strokeWidth={5}
        />
        {/* Dientes */}
        <line x1={140} y1={39} x2={140} y2={39 + 20 * appear} stroke={red(0.78 * glow)} strokeWidth={5} />
        <line x1={164} y1={39} x2={164} y2={39 + 13 * appear} stroke={red(0.78 * glow)} strokeWidth={5} />
      </svg>
      <div
        style={{
          fontFamily: FONT.mono,
          fontSize: 42,
          fontWeight: 500,
          letterSpacing: "0.04em",
          color: red(0.85 * glow),
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {label}
      </div>
    </div>
  );
};

// ═══ EL ENSAMBLE ═════════════════════════════════════════════════════════════

/**
 * Dos mitades desalineadas que encajan. El desplazamiento inicial es grande y
 * asimétrico (arriba-izquierda y abajo-derecha); el spring seco las lleva a
 * cero sin rebote — tienen que cerrar como una pieza mecánica, no aterrizar.
 */
const Assemble: React.FC<{ top: string; bottom: string; alive: number }> = ({
  top,
  bottom,
  alive,
}) => {
  const frame = useCurrentFrame();
  const enter = ramp(frame, M5.halvesIn);
  const snap = useDamped(M5.snapAt, SPRING.hit);

  // Offsets de reposo → 0. `enter` los trae al frame; `snap` los cierra.
  const dxTop = (1 - snap) * -232 * enter;
  const dxBottom = (1 - snap) * 232 * enter;
  const gap = (1 - snap) * 88;

  const peak = M5.flash.from + frames(0.13);
  const flash =
    ramp(frame, { from: M5.flash.from, to: peak }) *
    (1 - ramp(frame, { from: peak, to: M5.flash.to }));

  return (
    <div style={{ position: "relative", opacity: enter * alive }}>
      <div
        style={{
          fontFamily: FONT.display,
          fontSize: TYPE.hero,
          letterSpacing: TRACKING.display,
          lineHeight: 1.0,
          color: COLORS.bone,
          textAlign: "center",
          transform: `translate(${dxTop.toFixed(1)}px, ${(-gap).toFixed(1)}px)`,
        }}
      >
        {top}
      </div>
      <div
        style={{
          fontFamily: FONT.display,
          fontSize: TYPE.hero,
          letterSpacing: TRACKING.display,
          lineHeight: 1.0,
          color: COLORS.bone,
          textAlign: "center",
          transform: `translate(${dxBottom.toFixed(1)}px, ${gap.toFixed(1)}px)`,
        }}
      >
        {bottom}
      </div>

      {/* Destello en el punto de encaje: la costura entre las dos mitades. */}
      {flash > 0.001 ? (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            width: 640,
            height: 6,
            marginLeft: -320,
            marginTop: -3,
            background: `linear-gradient(90deg, transparent, ${COLORS.red}, transparent)`,
            opacity: flash,
          }}
        />
      ) : null}
    </div>
  );
};

// ═══ MOVIMIENTO ══════════════════════════════════════════════════════════════

export const M5Cierre: React.FC<{ data: CriterioProps["m5"] }> = ({ data }) => {
  const frame = useCurrentFrame();

  const trabaAlive = 1 - ramp(frame, M5.trabaOut);
  const assembleAlive = 1 - ramp(frame, M5.assembleOut);
  const punchAlive = 1 - ramp(frame, M5.punchOut);

  // A partir de acá no se mueve nada: el frame final es estático.
  const frozen = frame >= M5.staticFrom;

  return (
    <AbsoluteFill>
      <Backdrop>
        {/* ── LA TRABA · dos caras enfrentadas ──────────────────────── */}
        {trabaAlive > 0.001 ? (
          <AbsoluteFill style={{ opacity: trabaAlive }}>
            {/* Las dos caras cuelgan de anclas opuestas y la llave queda justo
                en el medio: el hueco entre ellas ES la traba. Centrarlas todas
                juntas desperdiciaba los dos tercios exteriores del frame. */}
            <div
              style={{
                position: "absolute",
                top: ZONE.high,
                left: SAFE_X,
                width: CONTENT_W,
                transform: "translateY(-50%)",
              }}
            >
              <KineticText
                text={data.faceA}
                span={M5.faceA}
                variant="body"
                color={COLORS.bone}
                align="center"
              />
            </div>

            <div
              style={{
                position: "absolute",
                top: ZONE.center,
                left: 0,
                width: "100%",
                display: "flex",
                justifyContent: "center",
                transform: "translateY(-50%)",
              }}
            >
              <Key label={data.keyLabel} alive={trabaAlive} />
            </div>

            <div
              style={{
                position: "absolute",
                top: ZONE.low,
                left: SAFE_X,
                width: CONTENT_W,
                transform: "translateY(-50%)",
              }}
            >
              <KineticText
                text={data.faceB}
                span={M5.faceB}
                variant="body"
                color={COLORS.boneDim}
                align="center"
                direction="down"
              />
            </div>
          </AbsoluteFill>
        ) : null}

        {/* ── LA SALIDA · el ensamble ───────────────────────────────── */}
        {frame >= M5.halvesIn.from && assembleAlive > 0.001 ? (
          <AbsoluteFill
            style={{ alignItems: "center", justifyContent: "center", padding: `0 ${SAFE_X}px` }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <Assemble
                top={data.assembleTop}
                bottom={data.assembleBottom}
                alive={assembleAlive}
              />
              <KineticText
                text={data.assembled}
                span={M5.assembled}
                out={M5.assembleOut}
                variant="body"
                color={COLORS.boneDim}
                align="center"
                style={{ marginTop: 128 }}
              />
            </div>
          </AbsoluteFill>
        ) : null}

        {/* ── CIERRE CONCEPTUAL ─────────────────────────────────────── */}
        <AbsoluteFill
          style={{ alignItems: "center", justifyContent: "center", padding: `0 ${SAFE_X}px` }}
        >
          {/* El margen para el énfasis por escala de "desarmados" ya lo
              descuenta KineticText al medir; no hace falta bajarle el cuerpo. */}
          <KineticText
            text={data.concept}
            span={M5.concept}
            out={M5.conceptOut}
            variant="display"
            color={COLORS.bone}
            align="center"
            travel={38}
          />
        </AbsoluteFill>

        {/* ── CIERRE INTERACTIVO · tres preguntas, con aire ─────────── */}
        {/* Se ACUMULAN, no se reemplazan: las dos preguntas son paralelas
            ("producís/criterio" contra "sabés/ejecución") y el paralelo es el
            argumento — hay que poder leerlas juntas. Van en columna y cada una
            reserva su lugar desde el frame 0 (la máscara recorta pero el bloque
            ya ocupa su alto), así el conjunto no se mueve al ir entrando. */}
        <AbsoluteFill
          style={{
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 104,
            padding: `0 ${SAFE_X}px`,
          }}
        >
          {data.questions.map((q, i) => {
            const from = M5.questionsStart + i * M5.questionStagger;
            return (
              <KineticText
                key={i}
                text={q}
                span={{ from, to: from + M5.questionDuration }}
                out={M5.questionsOut}
                variant="body"
                size={TYPE.h2}
                color={i === 0 ? COLORS.boneDim : COLORS.bone}
                align="center"
                travel={26}
              />
            );
          })}
        </AbsoluteFill>

        {/* ── REMATE ────────────────────────────────────────────────── */}
        {punchAlive > 0.001 ? (
          <PushIn span={M5.punchPushIn} to={1.05}>
            <AbsoluteFill
              style={{
                alignItems: "center",
                justifyContent: "center",
                padding: `0 ${SAFE_X}px`,
                opacity: punchAlive,
              }}
            >
              <KineticText
                text={data.punch}
                span={M5.punch}
                variant="hero"
                align="center"
                travel={40}
              />
            </AbsoluteFill>
          </PushIn>
        ) : null}

        {/* ── FRAME FINAL · wordmark, sin CTA ───────────────────────── */}
        <AbsoluteFill
          style={{ alignItems: "center", justifyContent: "center", padding: `0 ${SAFE_X}px` }}
        >
          <MaskReveal
            span={frozen ? { from: 0, to: 1 } : M5.wordmark}
            travel={frozen ? 0 : 20}
          >
            <div
              style={{
                fontFamily: FONT.display,
                fontSize: TYPE.h2,
                letterSpacing: TRACKING.display,
                color: bone(0.82),
              }}
            >
              {data.wordmark}
            </div>
          </MaskReveal>
        </AbsoluteFill>
      </Backdrop>
    </AbsoluteFill>
  );
};
