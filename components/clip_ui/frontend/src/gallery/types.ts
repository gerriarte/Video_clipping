/**
 * Contrato de la galería de clips.
 *
 * Este archivo NO conoce a Streamlit ni al transporte: describe qué datos
 * necesita la galería y qué devuelve. El día que el host sea una API HTTP en
 * vez de un componente de Streamlit, este archivo no cambia.
 */

import type { FormatDef, Theme } from "../types";

export type { FormatDef, Theme };

/** Una foto del tramo, con su etiqueta ("arranque · 1:37"). */
export interface Thumb {
  url: string;
  label: string;
}

/** Cómo es la toma a lo largo del tramo (evidencia para elegir el formato). */
export interface Shot {
  /** Cuántas fotos se muestrearon (una cada ~3 s). */
  samples: number;
  /** Fracción del clip con dos personas en cuadro (0–1). */
  twoShot: number;
  /** Fracción con una sola persona. */
  solo: number;
  /** Fracción sin caras claras (pantalla compartida, plano abierto). */
  empty: number;
  /** El tramo alterna planos: ningún formato único le queda bien. */
  mixed: boolean;
  /** Clave del formato sugerido. */
  suggestion: string;
  /** Posición horizontal de cada cara detectada (0–1), para dibujar el recorte. */
  centersX: number[];
}

export interface Clip {
  /** Posición en la lista del backend. Es la identidad del clip. */
  id: number;
  /** Número visible del clip. Solo se usa cuando ya están cortados. */
  index: number;
  title: string;
  start: number;
  end: number;
  type: string;
  reason: string;
  /** Si entra en el corte. */
  selected: boolean;
  /** Clave del formato elegido. */
  format: string;
  speakerFollow: boolean;
  followShot: boolean;
  thumbs: Thumb[];
  /** null mientras no se analizó la toma. */
  shot: Shot | null;
  /**
   * El archivo ya cortado de este clip. Si viene, la tarjeta lo reproduce
   * entero; si no, busca el tramo dentro del video fuente. En el Paso 4 el
   * corte ya existe y puede traer jump cuts que el original no tiene.
   */
  clipUrl: string;
}

/** Lo que el host le pasa a la galería. */
export interface GalleryArgs {
  clips: Clip[];
  formats: FormatDef[];
  types: string[];
  /** URL del video fuente, para reproducir un tramo sin cortarlo. */
  videoUrl: string;
  /** Relación de aspecto del video fuente (ancho/alto). */
  sourceAspect: number;
  /**
   * Si se elige qué clips entran al corte (Paso 3). En el Paso 4 ya están
   * cortados: no hay nada que tildar y la tarjeta muestra su número.
   */
  pickable: boolean;
  /** Si se ofrece saltar al editor de timeline (solo antes de cortar). */
  showTimeline: boolean;
}

/** Lo único que la galería devuelve: el estado editable de cada clip. */
export interface ClipPatch {
  id: number;
  title: string;
  start: number;
  end: number;
  type: string;
  selected: boolean;
  format: string;
  speakerFollow: boolean;
  followShot: boolean;
}

/** Acciones que la galería no ejecuta: se las delega al host. */
export type GalleryAction = "timeline" | null;

export interface GalleryValue {
  clips: ClipPatch[];
  /** Qué clip está en foco, para que el host dibuje lo suyo al lado. */
  selected: number;
  action: GalleryAction;
  /** Cambia en cada commit para que el host distinga dos envíos iguales. */
  nonce: number;
}
