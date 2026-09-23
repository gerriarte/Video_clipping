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

export interface Overlays {
  hook?: HookOverlay;
  lower?: LowerThirdOverlay;
}

/** Lo que se dibuja si el clip no trae nada: nada. */
export const NO_OVERLAYS: Overlays = {};
