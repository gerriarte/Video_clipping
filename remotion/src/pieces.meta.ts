/**
 * Duración y fps del cold open y del cierre.
 *
 * Viven acá y no en sus componentes para que `Root.tsx` pueda registrarlos sin
 * importar los componentes: ColdOpen y CierreOutro cargan tipografías de Google
 * al evaluarse, y esas descargas corrían en CADA render de clip aunque
 * ClipComposition no use texto. Con las medidas separadas, Root los puede
 * declarar con `lazyComponent` y el clip ya no paga por ellas.
 */

export const COLD_OPEN_DURATION = 105;
export const COLD_OPEN_FPS = 30;

export const CIERRE_DURATION = 240;
export const CIERRE_FPS = 30;
