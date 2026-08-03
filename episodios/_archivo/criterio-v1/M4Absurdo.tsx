/**
 * M4 — EL ABSURDO   ·   frames 4500–6750   ·   2:30–3:45
 *
 * Beat: pico de incomodidad + el único dato duro del episodio.
 * Este es el movimiento del rojo. En el resto del video es un bisturí; acá es
 * el clima.
 *
 * FRAME GUIDES (locales a la Sequence)
 *   18–60      el bloque CRITERIO, sólido, ocupando el centro
 *   120–153    barrido diagonal: lo empuja fuera del frame
 *   153–240    el vacío que queda. Se sostiene: es el punto
 *   120–300    el fondo vira al gradiente de marca, lento
 *   315        DATO DURO · hard cut, sin transición de entrada
 *   315–378    el número cuenta hasta su valor (mono, escala grande)
 *   384–414    la etiqueta del dato
 *   720–756    el dato se va
 *   768–810    entra el ComparativeGauge
 *   825–1140   las barras se cruzan
 *   1560–1602  el gauge se va
 *   1620–1674  remate + push-in hasta el corte
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { COLORS, EASE, FONT, SPRING, TRACKING, bone, red } from "./theme";
import { Backdrop, DiagonalWipe, PushIn, ramp, useDamped } from "./primitives";
import { KineticText } from "./KineticText";
import { DataStat } from "./DataStat";
import { ComparativeGauge } from "./ComparativeGauge";
import { M4, SAFE_X, WIDTH, HEIGHT, frames } from "./timing";
import type { CriterioProps } from "./schema";

const BLOCK_W = 880;
const BLOCK_H = 360;
const BLOCK_X = (WIDTH - BLOCK_W) / 2;
const BLOCK_Y = (HEIGHT - BLOCK_H) / 2;

// ═══ EL ACTIVO EXPULSADO ═════════════════════════════════════════════════════

/**
 * El mercado expulsa el activo. El bloque es sólido (bone lleno, texto en
 * negativo): es lo único macizo del episodio. El barrido lo saca del frame en
 * un gesto seco, con easing de entrada — acelera y se va. Sin dramatismo.
 *
 * En vertical el barrido cruza de arriba hacia abajo, así que el bloque sale
 * por abajo, no por el costado: tiene que irse en la dirección del barrido.
 */
const ExpelledBlock: React.FC<{ label: string }> = ({ label }) => {
  const frame = useCurrentFrame();
  const enter = useDamped(M4.blockIn.from, SPRING.heavy);

  const push = ramp(frame, M4.expulsion, [0, 1500], EASE.in);
  const gone = push > 1400;

  // El hueco: el contorno de lo que estaba, una vez que ya no está.
  const voidIn = ramp(frame, {
    from: M4.expulsion.to - frames(0.2),
    to: M4.expulsion.to + frames(0.6),
  });

  return (
    <>
      {voidIn > 0 ? (
        <div
          style={{
            position: "absolute",
            left: BLOCK_X,
            top: BLOCK_Y,
            width: BLOCK_W,
            height: BLOCK_H,
            border: `1px dashed ${bone(0.16 * voidIn)}`,
          }}
        />
      ) : null}

      {gone ? null : (
        <div
          style={{
            position: "absolute",
            left: BLOCK_X,
            top: BLOCK_Y,
            width: BLOCK_W,
            height: BLOCK_H,
            backgroundColor: COLORS.bone,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `translateY(${push.toFixed(1)}px) scaleY(${(0.82 + enter * 0.18).toFixed(3)})`,
          }}
        >
          <div
            style={{
              fontFamily: FONT.display,
              fontSize: 116,
              letterSpacing: TRACKING.display,
              color: COLORS.bgDeep,
              clipPath: `inset(${(1 - enter) * 100}% 0% 0% 0%)`,
            }}
          >
            {label}
          </div>
        </div>
      )}
    </>
  );
};

// ═══ MOVIMIENTO ══════════════════════════════════════════════════════════════

export const M4Absurdo: React.FC<{
  data: CriterioProps["m4"];
  lifeExpectancyAt65: number;
}> = ({ data, lifeExpectancyAt65 }) => {
  const frame = useCurrentFrame();

  // El fondo vira al gradiente de marca. Tope 0.55: si llega a 1 el rojo deja
  // de ser un acento y se come el movimiento.
  const brandMix = ramp(frame, M4.bgShift, [0, 0.55]);

  const dataCut = frame >= M4.dataCut;
  const dataAlive = dataCut ? 1 - ramp(frame, M4.dataOut) : 0;
  const gaugeAlive = 1 - ramp(frame, M4.gaugeOut);
  const gaugeStarted = frame >= M4.gaugeIn.from;

  return (
    <AbsoluteFill>
      <Backdrop brandMix={brandMix}>
        {/* ── EXPULSIÓN ─────────────────────────────────────────────── */}
        {frame < M4.dataCut ? <ExpelledBlock label={data.blockLabel} /> : null}

        {/* ── DATO DURO ─────────────────────────────────────────────── */}
        {dataAlive > 0.001 ? (
          <AbsoluteFill
            style={{
              alignItems: "center",
              justifyContent: "center",
              padding: `0 ${SAFE_X}px`,
              opacity: dataAlive,
            }}
          >
            <DataStat
              value={lifeExpectancyAt65}
              unit={data.dataUnit}
              label={data.dataLabel}
              source={data.dataSource}
              count={M4.dataCount}
              labelSpan={M4.dataLabel}
            />
          </AbsoluteFill>
        ) : null}

        {/* ── COMPARATIVE GAUGE · junior vs criterio ────────────────── */}
        {gaugeStarted && gaugeAlive > 0.001 ? (
          <AbsoluteFill
            style={{
              alignItems: "flex-start",
              justifyContent: "center",
              padding: `0 ${SAFE_X}px`,
              opacity: gaugeAlive,
            }}
          >
            <div>
              <KineticText
                text={data.gaugeTitle}
                span={M4.gaugeIn}
                variant="display"
                style={{ marginBottom: 132 }}
              />

              <ComparativeGauge
                series={[
                  {
                    label: data.juniorLabel,
                    note: data.juniorNote,
                    from: data.juniorFrom,
                    to: data.juniorTo,
                    color: COLORS.red,
                  },
                  {
                    label: data.criterioLabel,
                    note: data.criterioNote,
                    from: data.criterioFrom,
                    to: data.criterioTo,
                    color: COLORS.bone,
                  },
                ]}
                scaleMax={data.gaugeScaleMax}
                entry={M4.gaugeIn}
                fill={M4.gaugeFill}
                crossLabel={data.crossLabel}
              />
            </div>
          </AbsoluteFill>
        ) : null}

        {/* ── REMATE ────────────────────────────────────────────────── */}
        <PushIn span={M4.punchPushIn} to={1.06}>
          <AbsoluteFill
            style={{ alignItems: "center", justifyContent: "center", padding: `0 ${SAFE_X}px` }}
          >
            <KineticText
              text={data.punch}
              span={M4.punch}
              variant="display"
              align="center"
              travel={40}
            />
          </AbsoluteFill>
        </PushIn>
      </Backdrop>

      {/* El barrido que expulsa el bloque. Por encima de todo. */}
      <DiagonalWipe span={M4.expulsion} color={red(0.9)} band={300} />
    </AbsoluteFill>
  );
};
