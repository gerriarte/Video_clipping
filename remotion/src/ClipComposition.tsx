import React from "react";
import {
  AbsoluteFill,
  Audio,
  useCurrentFrame,
  interpolate,
} from "remotion";
// `Video` de @remotion/media reemplaza a OffthreadVideo, que quedó como legado.
// El motivo es velocidad, NO calidad: los dos entregan exactamente la misma
// definición (18.4 vs 18.5 de varianza del Laplaciano sobre el mismo frame),
// pero éste rinde ~37% mejor (7.0 s contra 11.2 s en el mismo render de prueba).
//
// Ojo al migrar: `Video` dibuja en un <canvas>, así que el `objectFit` del CSS
// NO le aplica — va como prop — y no existe `object-position`. El recorte
// horizontal se hace moviendo un contenedor (ver `CoveredVideo`).
import { Video } from "@remotion/media";
import { OverlayLayer } from "./overlays/OverlayLayer";
import type { Overlays } from "./overlays/types";

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
  /** Aspecto (ancho/alto) del video fuente. Hace falta para calcular el recorte
   *  horizontal a mano: el <Video> de @remotion/media dibuja en canvas y no
   *  tiene `object-position`, así que ya no lo resuelve el CSS. 16:9 por defecto. */
  sourceAspect?:    number;
  /** Capas encima del video (gancho, placa de nombre). Ver overlays/types.ts.
   *  Sin esto el clip se renderiza exactamente como antes. */
  overlays?:        Overlays;
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
  /** Trayectoria de la cámara DENTRO de este tramo (tiempo del clip, igual que
   *  `focusKeyframes` global). Con esto, seguir la toma no apaga el seguimiento
   *  del hablante: lo mantiene adentro de cada plano cerrado. Si falta, el
   *  tramo usa `focusX` fijo. */
  focusKeyframes?: FocusKeyframe[];
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
      <Video
        src={src}
        muted={muted}
        // "fill" = estirar a la caja, que es lo que hacía el <img> de antes (su
        // object-fit por defecto). La caja ya lleva el aspecto correcto metido
        // en el rectángulo, así que estirar no deforma.
        objectFit="fill"
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

/** Emula `object-fit: cover` + `object-position: X%` sin usar CSS.
 *
 *  El <Video> de @remotion/media dibuja en un canvas: el `object-fit` del CSS no
 *  le aplica (por eso el componente expone `objectFit` como prop) y no hay
 *  equivalente de `object-position`. Como el recorte que sigue al hablante ES un
 *  desplazamiento horizontal, lo resolvemos moviendo un contenedor interno del
 *  ancho del video "cubriendo" — la misma técnica que ya usa `CroppedVideo`.
 *
 *  `visible` es la fracción del ancho de la fuente que entra en el contenedor. */
const CoveredVideo: React.FC<{
  src:             string;
  posX:            number;
  containerAspect: number;
  sourceAspect:    number;
  muted?:          boolean;
}> = ({ src, posX, containerAspect, sourceAspect, muted }) => {
  const visible  = Math.min(1, containerAspect / sourceAspect);
  const widthPct = 100 / visible;
  const leftPct  = -(widthPct - 100) * posX;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          top:      0,
          height:   "100%",
          width:    `${widthPct.toFixed(4)}%`,
          left:     `${leftPct.toFixed(4)}%`,
        }}
      >
        <Video
          src={src}
          muted={muted}
          objectFit="cover"
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
};

/** Los píxeles: un layout sobre el lienzo. `muted` cuando el audio lo pone
 *  aparte un <Audio> (modo "seguir la toma": el video se remonta en cada cambio
 *  de layout y el sonido no puede depender de eso). */
const ClipVisual: React.FC<{
  src:            string;
  layout:         "fill" | "fit" | "letterbox" | "split";
  posX:           number;
  focusTop:       number;
  focusBottom:    number;
  canvasAspect:   number;
  sourceAspect:   number;
  muted?:         boolean;
}> = ({ src, layout, posX, focusTop, focusBottom, canvasAspect, sourceAspect, muted }) => (
  <AbsoluteFill style={{ background: "#000" }}>
    {layout === "fill" ? (
      /* TALKING HEAD: recorte que llena toda la pantalla, centrado en quien
         habla; posX se mueve suave entre hablantes según los keyframes. */
      <AbsoluteFill>
        <CoveredVideo
          src={src}
          muted={muted}
          posX={posX}
          containerAspect={canvasAspect}
          sourceAspect={sourceAspect}
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
        <Video
          src={src}
          muted={muted}
          objectFit="contain"
          style={{ width: "100%", height: "100%" }}
        />
      </AbsoluteFill>
    ) : layout === "split" ? (
      /* DOS HOSTS: dos recortes del mismo video apilados. La mitad superior
         se centra en focusTop y la inferior en focusBottom. El audio del clip
         es idéntico en ambos videos: muteamos el de abajo para no duplicarlo. */
      <AbsoluteFill>
        {/* Cada mitad es un contenedor de la MITAD de alto: su aspecto es el
            doble de ancho que el del lienzo entero. */}
        <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "50%", overflow: "hidden" }}>
          <CoveredVideo
            src={src}
            muted={muted}
            posX={focusTop}
            containerAspect={canvasAspect * 2}
            sourceAspect={sourceAspect}
          />
        </div>
        <div style={{ position: "absolute", top: "50%", left: 0, width: "100%", height: "50%", overflow: "hidden" }}>
          <CoveredVideo
            src={src}
            muted
            posX={focusBottom}
            containerAspect={canvasAspect * 2}
            sourceAspect={sourceAspect}
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
          <Video
            src={src}
            muted
            objectFit="cover"
            style={{
              width:     "100%",
              height:    "100%",
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
          <Video
            src={src}
            muted={muted}
            objectFit="contain"
            style={{ width: "100%", height: "100%" }}
          />
        </AbsoluteFill>
      </>
    )}
  </AbsoluteFill>
);

const ClipBody: React.FC<ClipCompositionProps> = ({
  clipPath,
  fps,
  layout = "fit",
  focusX = 0.5,
  focusKeyframes = [],
  focusTop = 0.5,
  focusBottom = 0.5,
  manualCrops,
  layoutSegments,
  width,
  height,
  sourceAspect = 16 / 9,
}) => {
  // Posición horizontal del recorte en este frame (cámara que sigue al hablante).
  const frame = useCurrentFrame();
  const posX  = focusAt(frame / fps, focusKeyframes, focusX);

  // Aspecto del lienzo de salida: `CoveredVideo` lo necesita para calcular qué
  // franja de la fuente entra en pantalla (antes lo resolvía el CSS con cover).
  const canvasAspect = width / height;

  // Sin clip: <Video> lanza "No src passed". Pasa al abrir la composición
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
          // El tramo manda: si trae su propia trayectoria, la cámara sigue al
          // hablante adentro del plano; si no, foco fijo (los tramos "split"
          // nunca traen: ahí cada mitad ya tiene su propio foco).
          posX={focusAt(frame / fps, seg.focusKeyframes ?? [], seg.focusX ?? focusX)}
          focusTop={seg.focusTop ?? focusTop}
          focusBottom={seg.focusBottom ?? focusBottom}
          canvasAspect={canvasAspect}
          sourceAspect={sourceAspect}
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
      canvasAspect={canvasAspect}
      sourceAspect={sourceAspect}
    />
  );
};


/**
 * El clip, con sus capas encima.
 *
 * `ClipBody` resuelve el video y el recorte (y tiene varias ramas: fill, fit,
 * letterbox, split, seguir la toma). Las capas se dibujan después, una sola
 * vez, para no repetirlas en cada rama — y para que agregar una capa nueva no
 * obligue a tocar la lógica de recorte.
 */
export const ClipComposition: React.FC<ClipCompositionProps> = (props) => (
  <>
    <ClipBody {...props} />
    <OverlayLayer overlays={props.overlays} fallbackText={props.title} />
  </>
);
