/**
 * Primitivas de movimiento de "Criterio".
 *
 * Reglas que estas primitivas hacen cumplir por construcción:
 *  · Todo se anima con useCurrentFrame + interpolate/spring. Nada de CSS
 *    transitions ni animations.
 *  · Todo interpolate va con extrapolateLeft/Right "clamp": los cortes tienen
 *    que ser limpios, nunca un valor que sigue corriendo fuera de su rango.
 *  · El texto entra por máscara vertical o por blur→focus. No hay fade genérico.
 */
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  BRAND_ANGLE_DEG,
  COLORS,
  DIAGONAL_DY,
  EASE,
  FONT,
  SPRING,
  TRACKING,
  TYPE,
  bone,
} from "./theme";
import { HEIGHT, WIDTH } from "./timing";

// ═══ HELPERS ═════════════════════════════════════════════════════════════════

export interface Span {
  from: number;
  to: number;
}

/** interpolate con clamp en ambos extremos. El 99% de los usos del episodio. */
export const ramp = (
  frame: number,
  { from, to }: Span,
  outRange: [number, number] = [0, 1],
  easing = EASE.out
) =>
  interpolate(frame, [from, to], outRange, {
    easing,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

/** Spring sobreamortiguado que arranca en `delay`. Devuelve 0→1. */
export const useDamped = (
  delay: number,
  config: (typeof SPRING)[keyof typeof SPRING] = SPRING.dry
) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config });
};

/**
 * Geometría del corte a 45°, en formato vertical.
 *
 * La recta baja hacia la izquierda: corta el borde izquierdo en `yLeft` y el
 * derecho en `yLeft - DIAGONAL_DY`. `diagonalClipTop` devuelve la región de
 * ARRIBA de esa recta; `diagonalClipBottom`, la de abajo.
 */
export const diagonalClipTop = (yLeft: number) =>
  `polygon(0px 0px, ${WIDTH}px 0px, ${WIDTH}px ${yLeft - DIAGONAL_DY}px, 0px ${yLeft}px)`;

export const diagonalClipBottom = (yLeft: number) =>
  `polygon(0px ${yLeft}px, ${WIDTH}px ${yLeft - DIAGONAL_DY}px, ${WIDTH}px ${HEIGHT}px, 0px ${HEIGHT}px)`;

/** El split fijo de M1: la recta pasa por el centro del frame. */
export const SPLIT_Y_LEFT = (HEIGHT + DIAGONAL_DY) / 2; // 1500
export const SPLIT_Y_RIGHT = SPLIT_Y_LEFT - DIAGONAL_DY; // 420

export const SPLIT_TOP = diagonalClipTop(SPLIT_Y_LEFT);
export const SPLIT_BOTTOM = diagonalClipBottom(SPLIT_Y_LEFT);

// ═══ FONDO ═══════════════════════════════════════════════════════════════════

/** Grano: el fondo near-black se ve plano sin esto. */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.05 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // El grano hierve a ~15 Hz sin importar el fps. Atado al frame directamente,
  // a 60 fps herviría al doble y se leería como ruido de video, no como grano.
  const seed = Math.floor(frame / Math.max(1, Math.round(fps / 15))) % 12;
  const id = `grain-${seed}`;
  return (
    <AbsoluteFill style={{ opacity, mixBlendMode: "screen", pointerEvents: "none" }}>
      <svg width={WIDTH} height={HEIGHT}>
        <filter id={id}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={seed} />
        </filter>
        <rect width={WIDTH} height={HEIGHT} filter={`url(#${id})`} />
      </svg>
    </AbsoluteFill>
  );
};

/**
 * Viñeteado: hunde los bordes hacia bgDeep para que el centro respire.
 * Va DETRÁS del contenido — encima le comía los extremos a los headlines que
 * cruzan todo el ancho, que es justo lo que hacen los de este episodio.
 * Además arranca a mitad de radio, para que la caída sea solo en el borde.
 */
export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.9 }) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(ellipse 78% 70% at 50% 48%, transparent 45%, ${COLORS.bgDeep} 100%)`,
      opacity: strength,
      pointerEvents: "none",
    }}
  />
);

/** Retícula de fondo. Casi invisible: solo evita que el negro sea un vacío. */
export const GridBackdrop: React.FC<{
  opacity?: number;
  step?: number;
  stroke?: string;
}> = ({ opacity = 1, step = 120, stroke = COLORS.gridLine }) => {
  const cols = [];
  for (let x = step; x < WIDTH; x += step) cols.push(x);
  const rows = [];
  for (let y = step; y < HEIGHT; y += step) rows.push(y);
  return (
    <AbsoluteFill style={{ opacity, pointerEvents: "none" }}>
      <svg width={WIDTH} height={HEIGHT}>
        {cols.map((x) => (
          <line key={`c${x}`} x1={x} y1={0} x2={x} y2={HEIGHT} stroke={stroke} strokeWidth={1} />
        ))}
        {rows.map((y) => (
          <line key={`r${y}`} x1={0} y1={y} x2={WIDTH} y2={y} stroke={stroke} strokeWidth={1} />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

/** El fondo base de todo movimiento. Se monta una vez por Sequence. */
export const Backdrop: React.FC<{
  grid?: boolean;
  /** 0 = bg plano · 1 = gradiente de marca a pleno. Uso escaso (M4). */
  brandMix?: number;
  children?: React.ReactNode;
}> = ({ grid = true, brandMix = 0, children }) => (
  <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
    {brandMix > 0 ? (
      <AbsoluteFill
        style={{
          background: `linear-gradient(${BRAND_ANGLE_DEG}deg, rgba(229,50,43,0.55) 0%, ${COLORS.bgDeep} 62%)`,
          opacity: brandMix,
        }}
      />
    ) : null}
    {grid ? <GridBackdrop /> : null}
    {/* Viñeteado antes del contenido: es fondo, no un filtro sobre la tipografía. */}
    <Vignette />
    {children}
    {/* El grano sí va encima de todo: unifica el frame. */}
    <Grain />
  </AbsoluteFill>
);

// ═══ ENTRADAS DE TEXTO ═══════════════════════════════════════════════════════

/**
 * Entrada por máscara vertical: el texto se descubre de abajo hacia arriba
 * mientras sube los últimos píxeles. Es la entrada por defecto del episodio.
 */
export const MaskReveal: React.FC<{
  span: Span;
  /** Rango opcional para volver a enmascarar (salida). */
  out?: Span;
  direction?: "up" | "down";
  /** Cuántos px sube/baja el contenido mientras se descubre. */
  travel?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ span, out, direction = "up", travel = 26, style, children }) => {
  const frame = useCurrentFrame();
  const p = ramp(frame, span);
  const q = out ? ramp(frame, out) : 0;

  // El clip visible crece desde el borde opuesto a la dirección de entrada.
  const hidden = (1 - p) * 100;
  const closing = q * 100;
  const inset =
    direction === "up"
      ? `${Math.max(hidden, 0)}% 0% ${closing}% 0%`
      : `${closing}% 0% ${Math.max(hidden, 0)}% 0%`;

  const dy = (1 - p) * travel * (direction === "up" ? 1 : -1);

  return (
    <div style={{ ...style, clipPath: `inset(${inset})` }}>
      <div style={{ transform: `translateY(${dy}px)` }}>{children}</div>
    </div>
  );
};

/** Entrada por foco: entra desenfocado y se resuelve. Nunca un fade solo. */
export const BlurFocus: React.FC<{
  span: Span;
  out?: Span;
  blur?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ span, out, blur = 14, style, children }) => {
  const frame = useCurrentFrame();
  const p = ramp(frame, span);
  const q = out ? ramp(frame, out) : 0;
  const b = (1 - p) * blur + q * blur;
  return (
    <div
      style={{
        ...style,
        filter: `blur(${b.toFixed(2)}px)`,
        opacity: p * (1 - q),
      }}
    >
      {children}
    </div>
  );
};

/**
 * Push-in de cámara. Lento y con intención: solo en remates. No hay parallax
 * en este episodio.
 */
export const PushIn: React.FC<{
  span: Span;
  to?: number;
  children: React.ReactNode;
}> = ({ span, to = 1.05, children }) => {
  const frame = useCurrentFrame();
  const scale = ramp(frame, span, [1, to], EASE.inOut);
  return (
    <AbsoluteFill style={{ transform: `scale(${scale.toFixed(4)})`, transformOrigin: "50% 50%" }}>
      {children}
    </AbsoluteFill>
  );
};

// ═══ PUNTUACIÓN ENTRE MOVIMIENTOS ════════════════════════════════════════════

/**
 * Flash de gridline. Es el único recurso de corte del episodio junto al
 * barrido diagonal — coherencia, no variedad.
 */
export const GridFlash: React.FC<{ at: number; duration?: number }> = ({ at, duration }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // ~0.27 s. En frames fijos, a 60 fps el flash duraría la mitad y casi no se
  // vería — es el único recurso de corte del episodio, tiene que registrarse.
  const span = duration ?? Math.round(0.27 * fps);
  // OJO: clamp a la izquierda devuelve 1 para todo frame ANTERIOR al corte, así
  // que el flash tiene que apagarse explícitamente antes de `at`. Sin esta
  // guarda, los flashes de los cortes futuros quedan encendidos desde el frame 0.
  if (frame < at) return null;
  const p = interpolate(frame, [at, at + span], [1, 0], {
    easing: EASE.in,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  if (p <= 0) return null;
  // Misma retícula, subida a un stroke visible: el corte "prende" la grilla.
  return (
    <AbsoluteFill style={{ opacity: p, pointerEvents: "none" }}>
      <GridBackdrop step={120} stroke={bone(0.5)} />
    </AbsoluteFill>
  );
};

/**
 * Barrido diagonal en el ángulo de marca: una banda perpendicular al gradiente
 * (45° en pantalla, top-right → bottom-left) que cruza el frame y se va.
 */
export const DiagonalWipe: React.FC<{
  span: Span;
  color?: string;
  /** Ancho de la banda medido perpendicular a su eje, en px. */
  band?: number;
}> = ({ span, color = COLORS.bone, band = 260 }) => {
  const frame = useCurrentFrame();
  const p = ramp(frame, span, [0, 1], EASE.inOut);
  if (p <= 0 || p >= 1) return null;

  // En vertical el barrido cruza de arriba hacia abajo. El margen extra cubre
  // el alto que gana la banda al rotar más el ancho del frame.
  const travel = HEIGHT / 2 + WIDTH + band;
  const dy = interpolate(p, [0, 1], [-travel, travel]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: band,
          height: 4000,
          marginLeft: -band / 2,
          marginTop: -2000,
          background: `linear-gradient(90deg, transparent 0%, ${color} 45%, ${color} 55%, transparent 100%)`,
          opacity: 0.92,
          transform: `translateY(${dy.toFixed(1)}px) rotate(45deg)`,
        }}
      />
    </AbsoluteFill>
  );
};

// ═══ TIPOGRAFÍA CINÉTICA ═════════════════════════════════════════════════════

/** Kicker: etiqueta chica en versalitas con tracking abierto. */
export const Kicker: React.FC<{
  children: React.ReactNode;
  color?: string;
  style?: React.CSSProperties;
}> = ({ children, color = COLORS.boneDim, style }) => (
  <div
    style={{
      fontFamily: FONT.body,
      fontWeight: 600,
      fontSize: TYPE.label,
      letterSpacing: TRACKING.label,
      textTransform: "uppercase",
      color,
      ...style,
    }}
  >
    {children}
  </div>
);

/** Headline en Archivo Black. El peso tipográfico es la voz del episodio. */
export const Headline: React.FC<{
  children: React.ReactNode;
  size?: number;
  color?: string;
  style?: React.CSSProperties;
}> = ({ children, size = TYPE.h1, color = COLORS.bone, style }) => (
  <div
    style={{
      fontFamily: FONT.display,
      fontSize: size,
      lineHeight: 0.98,
      letterSpacing: TRACKING.display,
      color,
      ...style,
    }}
  >
    {children}
  </div>
);

/**
 * Línea que se autocompleta. Simula output de IA: prolijo, sin dudas, sin
 * correcciones. Ese es el punto — no titubea nunca.
 */
export const Typeline: React.FC<{
  text: string;
  span: Span;
  style?: React.CSSProperties;
  caret?: boolean;
}> = ({ text, span, style, caret = true }) => {
  const frame = useCurrentFrame();
  const p = ramp(frame, span, [0, 1], EASE.inOut);
  const shown = Math.round(p * text.length);
  const typing = frame >= span.from && frame < span.to;
  return (
    <div style={{ fontFamily: FONT.body, color: COLORS.boneDim, ...style }}>
      {text.slice(0, shown)}
      {caret && typing ? (
        <span style={{ color: bone(0.3) }}>▌</span>
      ) : null}
    </div>
  );
};

/**
 * Micro-shake determinista que decae. Para las muescas de M2: cada marca se
 * graba con impacto, no aparece.
 */
export const useShake = (
  delay: number,
  amplitude = 7,
  /** Duración total del temblor, EN SEGUNDOS. En frames, a 60 fps duraría la
   *  mitad de tiempo y el impacto dejaría de sentirse. */
  decaySeconds = 0.6,
  seed = "s"
) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const span = decaySeconds * fps;
  const t = frame - delay;
  if (t < 0 || t > span) return { x: 0, y: 0 };
  const fall = Math.max(0, 1 - t / span);
  // El jitter se muestrea por unidad de tiempo, no por frame: si no, a 60 fps
  // el temblor tiene el doble de muestras y se ve como vibración fina.
  const tick = Math.floor((t / fps) * 30);
  return {
    x: (random(`${seed}x${tick}`) - 0.5) * amplitude * fall * fall,
    y: (random(`${seed}y${tick}`) - 0.5) * amplitude * fall * fall,
  };
};
