/**
 * Timings de "Criterio".
 *
 * TODOS los valores de este archivo son placeholders keyeados a una locución
 * que todavía no existe. Cada beat es una constante con nombre: para
 * re-sincronizar con la VO final se tocan estos números y nada más — ningún
 * movimiento tiene frames hardcodeados en su JSX.
 *
 * Convención: los beats DENTRO de un movimiento son locales al <Sequence>
 * (arrancan en 0), porque Remotion resetea useCurrentFrame en cada Sequence.
 * Los rangos de MOVEMENTS son absolutos sobre la timeline de 9000 frames.
 */

/**
 * Frames por segundo. ES LA ÚNICA PERILLA: todo el episodio deriva de segundos
 * vía `frames()`, así que cambiar este número reescala la pieza entera sin
 * tocar nada más. No dejar NINGÚN offset en frames crudos en los componentes —
 * a 60 fps correría al doble de velocidad que el resto.
 */
export const FPS = 60;

/** 9:16 vertical — TikTok. El lado corto es el ancho: 1080 px es el límite
 *  real de toda la tipografía del episodio. */
export const WIDTH = 1080;
export const HEIGHT = 1920;

/** Segundos → frames. Exportado: los componentes lo usan para sus micro-timings. */
export const frames = (seconds: number) => Math.round(seconds * FPS);

export const DURATION = frames(300);

/** Zona segura lateral. La UI de TikTok come el borde derecho y el pie. */
export const SAFE_X = 84;

const s = frames;

// ═══ MOVIMIENTOS (absoluto) ══════════════════════════════════════════════════

export const MOVEMENTS = {
  m1: { from: s(0), duration: s(45) }, // 0:00–0:45  fenómeno
  m2: { from: s(45), duration: s(45) }, // 0:45–1:30  qué es el criterio
  m3: { from: s(90), duration: s(60) }, // 1:30–2:30  la inversión
  m4: { from: s(150), duration: s(75) }, // 2:30–3:45  el absurdo
  m5: { from: s(225), duration: s(75) }, // 3:45–5:00  traba y salida
} as const;

/** Duración del flash de gridline que puntúa cada corte entre movimientos. */
export const CUT_FLASH = s(0.27);

// ═══ M1 — FENÓMENO (local, 0–1350) ═══════════════════════════════════════════

export const M1 = {
  /** El barrido diagonal que abre el split. */
  splitWipe: { from: s(0.5), to: s(1.6) },
  /** "10 AÑOS DE EXPERIENCIA" — mitad A. */
  headline: { from: s(1.4), to: s(2.6) },
  /** "filtra +45" — el dato apagado debajo. */
  kicker: { from: s(3.0), to: s(3.8) },
  /** Mitad B: el bloque de output IA empieza a autocompletarse. */
  linesStart: s(5.0),
  /** Frames que tarda cada línea en escribirse. */
  lineDuration: s(1.7),
  /** Separación entre el arranque de una línea y la siguiente. */
  lineStagger: s(2.1),
  /** Las dos mitades se apagan un punto para dejar entrar la pregunta. */
  halvesRecede: { from: s(33.0), to: s(34.5) },
  /** La pregunta central. */
  question: { from: s(34.0), to: s(36.0) },
  /** Push-in lento sobre la pregunta, hasta el corte. */
  pushIn: { from: s(34.0), to: s(45.0) },
} as const;

// ═══ M2 — QUÉ ES EL CRITERIO (local, 0–1350) ═════════════════════════════════

export const M2 = {
  /** Columna izquierda (IA): las partículas arrancan primero. */
  leftColumn: { from: s(0.6), to: s(2.0) },
  /** Columna derecha (criterio): entra alternada, después. */
  rightColumn: { from: s(2.2), to: s(3.4) },
  /** Primera muesca grabada. */
  notchesStart: s(4.0),
  /** Cadencia entre muescas. Lenta: cada una pesa. */
  notchStagger: s(1.15),
  notchCount: 11,
  /** Las columnas se van antes del golpe central. */
  columnsOut: { from: s(19.0), to: s(20.2) },
  /** GOLPE: "El criterio es error acumulado. No información." */
  hit: { from: s(20.2), to: s(21.6) },
  /** Push-in lento sobre el golpe. */
  hitPushIn: { from: s(20.2), to: s(31.0) },
  hitOut: { from: s(30.0), to: s(31.2) },
  /** Micro-lista rápida: 3 ítems que entran y se van. */
  listStart: s(31.4),
  listItemDuration: s(1.5),
  listItemStagger: s(1.15),
  /** Cierre: "no es saber la respuesta — es oler que…". */
  closing: { from: s(37.5), to: s(39.2) },
} as const;

// ═══ M3 — LA INVERSIÓN (local, 0–1800) ═══════════════════════════════════════

export const M3 = {
  /** Ejes y etiquetas EJECUCIÓN / CRITERIO. */
  axes: { from: s(0.5), to: s(1.8) },
  /** La curva de EJECUCIÓN colapsa hacia cero. */
  execCurve: { from: s(2.0), to: s(7.0) },
  /** La curva de CRITERIO se dispara. Arranca después, cruza a la otra. */
  critCurve: { from: s(3.2), to: s(8.4) },
  /** El toque de rojo al tope de CRITERIO. */
  critPeak: { from: s(8.0), to: s(9.0) },
  /** La regla chica al pie del data-moment. */
  rule: { from: s(9.5), to: s(10.8) },
  /** El data-moment se va, entra EL FILTRO. */
  chartOut: { from: s(15.0), to: s(16.2) },
  /** Cabeceras SE DEPRECIÓ / SE APRECIÓ. */
  tableHead: { from: s(16.4), to: s(17.6) },
  /** Primera fila de la tabla. */
  rowsStart: s(18.4),
  /** Cadencia entre filas. Cada fila es un argumento, no un ítem de lista. */
  rowStagger: s(3.6),
  /** Cuánto tarda una fila en entrar. */
  rowDuration: s(1.2),
  /** Retardo entre que entra la fila izquierda y se tacha. */
  rowStrikeDelay: s(1.4),
  /** La tabla se va. */
  tableOut: { from: s(48.0), to: s(49.4) },
  /** Sello del movimiento: "30 años optimizando algo que desapareció…". */
  seal: { from: s(49.6), to: s(51.4) },
} as const;

// ═══ M4 — EL ABSURDO (local, 0–2250) ═════════════════════════════════════════

export const M4 = {
  /** El bloque CRITERIO, sólido, antes de que lo echen. */
  blockIn: { from: s(0.6), to: s(2.0) },
  /** El barrido que lo empuja fuera del frame. Gesto seco. */
  expulsion: { from: s(4.0), to: s(5.1) },
  /** El vacío que queda. Se sostiene: es el punto del movimiento. */
  voidHold: { from: s(5.1), to: s(8.0) },
  /** El fondo vira al gradiente de marca. Lento, casi imperceptible. */
  bgShift: { from: s(4.0), to: s(10.0) },
  /** DATO DURO — hard cut, sin transición de entrada. */
  dataCut: s(10.5),
  /** El número cuenta hasta su valor. Mono, escala grande. */
  dataCount: { from: s(10.5), to: s(12.6) },
  /** La etiqueta del dato, debajo. */
  dataLabel: { from: s(12.8), to: s(13.8) },
  dataOut: { from: s(24.0), to: s(25.2) },
  /** ComparativeGauge: junior vs criterio. Las barras se cruzan. */
  gaugeIn: { from: s(25.6), to: s(27.0) },
  /** Lento a propósito: el cruce tiene que poder leerse mientras pasa. */
  gaugeFill: { from: s(27.5), to: s(38.0) },
  gaugeOut: { from: s(52.0), to: s(53.4) },
  /** El remate del movimiento. */
  punch: { from: s(54.0), to: s(55.8) },
  punchPushIn: { from: s(54.0), to: s(75.0) },
} as const;

// ═══ M5 — TRABA Y SALIDA (local, 0–2250) ═════════════════════════════════════

export const M5 = {
  // ── La traba: dos caras enfrentadas y una llave que nadie agarra ──────────
  /** Cara de arriba: cómo se ve el que tiene criterio. */
  faceA: { from: s(1.0), to: s(2.6) },
  /** Cara de abajo: el prejuicio del que mira. Enfrentada a la anterior. */
  faceB: { from: s(4.2), to: s(5.8) },
  /** La llave aparece entre las dos. */
  keyIn: { from: s(7.4), to: s(8.6) },
  /** Titileo de la llave. Período completo del parpadeo. */
  keyBlinkPeriod: s(0.87),
  /** Hasta acá queda suspendida, sin que nadie la agarre. */
  trabaOut: { from: s(16.2), to: s(17.4) },

  // ── La salida: el ensamble ───────────────────────────────────────────────
  /** Las dos mitades entran desalineadas y separadas. */
  halvesIn: { from: s(17.8), to: s(19.6) },
  /** Frame exacto del encaje. El spring seco arranca acá. */
  snapAt: s(23.0),
  /** Destello rojo en el punto de encaje. Corto: destella y se apaga. */
  flash: { from: s(23.2), to: s(24.4) },
  /** La línea ensamblada: "por primera vez, en la misma persona". */
  assembled: { from: s(24.2), to: s(25.6) },
  assembleOut: { from: s(31.0), to: s(32.2) },

  // ── Cierre conceptual ────────────────────────────────────────────────────
  concept: { from: s(33.2), to: s(35.2) },
  conceptOut: { from: s(43.0), to: s(44.2) },

  // ── Cierre interactivo: tres preguntas, ritmo lento ──────────────────────
  /** Primera pregunta. Las otras dos salen de acá + questionStagger. */
  questionsStart: s(46.0),
  questionStagger: s(5.0),
  questionDuration: s(1.6),
  questionsOut: { from: s(62.0), to: s(63.4) },

  // ── Remate ───────────────────────────────────────────────────────────────
  punch: { from: s(64.0), to: s(66.0) },
  punchPushIn: { from: s(64.0), to: s(71.5) },
  punchOut: { from: s(71.0), to: s(72.0) },

  // ── Frame final ──────────────────────────────────────────────────────────
  /** El wordmark entra y a partir de `staticFrom` no se mueve más nada. */
  wordmark: { from: s(72.2), to: s(73.6) },
  staticFrom: s(74.0),
} as const;
