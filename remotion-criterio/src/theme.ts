/**
 * Sistema de diseño MultiAsking — episodio vertical.
 *
 * Si el proyecto de la serie ya expone un theme compartido, importalo acá
 * y reemplazá los valores de COLOR. El resto (layout, timing, type) es
 * específico del formato 9:16 y no existe en el sistema horizontal.
 */

// ─────────────────────────────────────────────────────────────
// COLOR
// ─────────────────────────────────────────────────────────────
export const COLOR = {
  bg: '#0A0A0A',
  bone: '#F2EFE9',
  accent: '#E2231A',
  muted: 'rgba(242, 239, 233, 0.46)',
  hairline: 'rgba(242, 239, 233, 0.14)',
  seam: 'rgba(242, 239, 233, 0.18)',
} as const;

/**
 * REGLA DEL ACENTO — el rojo aparece exactamente 4 veces en el episodio.
 * Cualquier uso fuera de esta lista es un bug, no una decisión.
 */
export const ACCENT_BUDGET = [
  'B1 · SEIS SEMANAS',
  'B2 · badge de confianza "Media"',
  'B4 · borde de comportamiento revelado',
  'B5 · tercera pregunta de cierre',
] as const;

// ─────────────────────────────────────────────────────────────
// CANVAS Y ZONAS SEGURAS
// ─────────────────────────────────────────────────────────────
export const CANVAS = { width: 1080, height: 1920, fps: 30 } as const;

export const SAFE = {
  /** Barra de marca. Sacrificable: la UI de la plataforma se monta acá. */
  top: 140,
  /** Bloque de caption de la plataforma. Nada legible por debajo. */
  bottom: 1570,
  /** Columna de acciones (like/comentar/compartir). */
  right: 940,
} as const;

export const LAYOUT = {
  margin: 72,
  baseline: 12,
  /** Reloj del episodio, justo debajo de la barra de marca. */
  progressY: 132,
  /** SPLIT: pane de animación */
  splitPane: { y: 140, height: 960 },
  /** SPLIT: costura entre panes */
  seamY: 1100,
  /** SPLIT: pane de rostro */
  facePane: { y: 1100, height: 820 },
  /** FULL: pane de animación a sangre */
  fullPane: { y: 140, height: 1780 },
  /** Banda de subtítulos en SPLIT: justo arriba de la costura. */
  subtitles: { y: 980, height: 160 },
  /**
   * Banda de subtítulos en FULL. Sin rostro, el pane de animación llega
   * hasta abajo y la banda de 980 le caía encima al contenido; acá va
   * debajo de todo y todavía arriba de la línea de caption (1570).
   */
  subtitlesFull: { y: 1320, height: 160 },
  /** Ancho útil entre márgenes */
  get contentWidth() {
    return CANVAS.width - this.margin * 2;
  },
} as const;

/** Ángulo único del wipe diagonal en todo el episodio. */
export const WIPE_ANGLE = 22;

// ─────────────────────────────────────────────────────────────
// TIPOGRAFÍA
// ─────────────────────────────────────────────────────────────
export const FONT = {
  display: "'Archivo Black', 'Archivo', sans-serif",
  body: "'Archivo', 'Inter', system-ui, sans-serif",
} as const;

type TypeStyle = React.CSSProperties;

export const TYPE: Record<
  'displayXL' | 'displayL' | 'displayM' | 'body' | 'label' | 'footnote',
  TypeStyle
> = {
  displayXL: {
    whiteSpace: 'pre-line',
    fontFamily: FONT.display,
    fontSize: 132,
    lineHeight: 0.92,
    letterSpacing: '-0.03em',
    color: COLOR.bone,
  },
  displayL: {
    whiteSpace: 'pre-line',
    fontFamily: FONT.display,
    fontSize: 96,
    lineHeight: 0.94,
    letterSpacing: '-0.025em',
    color: COLOR.bone,
  },
  displayM: {
    whiteSpace: 'pre-line',
    fontFamily: FONT.display,
    fontSize: 72,
    lineHeight: 1,
    letterSpacing: '-0.02em',
    color: COLOR.bone,
  },
  body: {
    whiteSpace: 'pre-line',
    fontFamily: FONT.body,
    fontSize: 40,
    fontWeight: 500,
    lineHeight: 1.35,
    letterSpacing: 0,
    color: COLOR.bone,
  },
  label: {
    fontFamily: FONT.body,
    fontSize: 28,
    fontWeight: 600,
    lineHeight: 1.3,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    color: COLOR.bone,
  },
  footnote: {
    fontFamily: FONT.body,
    fontSize: 22,
    fontWeight: 500,
    lineHeight: 1.3,
    letterSpacing: '0.04em',
    color: COLOR.muted,
  },
};

/** Números: ancho fijo para que los contadores no salten. */
export const TABULAR: TypeStyle = {
  fontVariantNumeric: 'tabular-nums',
  fontFeatureSettings: '"tnum"',
};

// ─────────────────────────────────────────────────────────────
// TIMING — todo múltiplo de 6 frames (0.2s)
// ─────────────────────────────────────────────────────────────
export const T = {
  enter: 18,
  exit: 12,
  holdMin: 60,
  modeTransition: 20,
  sectionWipe: 24,
  /** Máximo permitido sin cambio de estado en el pane de animación. */
  maxStatic: 150,
} as const;

/** Spring sobreamortiguado. Sin overshoot: el rebote rompe el registro. */
export const SPRING = { damping: 200, mass: 0.55, stiffness: 120 } as const;

/** Grosor mínimo: a 1080px un trazo de 1px titila tras la compresión. */
export const STROKE = 2;
