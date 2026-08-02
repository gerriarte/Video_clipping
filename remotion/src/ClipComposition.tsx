import React from "react";
import {
  AbsoluteFill,
  Audio,
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
  /** "fill"      = recorta para llenar la pantalla (talking head).
   *  "fit"       = plano completo 16:9 sobre fondo borroso (pantalla compartida).
   *  "letterbox" = plano completo 16:9 centrado sobre NEGRO (barras arriba y abajo).
   *  "split"     = dos recortes del mismo video apilados (un host arriba, otro abajo). */
  layout?:          "fill" | "fit" | "letterbox" | "split";
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
  /** Recorte que SIGUE LA TOMA: el layout cambia dentro del clip (split mientras
   *  están los dos, recorte cerrado cuando la cámara va a uno). Las dimensiones
   *  no cambian nunca — lo que cambia es cómo se recorta el mismo lienzo.
   *  Ordenados por `fromFrame`; el primero tiene que arrancar en 0. */
  layoutSegments?:  LayoutSegment[];
}

export interface LayoutSegment {
  fromFrame:    number;
  layout:       "fill" | "fit" | "letterbox" | "split";
  focusX?:      number;
  focusTop?:    number;
  focusBottom?: number;
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

/** Tramo de layout vigente en el frame `frame`. */
export const segmentAt = (
  segments: LayoutSegment[],
  frame: number
): LayoutSegment => {
  let current = segments[0];
  for (const s of segments) {
    if (s.fromFrame <= frame) current = s;
    else break;
  }
  return current;
};

/** Los píxeles: un layout sobre el lienzo. `muted` cuando el audio lo pone
 *  aparte un <Audio> (modo "seguir la toma": el video se remonta en cada cambio
 *  de layout y el sonido no puede depender de eso). */
const ClipVisual: React.FC<{
  src:          string;
  layout:       "fill" | "fit" | "letterbox" | "split";
  posX:         number;
  focusTop:     number;
  focusBottom:  number;
  muted?:       boolean;
}> = ({ src, layout, posX, focusTop, focusBottom, muted }) => (
  <AbsoluteFill style={{ background: "#000" }}>
    {layout === "fill" ? (
      /* TALKING HEAD: recorte que llena toda la pantalla.
         objectFit cover + objectPosition centra el recorte en quien habla;
         posX se mueve suave entre hablantes según los keyframes. */
      <AbsoluteFill>
        <OffthreadVideo
          src={src}
          muted={muted}
          style={{
            width:          "100%",
            height:         "100%",
            objectFit:      "cover",
            objectPosition: `${(posX * 100).toFixed(2)}% 50%`,
          }}
        />
      </AbsoluteFill>
    ) : layout === "letterbox" ? (
      /* PLANO COMPLETO SOBRE NEGRO: el 16:9 entero centrado, con barras arriba
         y abajo. No se pierde nada de la imagen y no hay fondo que distraiga
         (a diferencia de "fit", que rellena con el mismo video borroso). */
      <AbsoluteFill
        style={{
          display:        "flex",
          alignItems:     "center",
          justifyContent: "center",
          background:     "#000",
        }}
      >
        <OffthreadVideo
          src={src}
          muted={muted}
          style={{
            width:       "100%",
            aspectRatio: "16 / 9",
            objectFit:   "contain",
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
            src={src}
            muted={muted}
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
            src={src}
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
            src={src}
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
            src={src}
            muted={muted}
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

export const ClipComposition: React.FC<ClipCompositionProps> = ({
  clipPath,
  fps,
  layout = "fit",
  focusX = 0.5,
  focusKeyframes = [],
  focusTop = 0.5,
  focusBottom = 0.5,
  manualCrops,
  layoutSegments,
}) => {
  // Posición horizontal del recorte en este frame (cámara que sigue al hablante).
  const frame = useCurrentFrame();
  const posX  = focusAt(frame / fps, focusKeyframes, focusX);

  // Sin clip: OffthreadVideo lanza "No src passed". Pasa al abrir la composición
  // en Remotion Studio sin props (el render desde Python siempre manda clipPath).
  if (!clipPath) {
    return (
      <AbsoluteFill
        style={{
          background:     "#111",
          color:          "#666",
          display:        "flex",
          alignItems:     "center",
          justifyContent: "center",
          fontFamily:     "sans-serif",
          fontSize:       48,
          textAlign:      "center",
          padding:        80,
        }}
      >
        Sin clip: define clipPath en los props
      </AbsoluteFill>
    );
  }

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

  // ── Seguir la toma: el layout cambia dentro del clip ───────────────────────
  // El audio va aparte, en un <Audio> que abarca todo el clip: los elementos de
  // video se desmontan y remontan en cada cambio de layout, y si el sonido
  // colgara de ellos se cortaría en cada corte.
  if (layoutSegments && layoutSegments.length > 0) {
    const seg = segmentAt(layoutSegments, frame);
    return (
      <>
        <ClipVisual
          src={clipPath}
          layout={seg.layout}
          posX={seg.focusX ?? focusX}
          focusTop={seg.focusTop ?? focusTop}
          focusBottom={seg.focusBottom ?? focusBottom}
          muted
        />
        <Audio src={clipPath} />
      </>
    );
  }

  // Sin fade in/out a negro: así el primer frame ya muestra contenido y el
  // thumbnail en el grid de redes no queda en pantalla negra.
  return (
    <ClipVisual
      src={clipPath}
      layout={layout}
      posX={posX}
      focusTop={focusTop}
      focusBottom={focusBottom}
    />
  );
};
