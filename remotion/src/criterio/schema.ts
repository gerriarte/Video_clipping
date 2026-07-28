/**
 * Props de "Criterio".
 *
 * Todo el texto del episodio vive acá y se edita desde el panel de props de
 * Remotion Studio o desde el CLI (--props). Ningún movimiento tiene copy
 * hardcodeado: si hay que cambiar una palabra, se cambia en defaultProps.
 *
 * MARCADORES DE ÉNFASIS (los interpreta <RichLine>, ver richtext.tsx):
 *   *palabra*   → rojo. Solo para palabras-activación. Ver REGLA DEL ROJO.
 *   _palabra_   → énfasis por peso tipográfico, sin color.
 *   ~palabra~   → apagada a boneDim, casi fantasma.
 */
import { z } from "zod";

export const criterioSchema = z.object({
  /** Locución. Opcional: sin audio el episodio corre igual, con los timings
   *  placeholder de timing.ts. */
  audioSrc: z.string().optional(),

  /** EL DATO DURO del episodio (M4). Años de esperanza de vida a los 65.
   *  Expuesto al tope del schema porque es el único número real del video. */
  lifeExpectancyAt65: z.number(),

  m1: z.object({
    headline: z.string(),
    kicker: z.string(),
    /** Bloque de output IA que se autocompleta en la mitad B del split. */
    aiLines: z.array(z.string()),
    question: z.string(),
  }),

  m2: z.object({
    leftLabel: z.string(),
    rightLabel: z.string(),
    /** El golpe central. La palabra-activación va entre asteriscos. */
    hit: z.string(),
    list: z.array(z.string()),
    closing: z.string(),
  }),

  m3: z.object({
    fallingLabel: z.string(),
    risingLabel: z.string(),
    rule: z.string(),
    headLeft: z.string(),
    headRight: z.string(),
    /** Se emparejan por índice: fila i de la izquierda con fila i de la derecha. */
    depreciated: z.array(z.string()),
    appreciated: z.array(z.string()),
    seal: z.string(),
  }),

  m4: z.object({
    /** Etiqueta del bloque que el mercado expulsa del frame. */
    blockLabel: z.string(),
    /** El valor lo pone `lifeExpectancyAt65`; acá solo su presentación. */
    dataUnit: z.string(),
    dataLabel: z.string(),
    /** Nota de fuente al pie del dato. Vacío = no se muestra. */
    dataSource: z.string(),
    gaugeTitle: z.string(),
    juniorLabel: z.string(),
    juniorNote: z.string(),
    juniorFrom: z.number(),
    juniorTo: z.number(),
    criterioLabel: z.string(),
    criterioNote: z.string(),
    criterioFrom: z.number(),
    criterioTo: z.number(),
    gaugeScaleMax: z.number(),
    crossLabel: z.string(),
    punch: z.string(),
  }),

  m5: z.object({
    /** La traba: dos caras enfrentadas. */
    faceA: z.string(),
    faceB: z.string(),
    /** La llave que queda suspendida entre las dos y nadie agarra. */
    keyLabel: z.string(),
    /** Las dos mitades desalineadas que después encajan. */
    assembleTop: z.string(),
    assembleBottom: z.string(),
    /** La línea que queda cuando encajan. */
    assembled: z.string(),
    /** Cierre conceptual, full-screen. */
    concept: z.string(),
    /** Cierre interactivo: se muestran de a una, con aire. */
    questions: z.array(z.string()),
    /** Remate final. La activación va entre asteriscos. */
    punch: z.string(),
    /** Wordmark del frame final. Sin CTA. */
    wordmark: z.string(),
  }),
});

export type CriterioProps = z.infer<typeof criterioSchema>;

export const criterioDefaults: CriterioProps = {
  // PLACEHOLDER: el prompt cortó justo en este número ("esperanza de vida a los
  // 65 → [X] años"). Reemplazar por el dato real antes de publicar.
  lifeExpectancyAt65: 21,

  m1: {
    headline: "10 AÑOS DE\nEXPERIENCIA",
    kicker: "filtra +45",
    aiLines: [
      "> generando plan de go-to-market…",
      "  1. segmentación por cohorte de uso",
      "  2. pricing por valor percibido",
      "  3. canal: outbound + partners",
      "  4. métricas: CAC, payback, NRR",
      "listo. ¿querés que lo desarrolle?",
    ],
    question: "¿por qué\nse descarta\ntan barato\nal que\nla tiene?",
  },

  m2: {
    leftLabel: "Información acumulada",
    rightLabel: "Error acumulado",
    hit: "El criterio\nes *error*\nacumulado.\nNo\ninformación.",
    list: [
      "nunca perdió un cliente",
      "nunca bancó una decisión",
      "no tiene consecuencias",
    ],
    closing: "no es saber la respuesta —\nes _oler_ que la respuesta\nplausible está mal",
  },

  m3: {
    fallingLabel: "Ejecución",
    risingLabel: "Criterio",
    rule: "lo abundante se abarata\nel valor migra a lo escaso",
    headLeft: "Se depreció",
    headRight: "Se apreció",
    depreciated: [
      "procedimiento en terreno muerto",
      "memoria de canal que ya no existe",
      "dirigir ejecución",
    ],
    appreciated: [
      "leer señal con datos incompletos",
      "oler que algo está mal",
      "saber qué NO resolver",
    ],
    seal: "30 años\noptimizando\nalgo que\ndesapareció\n= ~nostalgia\noperativa~",
  },

  m4: {
    blockLabel: "CRITERIO",
    dataUnit: "años",
    dataLabel: "esperanza de vida a los 65",
    dataSource: "",
    gaugeTitle: "El mercado paga al revés",
    juniorLabel: "Junior",
    juniorNote: "sueldos de guerra",
    juniorFrom: 20,
    juniorTo: 95,
    criterioLabel: "Criterio",
    criterioNote: "a precio de remate",
    criterioFrom: 90,
    criterioTo: 30,
    gaugeScaleMax: 100,
    crossLabel: "el cruce",
    punch: "se paga más\npor *ejecutar\nrápido*\nque por saber\nhacia dónde",
  },

  m5: {
    faceA: "el que tiene el criterio\nno se ve tipeando\nen una terminal",
    faceB: "vos tenés metido que\nsenior = caro y lento",
    keyLabel: "USD 20/mes",
    assembleTop: "CRITERIO",
    assembleBottom: "EJECUCIÓN",
    assembled: "por primera vez,\nen la misma persona",
    concept: "los problemas\nno son\ndifíciles.\nestán\n_desarmados_.",
    questions: [
      "mirá tu último trimestre",
      "¿cuánto de lo que producís\nespera criterio?",
      "¿cuánto de lo que sabés\nespera ejecución?",
    ],
    punch: "no es falta\nde recursos.\nes de\n*ARMADO*.",
    wordmark: "@muas-mind",
  },
};
