import React from "react";
import { Composition } from "remotion";
import { getVideoMetadata } from "@remotion/media-utils";
import { ClipComposition, ClipCompositionProps } from "./ClipComposition";

export const Root: React.FC = () => {
  const defaultProps: ClipCompositionProps = {
    clipPath:    "",
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
  );
};
