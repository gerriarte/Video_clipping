/**
 * Todas las capas, en el orden en que se pisan.
 *
 * Se dibuja DESPUÉS del video en cualquiera de las ramas de layout de
 * ClipComposition (fill / fit / letterbox / split / seguir la toma), así que no
 * le importa cómo se esté recortando abajo.
 *
 * Si no hay nada prendido devuelve null: un clip sin capas tiene que costar
 * exactamente lo que costaba antes.
 */
import React from "react";
import type { Overlays } from "./types";
import { HookTitle } from "./HookTitle";
import { LowerThird } from "./LowerThird";

export const OverlayLayer: React.FC<{
  overlays?: Overlays;
  /** El título del clip, que el gancho usa si no le escribieron otro texto. */
  fallbackText?: string;
}> = ({ overlays, fallbackText = "" }) => {
  if (!overlays) return null;
  const { hook, lower } = overlays;
  if (!hook?.on && !lower?.on) return null;

  return (
    <>
      {lower?.on && <LowerThird lower={lower} />}
      {hook?.on && <HookTitle hook={hook} fallbackText={fallbackText} />}
    </>
  );
};

export type { Overlays } from "./types";
