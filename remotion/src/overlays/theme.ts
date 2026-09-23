/**
 * Lo visual compartido por las capas.
 *
 * La fuente se pide con pesos y subset explícitos a propósito: `loadFont()` sin
 * argumentos se baja todos los pesos y todos los alfabetos de la familia — unas
 * 190 peticiones por render, para usar dos. Acá son dos archivos.
 */
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", {
  weights: ["700", "900"],
  subsets: ["latin"],
});

export const FONT = fontFamily;

/** El amarillo de la pieza de cierre. La misma marca que la app. */
export const ACCENT = "#FFD000";

/**
 * Margen inferior que hay que dejar libre en vertical.
 *
 * TikTok, Reels y Shorts dibujan SU interfaz encima del video: el usuario, el
 * texto y los botones se comen aproximadamente el 18% de abajo y una franja a
 * la derecha. Cualquier cosa que pongamos ahí queda tapada.
 */
export const SAFE_BOTTOM = 0.18;

/** Margen superior libre (el botón de cerrar y el buscador de las apps). */
export const SAFE_TOP = 0.10;

/** Una sombra que hace legible el texto blanco sobre cualquier imagen. */
export const TEXT_SHADOW =
  "0 2px 12px rgba(0,0,0,.65), 0 1px 3px rgba(0,0,0,.85)";

/**
 * Entrada y salida en el borde de la capa.
 *
 * Devuelve 0 fuera de la ventana, sube a 1 al entrar y vuelve a 0 al salir, con
 * un tramo estable en el medio. Es lo que evita que una capa aparezca y
 * desaparezca de golpe.
 */
export function envelope(
  frame: number,
  fromFrame: number,
  durFrames: number,
  fadeFrames: number,
): number {
  const t = frame - fromFrame;
  if (t < 0 || t > durFrames) return 0;
  const fade = Math.max(1, Math.min(fadeFrames, Math.floor(durFrames / 2)));
  if (t < fade) return t / fade;
  if (t > durFrames - fade) return (durFrames - t) / fade;
  return 1;
}

/** Suavizado de la entrada: rápido al principio, frena al final. */
export const easeOut = (x: number): number => 1 - Math.pow(1 - x, 3);
