import React from "react";
import { Composition, staticFile } from "remotion";
import { getVideoMetadata } from "@remotion/media-utils";
import { ClipComposition, ClipCompositionProps } from "./ClipComposition";
// Solo las medidas: ColdOpen y CierreOutro se cargan con `lazyComponent` más
// abajo. Importarlos acá arrastraba sus tipografías de Google a CADA render de
// clip — 200+ requests de red por render, para dos piezas que el pipeline de
// clips no renderiza nunca (se arman a mano desde Remotion Studio).
import {
  COLD_OPEN_DURATION,
  COLD_OPEN_FPS,
  CIERRE_DURATION,
  CIERRE_FPS,
} from "./pieces.meta";

// Este proyecto es SOLO el render de clips del pipeline (ver
// config.REMOTION_DIR). Los episodios animados viven en episodios/ —
// cada uno con su propio proyecto Remotion. La composición "Criterio"
// que estaba acá era la versión sin sincronizar: quedó archivada en
// episodios/_archivo/criterio-v1/ y la reemplaza episodios/criterio/.

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
      <Composition
        id="ColdOpen"
        lazyComponent={() => import("./ColdOpen")}
        durationInFrames={COLD_OPEN_DURATION}
        fps={COLD_OPEN_FPS}
        width={1920}
        height={1080}
      />

      <Composition
        id="CierreOutro"
        lazyComponent={() => import("./CierreOutro")}
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

          // Fallback para Remotion Studio (preview interactivo).
          //
          // `public/preview.mp4` está gitignorado, así que en una copia recién
          // clonada no existe — pero `staticFile()` devuelve una ruta igual, y
          // el guard de `!p.clipPath` no lo atrapa. Contra un archivo que no
          // está, `getVideoMetadata` **no rechaza: se cuelga**, y el Studio se
          // queda para siempre en "Running calculateMetadata()…" sin decir por
          // qué. Por eso hace falta una carrera contra el reloj y no un
          // try/catch: no hay error que atrapar.
          const DURACION_DE_MUESTRA = 900; // 30 s a 30 fps
          const ESPERA_MAXIMA_MS = 4000;
          if (!p.clipPath) return { durationInFrames: DURACION_DE_MUESTRA };

          const medido = await Promise.race([
            getVideoMetadata(p.clipPath as string).catch(() => null),
            new Promise<null>((r) => setTimeout(() => r(null), ESPERA_MAXIMA_MS)),
          ]);
          if (!medido) return { durationInFrames: DURACION_DE_MUESTRA };
          return {
            durationInFrames: Math.ceil(
              medido.durationInSeconds * ((p.fps as number) ?? 30)
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
