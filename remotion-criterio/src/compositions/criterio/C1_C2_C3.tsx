import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, STROKE, TYPE } from '../../theme';
import { AnimPane, BrandBar, FacePane } from '../../shared/FacePane';
import { DiagonalWipe } from '../../shared/DiagonalWipe';
import { FadeUp, Reveal, useDraw } from '../../shared/anim';
import {
  AccumulationContrast,
  ContradictionPair,
  HabitFilter,
  PriceCross,
} from '../../components/Criterio';
import { useCue } from '../../shared/useCue';

const EP = 'Episodio · Criterio';

/**
 * Sin A-roll grabado, los bloques compuestos para el split corren en
 * "solo": misma caja de 960, centrada, sin la mitad de abajo vacía. En
 * cuanto existan los clips a cámara se pasa el path por props y el bloque
 * vuelve al split, sin tocar una línea de animación.
 */
const paneMode = (arollSrc?: string) => (arollSrc ? 'split' : 'solo');

// ═══════════════════════════════════════════════════════════════
// C1 · ARRANQUE — 0:00–0:51
// ═══════════════════════════════════════════════════════════════
export const c1Schema = z.object({
  arollSrc: z.string().optional(),
  hook: z.string(),
  demand: z.object({ label: z.string(), value: z.string() }),
  filter: z.object({ label: z.string(), value: z.string() }),
  qualities: z.array(z.string()).length(3),
  question: z.string(),
});

/**
 * El bloque abre con una contradicción, no con una tesis. Las dos
 * condiciones se muestran unidas por un trazo, y el trazo se parte:
 * ese hueco es todo el bloque.
 *
 * Las tres cualidades ("impecable, perfecto, pulido") entran como texto
 * pelado, cada una exactamente cuando se pronuncia. Adornarlas sería
 * contradecir el argumento: lo que describen es superficie.
 */
export const C1_Arranque: React.FC<z.infer<typeof c1Schema>> = ({
  arollSrc,
  hook,
  demand,
  filter,
  qualities,
  question,
}) => {
  const fPair = useCue('c1.pair', 224);
  const fGap = useCue('c1.gap', 347);
  const fQual = useCue('c1.qual1', 592);
  const fQual2 = useCue('c1.qual2', 635);
  const fQual3 = useCue('c1.qual3', 663);
  const fQuestion = useCue('c1.question', 959);

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode={EP} />

      <AnimPane mode={paneMode(arollSrc)}>
        <Sequence durationInFrames={fQual - 12} name="contradicción">
          {/* El VO tarda siete segundos en llegar a la primera cifra. Sin
              esto la pantalla arranca vacía, que es peor que cualquier
              placa: el hook se dice y no se ve. */}
          <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
            <Reveal at={12} out={Math.max(24, fPair - 30)} style={{ ...TYPE.displayXL }}>
              {hook}
            </Reveal>
          </AbsoluteFill>

          {/* Dentro de su propia <Sequence>: los marcos de los dos paneles
              se dibujan siempre, así que montados desde el frame 0 se veían
              dos cajas vacías durante todo el hook. */}
          <Sequence from={fPair} name="par">
            <div style={{ position: 'absolute', left: LAYOUT.margin, top: 40 }}>
              <ContradictionPair
                at={0}
                gapAt={fGap - fPair}
                top={demand}
                bottom={{ ...filter, accent: true }}
              />
            </div>
          </Sequence>
        </Sequence>

        <Sequence from={fQual - 12} durationInFrames={fQuestion - fQual} name="cualidades">
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 200 }}>
            {qualities.map((q, i) => (
              <Reveal
                key={q}
                at={[12, fQual2 - fQual + 12, fQual3 - fQual + 12][i]}
                style={{ ...TYPE.displayXL, marginBottom: 8 }}
              >
                {q}
              </Reveal>
            ))}
          </div>
        </Sequence>

        <Sequence from={fQuestion} name="pregunta">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill
            style={{
              justifyContent: 'center',
              padding: `0 ${LAYOUT.margin}px`,
            }}
          >
            <Reveal at={24} style={{ ...TYPE.displayL }}>
              {question}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
      </AnimPane>

      {arollSrc ? <FacePane src={arollSrc} offsetY={-180} scale={1.15} /> : null}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════
// C2 · QUÉ ES ESTO EN SERIO — 0:51–1:32
// ═══════════════════════════════════════════════════════════════
export const c2Schema = z.object({
  definition: z.string(),
  negation: z.string(),
  /** Las tres condiciones del criterio, en el orden en que las dice el VO. */
  support: z.array(z.string()).length(3),
  leftLabel: z.string(),
  rightLabel: z.string(),
  leftFoot: z.string(),
  rightFoot: z.string(),
  closing: z.string(),
});

/**
 * La definición entra como negación antes que como afirmación: primero
 * se tacha "información acumulada", después aparece "error acumulado".
 * El orden importa —el espectador ya tenía la respuesta equivocada
 * cargada y hay que sacársela antes de poner la otra.
 */
export const C2_QueEs: React.FC<z.infer<typeof c2Schema>> = ({
  definition,
  negation,
  support,
  leftLabel,
  rightLabel,
  leftFoot,
  rightFoot,
  closing,
}) => {
  const fNeg = useCue('c2.negation', 18);
  const fDef = useCue('c2.definition', 151);
  const fSup1 = useCue('c2.sup1', 310);
  const fSup2 = useCue('c2.sup2', 377);
  const fSup3 = useCue('c2.sup3', 485);
  const fCols = useCue('c2.columns', 811);
  const fClose = useCue('c2.closing', 1069);

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode={EP} />
      <AnimPane mode="full">
        <Sequence durationInFrames={fCols - 12} name="definición">
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 160, width: 936 }}>
            {/* displayM y no displayL: en displayL "Información acumulada"
                se parte en dos líneas y el tachado le pega a una sola. */}
            <Reveal at={fNeg} style={{ ...TYPE.displayM, color: COLOR.muted }}>
              {negation}
            </Reveal>
            {/* Tachado que se dibuja. La negación se cancela en vivo, no
                aparece ya cancelada: el espectador ve el borrado. */}
            <Strike at={fNeg + 36} width={720} lift={38} />
            <div style={{ height: 60 }} />
            <Reveal at={fDef} style={{ ...TYPE.displayXL }}>
              {definition}
            </Reveal>
          </div>

          {/* Las tres condiciones, cada una con su palabra. El VO tarda
              veinte segundos en desplegar la definición: sin esto la placa
              se queda quieta todo ese tramo. */}
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 620, width: 936 }}>
            {support.map((s, i) => (
              <FadeUp
                key={s}
                at={[fSup1, fSup2, fSup3][i]}
                from="left"
                style={{ marginBottom: 26 }}
              >
                <div style={{ ...TYPE.body, fontSize: 44, color: COLOR.muted }}>{s}</div>
              </FadeUp>
            ))}
          </div>
        </Sequence>

        <Sequence from={fCols - 12} durationInFrames={fClose - fCols} name="acumulación">
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 180 }}>
            <AccumulationContrast
              at={24}
              span={fClose - fCols}
              leftLabel={leftLabel}
              rightLabel={rightLabel}
              leftFoot={leftFoot}
              rightFoot={rightFoot}
            />
          </div>
        </Sequence>

        <Sequence from={fClose} name="cierre">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill
            style={{
              justifyContent: 'center',
              padding: `0 ${LAYOUT.margin}px`,
            }}
          >
            <Reveal at={24} style={{ ...TYPE.displayL }}>
              {closing}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
      </AnimPane>
    </AbsoluteFill>
  );
};

/**
 * Tachado que se dibuja de izquierda a derecha. La negación se cancela
 * en vivo: el espectador ve el borrado, no encuentra la frase ya tachada.
 */
const Strike: React.FC<{ at: number; width: number; lift?: number }> = ({
  at,
  width,
  lift = 46,
}) => {
  const draw = useDraw(at, 24, width);
  return (
    <svg width={width} height={STROKE * 2} style={{ display: 'block', marginTop: -lift }}>
      <line
        x1={0}
        y1={STROKE}
        x2={width}
        y2={STROKE}
        stroke={COLOR.bone}
        strokeWidth={STROKE * 2}
        {...draw}
      />
    </svg>
  );
};

// ═══════════════════════════════════════════════════════════════
// C3 · LO QUE CAMBIÓ DE PRECIO — 1:32–2:25
// ═══════════════════════════════════════════════════════════════
export const c3Schema = z.object({
  crossDown: z.string(),
  crossUp: z.string(),
  scarcity: z.string(),
  trap: z.string(),
  rejected: z.string(),
  passes: z.array(z.string()).length(3),
  closing: z.string(),
});

/**
 * El cruce de curvas es un cliché de deck, pero acá el cruce ES la tesis
 * literal del bloque, así que se gana el lugar. Lo que lo saca del
 * cliché: sin ejes, sin grilla, sin gradiente, sin puntos de dato.
 *
 * Y después, inmediatamente, el filtro. Sin el filtro este bloque se
 * lee como "la experiencia vale", que es exactamente lo que el guion
 * NO dice.
 */
export const C3_Precio: React.FC<z.infer<typeof c3Schema>> = ({
  crossDown,
  crossUp,
  scarcity,
  trap,
  rejected,
  passes,
  closing,
}) => {
  const fCross = useCue('c3.cross', 18);
  const fScarcity = useCue('c3.scarcity', 424);
  const fTrap = useCue('c3.trap', 664);
  const fFilter = useCue('c3.filter', 888);
  const fPass1 = useCue('c3.pass1', 1099);
  const fPass2 = useCue('c3.pass2', 1237);
  const fPass3 = useCue('c3.pass3', 1325);
  const fClose = useCue('c3.closing', 1458);

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode={EP} />
      <AnimPane mode="full">
        <Sequence durationInFrames={fTrap - 12} name="cruce">
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 180 }}>
            <PriceCross at={fCross} labelDown={crossDown} labelUp={crossUp} />
          </div>
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 900, width: 936 }}>
            <Reveal at={fScarcity} style={{ ...TYPE.displayL }}>
              {scarcity}
            </Reveal>
          </div>
        </Sequence>

        <Sequence from={fTrap - 12} durationInFrames={fClose - fTrap} name="filtro">
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 140, width: 936 }}>
            <Reveal at={24} style={{ ...TYPE.displayM }}>
              {trap}
            </Reveal>
          </div>
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 320 }}>
            {/* Los frames del filtro son relativos a esta <Sequence>, que
                arranca en fTrap-12: de ahí el corrimiento. */}
            <HabitFilter
              at={fFilter - fTrap + 12}
              rejected={rejected}
              passes={passes}
              passAts={[fPass1, fPass2, fPass3].map((f) => f - fTrap + 12)}
            />
          </div>
        </Sequence>

        <Sequence from={fClose} name="cierre">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill
            style={{
              justifyContent: 'center',
              padding: `0 ${LAYOUT.margin}px`,
            }}
          >
            <Reveal at={24} style={{ ...TYPE.displayXL }}>
              {closing}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
      </AnimPane>
    </AbsoluteFill>
  );
};
