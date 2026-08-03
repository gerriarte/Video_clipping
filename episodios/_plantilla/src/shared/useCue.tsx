import React, { createContext, useContext } from 'react';
import { CUE_FRAMES, type CueId } from './cues';

export { CAPTIONS } from './captions';
export type { Caption } from './captions';

/**
 * Frame absoluto en que arranca el bloque que se está renderizando.
 *
 * Hace falta porque los cues se resuelven contra el audio del episodio
 * completo (frames absolutos) pero adentro de una <Series.Sequence> el
 * frame vuelve a cero. Sin esto, el cue del C5 le pediría al bloque un
 * frame 7000 que ahí adentro no existe y el visual no aparecía nunca.
 */
const CueOrigin = createContext(0);

export const CueScope: React.FC<{ start: number; children: React.ReactNode }> = ({
  start,
  children,
}) => <CueOrigin.Provider value={start}>{children}</CueOrigin.Provider>;

/**
 * Frame —relativo al bloque— en que se pronuncia el cue `id`.
 *
 * La verdad la manda el audio: al regrabar el VO y retranscribir, todo se
 * reacomoda solo sin tocar lógica de animación. El `fallback` solo entra si
 * el id no está en la tabla de `cues.ts` (que TypeScript ya no deja pasar).
 *
 * @param id        id de `CUE_SCRIPT`
 * @param fallback  frame relativo de respaldo
 * @param offset    corrimiento manual en frames, para anticipar el visual
 */
export const useCue = (id: CueId, fallback: number, offset = 0): number => {
  const origin = useContext(CueOrigin);
  const abs = CUE_FRAMES[id];
  if (abs === undefined) return fallback + offset;
  return abs - origin + offset;
};
