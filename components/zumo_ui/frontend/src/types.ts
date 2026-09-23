/**
 * Tipos compartidos por las pantallas de la UI de Zumo.
 *
 * Lo propio de una pantalla vive en el `types.ts` de su carpeta; acá solo entra
 * lo que usan dos o más. Sin React, sin host.
 */

/** El tema que manda el host (Streamlit lo provee; una API lo puede fijar). */
export interface Theme {
  base: "light" | "dark";
  primaryColor: string;
  backgroundColor: string;
  secondaryBackgroundColor: string;
  textColor: string;
  font: string;
}

/** Un formato de salida, con lo que la UI necesita para dibujarlo. */
export interface FormatDef {
  key: string;
  /** Nombre largo ("9:16 vertical"). */
  label: string;
  /** Nombre corto para el botón ("9:16"). */
  short: string;
  /** Si el formato recorta algo. */
  crop: boolean;
  /** Relación de aspecto de la salida (ancho/alto). */
  aspect: number;
  /** El recorte se mueve solo dentro del clip. */
  autoLayout: boolean;
}
