/**
 * Contrato de la pantalla de publicación (Paso 5).
 *
 * No conoce a Streamlit ni al transporte: describe qué necesita la pantalla y
 * qué devuelve. Ver `../bridge.ts`.
 */
import type { FormatDef } from "../types";

export interface PlatformDef {
  /** Clave dentro de `captions` ("tiktok", "instagram", "youtube"). */
  key: string;
  label: string;
}

export interface PublishClip {
  /** Posición en la lista del backend. Es la identidad del clip. */
  id: number;
  /** Número visible del clip (el que va en el nombre del archivo). */
  index: number;
  title: string;
  start: number;
  end: number;
  /** Duración real del archivo (con jump cuts ya no es end - start). */
  duration: number;
  type: string;
  reason: string;
  format: string;
  /** Relación de aspecto de la salida (ancho/alto), para dibujar el player. */
  aspect: number;
  /** Video renderizado. "" si el archivo todavía no existe. */
  videoUrl: string;
  /** Portada del render, para la miniatura de la lista. */
  coverUrl: string;
  /** Un texto por plataforma. */
  captions: Record<string, string>;
}

export interface PublishArgs {
  screen: "publish";
  clips: PublishClip[];
  formats: FormatDef[];
  platforms: PlatformDef[];
}

/** Lo único editable acá: el formato y los textos. */
export interface PublishPatch {
  id: number;
  format: string;
  captions: Record<string, string>;
}

/** Lo que la pantalla no ejecuta: se lo delega al host. */
export interface PublishAction {
  kind: "rerender";
  id: number;
}

export interface PublishValue {
  clips: PublishPatch[];
  /** Qué clip está abierto, para que el host dibuje lo suyo al lado. */
  selected: number;
  action: PublishAction | null;
  /** Cambia en cada commit para que el host distinga dos envíos iguales. */
  nonce: number;
}
