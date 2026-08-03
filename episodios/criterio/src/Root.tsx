import React from 'react';
import { AbsoluteFill, Audio, Composition, staticFile } from 'remotion';
import { CANVAS, COLOR } from './theme';
import { BLOCK, BLOCKS, CRITERIO_TOTAL, type BlockKey } from './shared/cues';
import { CueScope } from './shared/useCue';
import { VoiceProvider } from './shared/voice';
import { Backdrop, BackdropTop } from './shared/Backdrop';
import { CriterioMaster, criterioSchema } from './compositions/criterio/CriterioMaster';
import {
  C1_Arranque,
  C2_QueEs,
  C3_Precio,
  c1Schema,
  c2Schema,
  c3Schema,
} from './compositions/criterio/C1_C2_C3';
import { C4_Absurdo, C5_Salida, c4Schema, c5Schema } from './compositions/criterio/C4_C5';

// ═══════════════════════════════════════════════════════════════
// EPISODIO · CRITERIO
// "El activo que el mercado está tirando justo cuando más vale"
//
// El VO ya está grabado y es el que manda: la duración de cada bloque y
// el frame de cada animación salen de public/captions.json. Todo el copy
// vive acá; no hay que tocar animación para corregir un texto.
// ═══════════════════════════════════════════════════════════════
const VO_CRITERIO = 'audio/vo-criterio.mp3';

/**
 * A-roll: todavía no hay clips a cámara, así que el episodio corre a
 * pantalla completa. Cuando existan, se completan estos paths (archivos
 * en public/video/) y C1, C4 y C5 vuelven solos al split que diseñó el
 * guion, sin tocar una línea de animación.
 */
const AROLL = {
  c1: '', // criterio-aroll-1.mp4 — cubre C1 (~50s)
  c4: '', // criterio-aroll-2.mp4 — cubre C4 (~55s)
  c5: '', // criterio-aroll-3.mp4 — cubre C5 (entra, sale y vuelve)
};

const C1 = {
  arollSrc: AROLL.c1,
  hook: 'Una contradicción\nque nadie ve.',
  demand: { label: 'Todo aviso pide', value: '10 años de experiencia' },
  filter: { label: 'Todo filtro corta en', value: '45 años' },
  qualities: ['Impecable.', 'Perfecto.', 'Pulido.'],
  question: '¿Por qué el mercado lo descarta tan rápido, y tan barato?',
};

const C2 = {
  negation: 'Información acumulada',
  definition: 'Error acumulado',
  support: [
    'Haber tomado una decisión',
    'Haber pagado el costo de equivocarte',
    'Y que te haya quedado en el cuerpo',
  ],
  leftLabel: 'Lo que la IA acumula',
  rightLabel: 'Lo que deja una consecuencia',
  leftFoot: 'Infinito. Gratis. Sin costo de equivocarse.',
  rightFoot: 'Cada marca costó un cliente, una decisión, una discusión.',
  closing: 'Información plausible, ordenada, infinita. Criterio, cero.',
};

const C3 = {
  crossDown: 'Ejecución',
  crossUp: 'Criterio',
  scarcity: 'Todo el valor se muda a lo que quedó escaso.',
  trap: 'No toda experiencia es criterio.',
  rejected: 'Costumbre',
  passes: [
    'Leer una situación con datos incompletos',
    'Oler que algo está mal antes de poder explicar por qué',
    'Saber qué problema conviene no resolver',
  ],
  closing: 'Eso no caducó.\nEso se disparó de precio.',
};

const C4 = {
  arollSrc: AROLL.c4,
  pivot: 'No te vengo a hablar de injusticia.\nTe vengo a hablar de vos.',
  tags: [
    {
      what: 'Talento junior',
      price: 'Sueldo de guerra',
      note: 'Produce lo mismo que la IA te da gratis',
    },
    {
      what: 'Criterio',
      price: 'Precio de remate',
      note: 'Disponible, mirándote de frente',
    },
  ],
  verdict: 'No es un problema moral.\nEstás comprando el ingrediente equivocado.',
};

const C5 = {
  arollSrc: AROLL.c5,
  barrier: 'La traba no es capacidad.\nEs identidad.',
  keyAmount: 20,
  keyCaption: 'Por mes. Lo que cuesta la llave que no agarra.',
  mirror: [
    'Y de tu lado: «senior» = «caro y lento».',
    'Ese modelo mental se formó cuando hacer era lo difícil.',
  ],
  halvesLeft: 'Criterio para resolverlo',
  halvesRight: 'Capacidad de ejecutarlo',
  halvesClosing: 'Nunca vivieron en la misma persona, al mismo tiempo.\nAhora sí pueden.',
  questions: [
    '¿Cuánto de lo que producís está esperando criterio?',
    '¿Cuánto de lo que ya sabés está esperando ejecución?',
  ],
  verdict: 'Tu problema no es de plata ni de gente.\nEs de armado.',
};

/**
 * Preview de un bloque suelto, para iterar sin renderizar los cuatro
 * minutos y medio. Trae su tramo de VO y su origen de cues, así lo que se
 * ve en el Studio está sincronizado igual que en el master.
 */
const BlockPreview: React.FC<{ block: BlockKey; children: React.ReactNode }> = ({
  block,
  children,
}) => {
  const start = BLOCK[block].start;
  const index = BLOCKS.findIndex((b) => b.key === block);
  return (
    <VoiceProvider src={VO_CRITERIO} startFrom={start}>
      <AbsoluteFill style={{ backgroundColor: COLOR.bg }} />
      <Audio src={staticFile(VO_CRITERIO)} trimBefore={start} />
      <Backdrop total={CRITERIO_TOTAL} blockIndex={index} blockCount={BLOCKS.length} />
      <CueScope start={start}>{children}</CueScope>
      <BackdropTop />
    </VoiceProvider>
  );
};

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="CriterioMaster"
      component={CriterioMaster}
      schema={criterioSchema}
      durationInFrames={CRITERIO_TOTAL}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={{ voSrc: VO_CRITERIO, c1: C1, c2: C2, c3: C3, c4: C4, c5: C5 }}
    />

    {/* Bloques sueltos. La duración también la manda el audio. */}
    <Composition
      id="C1-Arranque"
      component={(props: React.ComponentProps<typeof C1_Arranque>) => (
        <BlockPreview block="c1">
          <C1_Arranque {...props} />
        </BlockPreview>
      )}
      schema={c1Schema}
      durationInFrames={BLOCK.c1.duration}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={C1}
    />
    <Composition
      id="C2-QueEs"
      component={(props: React.ComponentProps<typeof C2_QueEs>) => (
        <BlockPreview block="c2">
          <C2_QueEs {...props} />
        </BlockPreview>
      )}
      schema={c2Schema}
      durationInFrames={BLOCK.c2.duration}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={C2}
    />
    <Composition
      id="C3-Precio"
      component={(props: React.ComponentProps<typeof C3_Precio>) => (
        <BlockPreview block="c3">
          <C3_Precio {...props} />
        </BlockPreview>
      )}
      schema={c3Schema}
      durationInFrames={BLOCK.c3.duration}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={C3}
    />
    <Composition
      id="C4-Absurdo"
      component={(props: React.ComponentProps<typeof C4_Absurdo>) => (
        <BlockPreview block="c4">
          <C4_Absurdo {...props} />
        </BlockPreview>
      )}
      schema={c4Schema}
      durationInFrames={BLOCK.c4.duration}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={C4}
    />
    <Composition
      id="C5-Salida"
      component={(props: React.ComponentProps<typeof C5_Salida>) => (
        <BlockPreview block="c5">
          <C5_Salida {...props} />
        </BlockPreview>
      )}
      schema={c5Schema}
      durationInFrames={BLOCK.c5.duration}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={C5}
    />
  </>
);
