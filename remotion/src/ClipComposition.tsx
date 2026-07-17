import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  useCurrentFrame,
  interpolate,
} from "remotion";

/** Keyframe de la "cámara" que sigue al hablante.
 *  t = segundos en la línea de tiempo del archivo de clip; x = objectPosition X (0–1). */
export interface FocusKeyframe {
  t: number;
  x: number;
}

export interface ClipCompositionProps {
  clipPath:         string;
  title:            string;
  width:            number;
  height:           number;
  fps:              number;
  durationInFrames?: number;
  /** "fill"  = recorta para llenar la pantalla (talking head).
   *  "fit"   = muestra el plano completo 16:9 sobre fondo borroso (pantalla compartida).
   *  "split" = dos recortes del mismo video apilados (un host arriba, otro abajo). */
  layout?:          "fill" | "fit" | "split";
  /** objectPosition X fijo del recorte en modo "fill" (0 = izq, 1 = der).
   *  Fallback cuando no hay keyframes dinámicos. */
  focusX?:          number;
  /** Trayectoria de la "cámara" que sigue a quien habla. Si tiene 2+ puntos,
   *  el recorte se desplaza suavemente entre hablantes; si no, usa focusX fijo. */
  focusKeyframes?:  FocusKeyframe[];
  /** Modo "split": objectPosition X (0–1) de la mitad superior e inferior. */
  focusTop?:        number;
  focusBottom?:     number;
  /** Recorte manual por rectángulo (fracciones 0–1 de la fuente): {x,y,w,h}.
   *  1 rect → recorte único a toda la pantalla; 2 rects → split (arriba/abajo).
   *  Cuando está presente tiene prioridad sobre layout/focus (permite zoom). */
  manualCrops?:     CropRect[];
}

export interface CropRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Muestra un rectángulo `crop` (fracciones de la fuente) llenando su contenedor.
 *  Escala y desplaza el video para que el sub-rectángulo cubra exactamente el
 *  contenedor: permite recortes más cerrados (zoom) manteniendo el aspecto. */
const CroppedVideo: React.FC<{ src: string; crop: CropRect; muted?: boolean }> = ({
  src,
  crop,
  muted,
}) => {
  const { x, y, w, h } = crop;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <OffthreadVideo
        src={src}
        muted={muted}
        style={{
          position: "absolute",
          width:    `${(100 / w).toFixed(4)}%`,
          height:   `${(100 / h).toFixed(4)}%`,
          left:     `${(-x / w * 100).toFixed(4)}%`,
          top:      `${(-y / h * 100).toFixed(4)}%`,
          maxWidth: "none",
        }}
      />
    </div>
  );
};

/** Evalúa la trayectoria de foco en el tiempo `t` (seg). Interpolación lineal
 *  entre keyframes (ya vienen suavizados desde Python); fuera de rango, clamp. */
const focusAt = (t: number, keyframes: FocusKeyframe[], fallback: number): number => {
  if (!keyframes || keyframes.length === 0) return fallback;
  if (keyframes.length === 1) return keyframes[0].x;
  return interpolate(
    t,
    keyframes.map((k) => k.t),
    keyframes.map((k) => k.x),
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
};

export const ClipComposition: React.FC<ClipCompositionProps> = ({
  clipPath,
  fps,
  layout = "fit",
  focusX = 0.5,
  focusKeyframes = [],
  focusTop = 0.5,
  focusBottom = 0.5,
  manualCrops,
}) => {
  // Posición horizontal del recorte en este frame (cámara que sigue al hablante).
  const frame = useCurrentFrame();
  const posX  = focusAt(frame / fps, focusKeyframes, focusX);

  // ── Recorte manual (con zoom): tiene prioridad sobre layout/focus ───────────
  if (manualCrops && manualCrops.length > 0) {
    if (manualCrops.length >= 2) {
      // Split manual: dos recortes apilados (audio del de abajo muteado).
      return (
        <AbsoluteFill style={{ background: "#000" }}>
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "50%", overflow: "hidden" }}>
            <CroppedVideo src={clipPath} crop={manualCrops[0]} />
          </div>
          <div style={{ position: "absolute", top: "50%", left: 0, width: "100%", height: "50%", overflow: "hidden" }}>
            <CroppedVideo src={clipPath} crop={manualCrops[1]} muted />
          </div>
          <div
            style={{
              position: "absolute", top: "50%", left: 0, width: "100%", height: 2,
              transform: "translateY(-1px)", background: "rgba(0,0,0,0.65)",
            }}
          />
        </AbsoluteFill>
      );
    }
    return (
      <AbsoluteFill style={{ background: "#000" }}>
        <CroppedVideo src={clipPath} crop={manualCrops[0]} />
      </AbsoluteFill>
    );
  }

  // Sin fade in/out a negro: así el primer frame ya muestra contenido y el
  // thumbnail en el grid de redes no queda en pantalla negra.
  return (
    <AbsoluteFill style={{ background: "#000" }}>

      {layout === "fill" ? (
        /* TALKING HEAD: recorte que llena toda la pantalla.
           objectFit cover + objectPosition centra el recorte en quien habla;
           posX se mueve suave entre hablantes según los keyframes. */
        <AbsoluteFill>
          <OffthreadVideo
            src={clipPath}
            style={{
              width:          "100%",
              height:         "100%",
              objectFit:      "cover",
              objectPosition: `${(posX * 100).toFixed(2)}% 50%`,
            }}
          />
        </AbsoluteFill>
      ) : layout === "split" ? (
        /* DOS HOSTS: dos recortes del mismo video apilados. La mitad superior
           se centra en focusTop y la inferior en focusBottom. El audio del clip
           es idéntico en ambos videos: muteamos el de abajo para no duplicarlo. */
        <AbsoluteFill>
          <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "50%", overflow: "hidden" }}>
            <OffthreadVideo
              src={clipPath}
              style={{
                width:          "100%",
                height:         "100%",
                objectFit:      "cover",
                objectPosition: `${(focusTop * 100).toFixed(2)}% 50%`,
              }}
            />
          </div>
          <div style={{ position: "absolute", top: "50%", left: 0, width: "100%", height: "50%", overflow: "hidden" }}>
            <OffthreadVideo
              src={clipPath}
              muted
              style={{
                width:          "100%",
                height:         "100%",
                objectFit:      "cover",
                objectPosition: `${(focusBottom * 100).toFixed(2)}% 50%`,
              }}
            />
          </div>
          {/* Costura sutil entre las dos mitades. */}
          <div
            style={{
              position:  "absolute",
              top:       "50%",
              left:      0,
              width:     "100%",
              height:    2,
              transform: "translateY(-1px)",
              background: "rgba(0,0,0,0.65)",
            }}
          />
        </AbsoluteFill>
      ) : (
        /* PANTALLA COMPARTIDA: plano completo 16:9 a todo el ancho (máximo
           detalle sin perder contenido) sobre fondo borroso que llena la pantalla. */
        <>
          <AbsoluteFill>
            <OffthreadVideo
              src={clipPath}
              muted
              style={{
                width:     "100%",
                height:    "100%",
                objectFit: "cover",
                filter:    "blur(18px) brightness(0.35) saturate(1.3)",
                transform: "scale(1.08)",
              }}
            />
          </AbsoluteFill>

          <AbsoluteFill
            style={{
              display:        "flex",
              alignItems:     "center",
              justifyContent: "center",
            }}
          >
            <OffthreadVideo
              src={clipPath}
              style={{
                width:       "100%",
                aspectRatio: "16 / 9",
                objectFit:   "contain",
              }}
            />
          </AbsoluteFill>
        </>
      )}

    </AbsoluteFill>
  );
};
