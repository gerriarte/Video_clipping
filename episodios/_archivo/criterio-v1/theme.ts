/**
 * Sistema de diseño de "Criterio".
 *
 * Todo lo visual del episodio sale de acá: colores, tipografías, curvas y
 * springs. Ningún movimiento define un color o una curva propia — si algo
 * necesita un valor nuevo, se agrega a este archivo y se hereda.
 */
import { Easing } from "remotion";
import { loadFont as loadArchivoBlack } from "@remotion/google-fonts/ArchivoBlack";
import { loadFont as loadArchivo } from "@remotion/google-fonts/Archivo";
import { loadFont as loadPlexMono } from "@remotion/google-fonts/IBMPlexMono";

// ═══ TIPOGRAFÍA ══════════════════════════════════════════════════════════════

const { fontFamily: archivoBlack } = loadArchivoBlack();
const { fontFamily: archivo } = loadArchivo();
const { fontFamily: plexMono } = loadPlexMono();

export const FONT = {
  /** Headlines. Peso único (900), sin cursiva. */
  display: archivoBlack,
  /** Cuerpo, etiquetas, listas. Variable: usar fontWeight explícito. */
  body: archivo,
  /** Solo números duros (M4) y tokens de dato. */
  mono: plexMono,
} as const;

// ═══ COLOR ═══════════════════════════════════════════════════════════════════

export const COLORS = {
  bg: "#0A0A0B",
  bgDeep: "#050506",
  bone: "#EDE7DA",
  boneDim: "rgba(237,231,218,0.45)",
  /** ACENTO ÚNICO. Ver REGLA DEL ROJO abajo antes de usarlo. */
  red: "#E5322B",
  gridLine: "rgba(237,231,218,0.06)",
} as const;

/** Bone a opacidad arbitraria, para estados intermedios entre bone y boneDim. */
export const bone = (alpha: number) => `rgba(237,231,218,${alpha})`;
/** Rojo a opacidad arbitraria (glows, barridos, fondos de data-moment). */
export const red = (alpha: number) => `rgba(229,50,43,${alpha})`;

/**
 * REGLA DEL ROJO — el rojo es un bisturí, no un color de relleno.
 * Solo aparece en: momentos-villano, palabras-activación y el dato duro de M4.
 * `RED_BUDGET` documenta dónde está permitido; si aparece fuera de esta lista,
 * está mal usado.
 */
export const RED_BUDGET = [
  "M2 · palabra 'error' en la frase bisagra",
  "M3 · el tope de la curva de CRITERIO",
  "M4 · movimiento completo (villano + dato duro)",
] as const;

// ═══ GRADIENTE DE MARCA ══════════════════════════════════════════════════════

/** Ángulo canónico. Todo barrido, split y gradiente usa este mismo ángulo. */
export const BRAND_ANGLE_DEG = 135;

/**
 * El borde perpendicular al gradiente cruza el frame a 45° (arriba-derecha →
 * abajo-izquierda): por cada píxel horizontal, uno vertical.
 *
 * En 9:16 el lado corto es el ancho, así que la recta se parametriza por dónde
 * corta el borde IZQUIERDO y se desplaza `DIAGONAL_DY` = ancho del frame entre
 * un borde lateral y el otro. Esto convierte el "split diagonal" en un corte
 * arriba/abajo con filo a 45°, que es la lectura correcta en vertical.
 */
export const DIAGONAL_DY = 1080;

/** Uso escaso: cierres de movimiento y fondo de data-moment. */
export const brandGradient = (from = COLORS.red, to = COLORS.bgDeep) =>
  `linear-gradient(${BRAND_ANGLE_DEG}deg, ${from} 0%, ${to} 100%)`;

// ═══ SPRINGS ═════════════════════════════════════════════════════════════════

/**
 * Todos sobreamortiguados a propósito: la voz del episodio es calculada, no
 * juguetona. `damping: 200` está muy por encima del amortiguamiento crítico
 * de cada combinación stiffness/mass, así que ninguno rebota. La velocidad se
 * regula con `stiffness`, nunca bajando el damping.
 */
export const SPRING = {
  /** Entrada estándar de texto. */
  dry: { damping: 200, stiffness: 200, mass: 1 },
  /** Bloques grandes, push-ins, cosas con peso. */
  heavy: { damping: 200, stiffness: 90, mass: 1.2 },
  /** Impacto seco: llega rápido y se apoya. Para las muescas de M2. */
  hit: { damping: 200, stiffness: 420, mass: 0.7 },
} as const;

// ═══ CURVAS ══════════════════════════════════════════════════════════════════

export const EASE = {
  /** Expo-out: arranca fuerte y frena largo. La curva por defecto. */
  out: Easing.bezier(0.16, 1, 0.3, 1),
  /** Simétrica, para barridos que cruzan el frame. */
  inOut: Easing.bezier(0.65, 0, 0.35, 1),
  /** Entrada dura: para cosas que se van del frame (expulsión de M4). */
  in: Easing.bezier(0.7, 0, 0.84, 0),
} as const;

// ═══ ESCALA TIPOGRÁFICA ══════════════════════════════════════════════════════

/**
 * Escala tipográfica para 9:16 (1080×1920), calibrada para un teléfono.
 *
 * Estos valores son TECHOS, no tamaños fijos: <KineticText> mide cada frase
 * con fitText y la agranda hasta llenar el ancho útil, frenando acá. Así el
 * texto siempre entra lo más grande posible sin desbordar, sin tener que
 * ajustar el cuerpo a mano cada vez que cambia una palabra del copy.
 */
export const TYPE = {
  hero: 148, // el golpe central de M2 y el remate de M5
  h1: 124, // headline de movimiento
  h2: 82, // subtítulo / cierre conceptual
  body: 52, // cuerpo, filas de tabla, preguntas
  label: 30, // etiquetas de eje, kickers
  data: 330, // el número duro de M4
} as const;

/** Ancho útil: 1080 menos la zona segura a cada lado. */
export const CONTENT_W = 912;

/**
 * Anclas verticales del frame de 1920.
 *
 * Centrar todo deja los tercios de arriba y abajo vacíos y el episodio se ve
 * chico. Cada escena elige a qué ancla cuelga su contenido, y las escenas de
 * varias partes reparten entre `high` y `low` para que el ojo recorra el alto.
 */
export const ZONE = {
  top: 232,
  high: 520,
  center: 960,
  low: 1400,
  bottom: 1688,
} as const;

/** Tracking negativo en los headlines: Archivo Black respira mejor apretada. */
export const TRACKING = {
  display: "-0.03em",
  body: "0em",
  label: "0.18em",
} as const;
