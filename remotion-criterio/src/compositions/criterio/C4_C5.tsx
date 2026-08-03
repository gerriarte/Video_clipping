import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { z } from 'zod';
import { COLOR, LAYOUT, TYPE } from '../../theme';
import { AnimPane, BrandBar, FacePane } from '../../shared/FacePane';
import { DiagonalWipe } from '../../shared/DiagonalWipe';
import { FadeUp, Reveal } from '../../shared/anim';
import { PriceKey, PriceTags, ProductiveLife, TwoHalves } from '../../components/Criterio';
import { useCue } from '../../shared/useCue';

const EP = 'Episodio · Criterio';

/** Ver C1_C2_C3: sin A-roll, el bloque de split corre en "solo". */
const paneMode = (arollSrc?: string) => (arollSrc ? 'split' : 'solo');

// ═══════════════════════════════════════════════════════════════
// C4 · EL ABSURDO — 2:25–3:18
// ═══════════════════════════════════════════════════════════════
export const c4Schema = z.object({
  arollSrc: z.string().optional(),
  pivot: z.string(),
  tags: z.array(z.object({ what: z.string(), price: z.string(), note: z.string() })).length(2),
  verdict: z.string(),
});

/**
 * Es el momento en que el guion deja de hablar del mercado y pasa a
 * hablarle al espectador ("no te vengo a hablar de injusticia, te vengo a
 * hablar de vos"). Ese giro pide cara: en voz en off suena a denuncia, a
 * cámara suena a acusación amable, que es lo que corresponde. Con A-roll,
 * el bloque entero va en split.
 */
export const C4_Absurdo: React.FC<z.infer<typeof c4Schema>> = ({
  arollSrc,
  pivot,
  tags,
  verdict,
}) => {
  const fLife = useCue('c4.life', 18);
  const fCut = useCue('c4.cut', 407);
  const fPivot = useCue('c4.pivot', 624);
  const fTags = useCue('c4.tag1', 921);
  const fTag2 = useCue('c4.tag2', 1189);
  const fVerdict = useCue('c4.verdict', 1350);

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode={EP} />

      <AnimPane mode={paneMode(arollSrc)}>
        <Sequence durationInFrames={fPivot - 12} name="vida productiva">
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 240 }}>
            <ProductiveLife at={fLife} cutAt={fCut} />
          </div>
        </Sequence>

        <Sequence from={fPivot - 12} durationInFrames={fTags - fPivot} name="giro">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
            <Reveal at={24} style={{ ...TYPE.displayXL }}>
              {pivot}
            </Reveal>
          </AbsoluteFill>
        </Sequence>

        <Sequence from={fTags} durationInFrames={fVerdict - fTags} name="precios">
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 180 }}>
            {/* Cada etiqueta entra cuando el VO la nombra: "sueldos de
                guerra" primero, "precio de remate" nueve segundos después. */}
            <PriceTags at={24} ats={[12, fTag2 - fTags]} rows={tags} />
          </div>
        </Sequence>

        <Sequence from={fVerdict} name="veredicto">
          <DiagonalWipe at={0} duration={24} />
          <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
            <Reveal at={24} style={{ ...TYPE.displayL }}>
              {verdict}
            </Reveal>
          </AbsoluteFill>
        </Sequence>
      </AnimPane>

      {arollSrc ? <FacePane src={arollSrc} offsetY={-180} scale={1.15} /> : null}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════════════════
// C5 · LA TRABA Y LA SALIDA — 3:18–4:31
// ═══════════════════════════════════════════════════════════════
export const c5Schema = z.object({
  arollSrc: z.string().optional(),
  barrier: z.string(),
  keyAmount: z.number(),
  keyCaption: z.string(),
  /** Las dos líneas del espejo: la segunda entra con su propia palabra. */
  mirror: z.array(z.string()).length(2),
  halvesLeft: z.string(),
  halvesRight: z.string(),
  halvesClosing: z.string(),
  questions: z.array(z.string()).length(2),
  verdict: z.string(),
});

/**
 * Único bloque que cambia de modo por dentro (cuando hay A-roll).
 *
 * El diagrama de los dos círculos es la firma del episodio y en 1080×960
 * queda apretado: necesita el pane completo. Así que el rostro sale
 * durante ese tramo y vuelve para las dos preguntas finales.
 *
 * La transición SPLIT→FULL→SPLIT no es capricho de layout: marca que ese
 * es el único momento del video donde el argumento deja de ser
 * diagnóstico y pasa a ser salida.
 */
export const C5_Salida: React.FC<z.infer<typeof c5Schema>> = (props) => {
  const fBarrier = useCue('c5.barrier', 18);
  const fKey = useCue('c5.key', 345);
  const fMirror = useCue('c5.mirror', 558);
  const fMirror2 = useCue('c5.mirror2', 688);
  const fHalves = useCue('c5.halves', 1025);
  const fLeft = useCue('c5.left', 1115);
  const fRight = useCue('c5.right', 1200);
  const fMerge = useCue('c5.merge', 1425);
  const fQ1 = useCue('c5.q1', 1671);
  const fQ2 = useCue('c5.q2', 1847);
  const fVerdict = useCue('c5.verdict', 2009);

  /** El tramo FULL arranca acá; adentro los frames vuelven a cero. */
  const halvesFrom = fHalves - 12;
  /**
   * El corte a las preguntas no va en "último trimestre" sino un pelo
   * antes de la primera pregunta: entre una cosa y la otra el VO mete
   * cuatro segundos ("antes de contratar a nadie, andá a tu último
   * trimestre y hacete dos preguntas") y la pantalla quedaba vacía.
   */
  const questionsFrom = fQ1 - 24;

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <BrandBar episode={EP} />

      {/* ── Tramo 1 · la traba ────────────────────────────────── */}
      <Sequence durationInFrames={halvesFrom} name="traba">
        <AnimPane mode={paneMode(props.arollSrc)}>
          <Sequence durationInFrames={fMirror - 12} name="identidad">
            <div style={{ position: 'absolute', left: LAYOUT.margin, top: 120, width: 936 }}>
              <Reveal at={fBarrier} style={{ ...TYPE.displayL }}>
                {props.barrier}
              </Reveal>
            </div>
            <div style={{ position: 'absolute', left: LAYOUT.margin, top: 520 }}>
              <PriceKey at={fKey} amount={props.keyAmount} caption={props.keyCaption} />
            </div>
          </Sequence>

          <Sequence from={fMirror - 12} name="espejo">
            <DiagonalWipe at={0} duration={24} />
            <AbsoluteFill style={{ justifyContent: 'center', padding: `0 ${LAYOUT.margin}px` }}>
              {/* Dos líneas, dos momentos: el modelo mental y su fecha de
                  vencimiento no se dicen juntos. */}
              <Reveal at={24} style={{ ...TYPE.displayL }}>
                {props.mirror[0]}
              </Reveal>
              <Reveal
                at={Math.max(36, fMirror2 - fMirror + 12)}
                style={{ ...TYPE.displayL, color: COLOR.muted, marginTop: 32 }}
              >
                {props.mirror[1]}
              </Reveal>
            </AbsoluteFill>
          </Sequence>
        </AnimPane>
        {props.arollSrc ? (
          <FacePane src={props.arollSrc} offsetY={-180} scale={1.15} exitAt={halvesFrom - 20} />
        ) : null}
      </Sequence>

      {/* ── Tramo 2 · la salida ───────────────────────────────── */}
      <Sequence from={halvesFrom} durationInFrames={questionsFrom - halvesFrom} name="dos mitades">
        <AnimPane mode="full">
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 220 }}>
            <TwoHalves
              at={12}
              leftAt={fLeft - halvesFrom}
              rightAt={fRight - halvesFrom}
              /* El solape se pinta sobre "ahora sí pueden". USO 4/4 del
                 acento: es lo único del video que se lee como salida. */
              mergeAt={fMerge - halvesFrom}
              left={props.halvesLeft}
              right={props.halvesRight}
            />
          </div>
          {/* displayM y no displayL: en displayL la frase se va a cuatro
              líneas y la última cae dentro de la banda de subtítulos. */}
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 900, width: 936 }}>
            <Reveal at={fMerge - halvesFrom + 18} style={{ ...TYPE.displayM }}>
              {props.halvesClosing}
            </Reveal>
          </div>
        </AnimPane>
      </Sequence>

      {/* ── Tramo 3 · las dos preguntas ───────────────────────── */}
      <Sequence from={questionsFrom} name="preguntas">
        {/* Sin rostro este tramo va a pane completo: las dos preguntas más
            el veredicto no entran en la caja de 960 y el cierre del
            episodio quedaba cortado abajo. */}
        <AnimPane mode={props.arollSrc ? 'split' : 'full'}>
          <DiagonalWipe at={0} duration={24} />
          <div style={{ position: 'absolute', left: LAYOUT.margin, top: 200, width: 936 }}>
            {props.questions.map((q, i) => {
              const at = [fQ1, fQ2][i] - questionsFrom;
              return (
                <div key={q} style={{ display: 'flex', gap: 28, marginBottom: 64 }}>
                  <FadeUp at={at}>
                    <div style={{ ...TYPE.footnote, paddingTop: 14 }}>
                      {String(i + 1).padStart(2, '0')}
                    </div>
                  </FadeUp>
                  <Reveal at={at} style={{ ...TYPE.displayM, maxWidth: 820 }} tracking="-0.02em">
                    {q}
                  </Reveal>
                </div>
              );
            })}
            <Reveal at={fVerdict - questionsFrom} style={{ ...TYPE.displayL, marginTop: 40 }}>
              {props.verdict}
            </Reveal>
          </div>
        </AnimPane>
        {props.arollSrc ? (
          <FacePane
            src={props.arollSrc}
            offsetY={-180}
            scale={1.15}
            enterAt={0}
            startFrom={questionsFrom}
          />
        ) : null}
      </Sequence>
    </AbsoluteFill>
  );
};
