/**
 * M2 — QUÉ ES EL CRITERIO   ·   frames 1350–2700   ·   0:45–1:30
 *
 * Beat: la frase bisagra. Definición por negación, en dos columnas que se
 * construyen alternadas.
 *
 * FRAME GUIDES (locales a la Sequence)
 *   18–60     columna izquierda (IA): tokens fluyendo hacia arriba, infinitos
 *   66–102    columna derecha (criterio): la superficie donde se graba
 *   120–…     muescas, de a una, cada 34 frames · impacto con micro-shake
 *   570–606   las columnas se van
 *   606–648   GOLPE: "El criterio es *error* acumulado. No información."
 *   606–930   push-in lento sobre el golpe
 *   942–…     micro-lista rápida (3 ítems que entran y se van)
 *   1125–1176 cierre
 *
 * ROJO: una sola palabra en todo el movimiento — "error", en el golpe central.
 */
import React from "react";
import { AbsoluteFill, random, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, SPRING, TYPE, bone } from "./theme";
import {
  Backdrop,
  BlurFocus,
  Kicker,
  MaskReveal,
  PushIn,
  ramp,
  useDamped,
  useShake,
} from "./primitives";
import { KineticText } from "./KineticText";
import { M2, SAFE_X, WIDTH, frames } from "./timing";
import type { CriterioProps } from "./schema";

// ═══ COLUMNA IZQUIERDA · información que fluye ═══════════════════════════════

const PARTICLE_COUNT = 68;
const TOKEN_POOL = ["01", "·", "0x", "//", "▁", "··", "1", "—", "0", "::"];

/** Ancho de cada columna. Dos columnas + aire lateral entran en 1080. */
const COL_W = 424;
/** Alto: las columnas ocupan el grueso del frame, no una franja del centro. */
const COL_H = 1120;
const COL_TOP = 336;

/**
 * Tokens que suben sin parar. No se acumulan en ningún lado, no dejan marca:
 * el flujo es el punto. Determinista vía `random`, así el render distribuido
 * da el mismo resultado en todos los workers.
 */
const InfoFlow: React.FC<{ opacity: number }> = ({ opacity }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const W = COL_W;
  const H = COL_H;
  // Las velocidades están en px por 1/30 s. Normalizadas al fps, el flujo sube
  // igual de rápido en pantalla a 30 que a 60.
  const t = (frame / fps) * 30;

  return (
    <svg width={W} height={H} style={{ opacity }}>
      {Array.from({ length: PARTICLE_COUNT }, (_, i) => {
        const x = random(`px${i}`) * W;
        const speed = 1.4 + random(`ps${i}`) * 2.8;
        const phase = random(`pp${i}`) * H;
        // Módulo sobre la altura: el flujo no tiene principio ni fin.
        const y = H - (((t * speed + phase) % (H + 60)) - 30);
        const a = 0.18 + random(`pa${i}`) * 0.3;
        const token = TOKEN_POOL[Math.floor(random(`pt${i}`) * TOKEN_POOL.length)];
        return (
          <text
            key={i}
            x={x}
            y={y}
            fontFamily={FONT.mono}
            fontSize={17 + random(`pz${i}`) * 11}
            fill={bone(a)}
          >
            {token}
          </text>
        );
      })}
    </svg>
  );
};

// ═══ COLUMNA DERECHA · error que se graba ════════════════════════════════════

const NOTCH_H = 132;
const NOTCH_GAP = 34;
const GROUP_W = 200;
const ROW_H = 252;
/** Grupos por fila. Dos entran en una columna de 424; tres no. */
const GROUPS_PER_ROW = 2;

/** Geometría de la muesca i: grupos de 5 (cuatro rectas + una cruzada). */
const notchGeometry = (i: number) => {
  const g = Math.floor(i / 5);
  const idx = i % 5;
  const gx = (g % GROUPS_PER_ROW) * GROUP_W;
  const gy = Math.floor(g / GROUPS_PER_ROW) * ROW_H;
  if (idx < 4) {
    const x = gx + idx * NOTCH_GAP;
    return { x1: x, y1: gy, x2: x + 5, y2: gy + NOTCH_H };
  }
  // La quinta cruza el grupo entero: es la que cierra la cuenta.
  return { x1: gx - 14, y1: gy + NOTCH_H, x2: gx + 3 * NOTCH_GAP + 20, y2: gy };
};

/**
 * Una muesca. No aparece: se graba. Entra con spring seco (sin rebote) y un
 * micro-shake que decae en medio segundo — el impacto tiene que sentirse en
 * el peso, no en el rebote.
 */
const Notch: React.FC<{ index: number; delay: number }> = ({ index, delay }) => {
  const p = useDamped(delay, SPRING.hit);
  const shake = useShake(delay, 9, 0.53, `n${index}`);
  const g = notchGeometry(index);

  // La muesca se dibuja de una punta a la otra, no se desvanece hacia adentro.
  const x2 = g.x1 + (g.x2 - g.x1) * p;
  const y2 = g.y1 + (g.y2 - g.y1) * p;

  return (
    <g transform={`translate(${shake.x.toFixed(2)}, ${shake.y.toFixed(2)})`}>
      <line
        x1={g.x1}
        y1={g.y1}
        x2={x2}
        y2={y2}
        stroke={COLORS.bone}
        strokeWidth={10}
        strokeLinecap="butt"
        opacity={0.88}
      />
    </g>
  );
};

// ═══ MOVIMIENTO ══════════════════════════════════════════════════════════════

export const M2Criterio: React.FC<{ data: CriterioProps["m2"] }> = ({ data }) => {
  const frame = useCurrentFrame();

  const columnsOut = ramp(frame, M2.columnsOut);
  const columnsAlive = 1 - columnsOut;

  const leftIn = ramp(frame, M2.leftColumn);
  const rightIn = ramp(frame, M2.rightColumn);

  const hitIn = ramp(frame, M2.hit);
  const hitOut = ramp(frame, M2.hitOut);
  const hitAlive = hitIn * (1 - hitOut);

  return (
    <AbsoluteFill>
      <Backdrop>
        {/* ── LAS DOS COLUMNAS ──────────────────────────────────────── */}
        <AbsoluteFill style={{ opacity: columnsAlive }}>
          {/* Izquierda · INFORMACIÓN acumulada */}
          <div style={{ position: "absolute", left: SAFE_X, top: COL_TOP }}>
            <div
              style={{
                // El clip vertical descubre el flujo desde abajo, como si la
                // columna se llenara. Nunca un fade.
                clipPath: `inset(${(1 - leftIn) * 100}% 0% 0% 0%)`,
              }}
            >
              <InfoFlow opacity={0.9} />
            </div>
            <MaskReveal
              span={{ from: M2.leftColumn.to, to: M2.leftColumn.to + frames(0.47) }}
              style={{ marginTop: 28, width: COL_W }}
            >
              <Kicker color={COLORS.boneDim}>{data.leftLabel}</Kicker>
            </MaskReveal>
          </div>

          {/* Derecha · ERROR acumulado */}
          <div style={{ position: "absolute", left: WIDTH - SAFE_X - COL_W, top: COL_TOP }}>
            {/* Las muescas ocupan dos filas de grupos; se centran en la caja
                para que la columna pese lo mismo que el flujo de la izquierda
                y las dos etiquetas queden a la misma altura. */}
            <svg width={COL_W} height={COL_H} style={{ opacity: rightIn }}>
              <g transform={`translate(0, ${(COL_H - (ROW_H + NOTCH_H)) / 2})`}>
                {Array.from({ length: M2.notchCount }, (_, i) => (
                  <Notch key={i} index={i} delay={M2.notchesStart + i * M2.notchStagger} />
                ))}
              </g>
            </svg>
            <MaskReveal
              span={{ from: M2.rightColumn.to, to: M2.rightColumn.to + frames(0.47) }}
              style={{ marginTop: 28, width: COL_W }}
            >
              <Kicker color={COLORS.bone}>{data.rightLabel}</Kicker>
            </MaskReveal>
          </div>
        </AbsoluteFill>

        {/* ── GOLPE CENTRAL · la frase bisagra ──────────────────────── */}
        {hitAlive > 0.001 ? (
          <PushIn span={M2.hitPushIn} to={1.07}>
            <AbsoluteFill
              style={{
                alignItems: "center",
                justifyContent: "center",
                padding: `0 ${SAFE_X}px`,
                opacity: hitAlive,
              }}
            >
              <KineticText
                text={data.hit}
                span={M2.hit}
                out={M2.hitOut}
                variant="hero"
                align="center"
                travel={46}
              />
            </AbsoluteFill>
          </PushIn>
        ) : null}

        {/* ── MICRO-LISTA · entra y se va, rápido ───────────────────── */}
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          {data.list.map((item, i) => {
            const from = M2.listStart + i * M2.listItemStagger;
            const to = from + M2.listItemDuration;
            return (
              <BlurFocus
                key={i}
                span={{ from, to: from + frames(0.3) }}
                out={{ from: to, to: to + frames(0.3) }}
                blur={10}
                style={{ position: "absolute" }}
              >
                <div
                  style={{
                    fontFamily: FONT.body,
                    fontWeight: 500,
                    fontSize: TYPE.h2 + 12,
                    letterSpacing: "-0.01em",
                    color: COLORS.boneDim,
                    whiteSpace: "nowrap",
                  }}
                >
                  {item}
                </div>
              </BlurFocus>
            );
          })}
        </AbsoluteFill>

        {/* ── CIERRE ────────────────────────────────────────────────── */}
        <AbsoluteFill
          style={{ alignItems: "center", justifyContent: "center", padding: `0 ${SAFE_X}px` }}
        >
          <KineticText
            text={data.closing}
            span={M2.closing}
            variant="body"
            size={TYPE.h2}
            align="center"
            travel={30}
          />
        </AbsoluteFill>
      </Backdrop>
    </AbsoluteFill>
  );
};
