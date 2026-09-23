/**
 * Contrato de las capas que van encima del clip.
 *
 * Van como overlay, no como placas concatenadas: un clip de 60 s no puede
 * regalar segundos a una cortina, y el enganche se juega en los primeros dos.
 * Por eso todo esto se dibuja ENCIMA del video, sin alargarlo.
 *
 * Los tiempos van en segundos (es lo que edita una persona); la conversión a
 * frames la hace cada componente con el fps de la composición.
 */

/** Cómo entra el texto del gancho. */
export type HookStyle = "pop" | "slide" | "type";

/** Dónde vive la capa en el alto del lienzo. */
export type VPosition = "top" | "center" | "bottom";

export interface HookOverlay {
  on: boolean;
  /** El texto. Vacío = se usa el título del clip. */
  text: string;
  style: HookStyle;
  position: VPosition;
  /** Segundo en que aparece, contado desde el inicio del clip. */
  start: number;
  /** Cuánto se queda en pantalla, en segundos. */
  dur: number;
}

export interface LowerThirdOverlay {
  on: boolean;
  name: string;
  role: string;
  start: number;
  dur: number;
  /** De qué lado entra y se apoya. */
  side: "left" | "right";
}

/** La placa de apertura o la de cierre. */
export interface CardOverlay {
  on: boolean;
  title: string;
  subtitle: string;
  /** Cuánto dura. La de intro cuenta desde el principio; la de cierre, hasta el final. */
  dur: number;
  /**
   * Cuánto se oscurece el video detrás (0 = nada, 1 = negro).
   *
   * No es una placa opaca por default a propósito: el movimiento de atrás es lo
   * que sostiene la atención mientras se lee. Con 1 se consigue la placa de
   * toda la vida, si se la quiere.
   */
  dim: number;
}

export interface Overlays {
  hook?: HookOverlay;
  lower?: LowerThirdOverlay;
  intro?: CardOverlay;
  outro?: CardOverlay;
}

/** Lo que se dibuja si el clip no trae nada: nada. */
export const NO_OVERLAYS: Overlays = {};
