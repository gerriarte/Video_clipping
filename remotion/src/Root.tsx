import React from "react";
import { Composition, staticFile } from "remotion";
import { getVideoMetadata } from "@remotion/media-utils";
import { ClipComposition, ClipCompositionProps } from "./ClipComposition";
import { ColdOpen, COLD_OPEN_DURATION, COLD_OPEN_FPS } from "./ColdOpen";
import { CierreOutro, CIERRE_DURATION, CIERRE_FPS } from "./CierreOutro";
import { Criterio } from "./criterio/Criterio";
import { criterioSchema, criterioDefaults } from "./criterio/schema";
import { DURATION, FPS, HEIGHT, WIDTH } from "./criterio/timing";

export const Root: React.FC = () => {
  // Solo para el preview en Remotion Studio: el render desde Python siempre
  // manda sus propios props (ver modules/renderer.py). public/preview.mp4 es un
  // clip local (gitignorado); si falta, la composición muestra un placeholder.
  const defaultProps: ClipCompositionProps = {
    clipPath:    staticFile("preview.mp4"),
    title:       "",
    width:       1080,
    height:      1920,
    fps:         30,
    layout:      "fit",
    focusX:      0.5,
    focusTop:    0.5,
    focusBottom: 0.5,
  };

  return (
    <>
      {/* Episodio editorial de 5 min. Todo el copy es editable desde el panel
          de props: ver src/criterio/schema.ts. */}
      <Composition
        id="Criterio"
        component={Criterio}
        durationInFrames={DURATION}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        schema={criterioSchema}
        defaultProps={criterioDefaults}
      />

      <Composition
        id="ColdOpen"
        component={ColdOpen}
        durationInFrames={COLD_OPEN_DURATION}
        fps={COLD_OPEN_FPS}
        width={1920}
        height={1080}
      />

      <Composition
        id="CierreOutro"
        component={CierreOutro}
        durationInFrames={CIERRE_DURATION}
        fps={CIERRE_FPS}
        width={1920}
        height={1080}
      />

      <Composition
        id="ClipComposition"
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        component={ClipComposition as React.ComponentType<any>}
        defaultProps={defaultProps}
        calculateMetadata={async ({ props }) => {
          const p = props as unknown as ClipCompositionProps;

          // Cuando viene desde Python ya trae durationInFrames calculado —
          // evita que Chromium intente cargar el video antes de renderizar.
          if (typeof p.durationInFrames === "number" && p.durationInFrames > 0) {
            return { durationInFrames: p.durationInFrames };
          }

          // Fallback para Remotion Studio (preview interactivo)
          if (!p.clipPath) return { durationInFrames: 900 };
          const meta = await getVideoMetadata(p.clipPath as string);
          return {
            durationInFrames: Math.ceil(
              meta.durationInSeconds * ((p.fps as number) ?? 30)
            ),
          };
        }}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};
