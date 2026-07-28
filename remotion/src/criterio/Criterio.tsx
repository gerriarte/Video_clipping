/**
 * "Criterio" — episodio editorial de 5 minutos.
 *
 * 1920×1080 · 30 fps · 9000 frames.
 *
 * Estructura: una <Sequence> por movimiento, premontada. Los cinco movimientos
 * son independientes entre sí — ninguno lee el frame absoluto de la timeline,
 * todos trabajan en frames locales contra las constantes de timing.ts.
 *
 * TRANSICIONES: corte seco. La única puntuación entre movimientos es un flash
 * de retícula de 8 frames sobre el corte. El barrido diagonal existe pero está
 * reservado para gestos internos (abrir el split de M1, expulsar el bloque de
 * M4). Coherencia, no variedad.
 */
import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
// El <Audio> de "remotion" quedó deprecado en 4.0.500 (se renombró a
// Html5Audio). El de @remotion/media es el camino nuevo: decodifica con
// mediabunny en vez de con el <audio> del navegador, así que en render el
// muestreo cae exacto en cada frame — que es justo lo que hace falta para
// sincronizar los beats de timing.ts contra la locución.
import { Audio } from "@remotion/media";
import { COLORS } from "./theme";
import { GridFlash } from "./primitives";
import { MOVEMENTS, CUT_FLASH, frames } from "./timing";
import { M1Fenomeno } from "./M1Fenomeno";
import { M2Criterio } from "./M2Criterio";
import { M3Inversion } from "./M3Inversion";
import { M4Absurdo } from "./M4Absurdo";
import { M5Cierre } from "./M5Cierre";
import type { CriterioProps } from "./schema";

/** Cuánto antes de entrar se monta cada Sequence (fuentes y layout listos
 *  antes del corte, sin un frame en blanco). */
const PREMOUNT = frames(1);

export const Criterio: React.FC<CriterioProps> = ({
  audioSrc,
  lifeExpectancyAt65,
  m1,
  m2,
  m3,
  m4,
  m5,
}) => (
  <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
    {audioSrc ? <Audio src={audioSrc} /> : null}

    <Sequence
      from={MOVEMENTS.m1.from}
      durationInFrames={MOVEMENTS.m1.duration}
      name="M1 · Fenómeno"
    >
      <M1Fenomeno data={m1} />
    </Sequence>

    <Sequence
      from={MOVEMENTS.m2.from}
      durationInFrames={MOVEMENTS.m2.duration}
      premountFor={PREMOUNT}
      name="M2 · Qué es el criterio"
    >
      <M2Criterio data={m2} />
    </Sequence>

    <Sequence
      from={MOVEMENTS.m3.from}
      durationInFrames={MOVEMENTS.m3.duration}
      premountFor={PREMOUNT}
      name="M3 · La inversión"
    >
      <M3Inversion data={m3} />
    </Sequence>

    <Sequence
      from={MOVEMENTS.m4.from}
      durationInFrames={MOVEMENTS.m4.duration}
      premountFor={PREMOUNT}
      name="M4 · El absurdo"
    >
      <M4Absurdo data={m4} lifeExpectancyAt65={lifeExpectancyAt65} />
    </Sequence>

    <Sequence
      from={MOVEMENTS.m5.from}
      durationInFrames={MOVEMENTS.m5.duration}
      premountFor={PREMOUNT}
      name="M5 · Traba y salida"
    >
      <M5Cierre data={m5} />
    </Sequence>

    {/* Puntuación de los cortes. Fuera de las Sequences: necesita el frame
        absoluto de la timeline, no el local de cada movimiento. */}
    <GridFlash at={MOVEMENTS.m2.from} duration={CUT_FLASH} />
    <GridFlash at={MOVEMENTS.m3.from} duration={CUT_FLASH} />
    <GridFlash at={MOVEMENTS.m4.from} duration={CUT_FLASH} />
    <GridFlash at={MOVEMENTS.m5.from} duration={CUT_FLASH} />
  </AbsoluteFill>
);
