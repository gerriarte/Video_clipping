import React from 'react';
import { AbsoluteFill, Easing, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { CANVAS, COLOR, LAYOUT, STROKE, WIPE_ANGLE } from '../theme';

export type Mode = 'split' | 'full' | 'solo';

/**
 * Pane de rostro — modo SPLIT.
 *
 * ENCUADRE: los ojos van a y ≈ 1290 del canvas completo. Los últimos
 * 350px (y > 1570) son pecho y fondo: ahí se monta la UI de la
 * plataforma. Si la cara cae en esa franja, el caption te la tapa.
 *
 * Encuadre FIJO. Sin punch-in, sin reframing dinámico: el zoom lento
 * sobre la cara es lenguaje de contenido de volumen.
 */
export const FacePane: React.FC<{
  src: string;
  /** Corrimiento vertical del crop, en px. Negativo sube la cara. */
  offsetY?: number;
  /** Escala del crop. 1 = ancho completo. */
  scale?: number;
  /** Frame en que el pane entra (revelado por máscara diagonal). */
  enterAt?: number;
  /** Frame en que el pane sale. */
  exitAt?: number;
  startFrom?: number;
}> = ({ src, offsetY = 0, scale = 1, enterAt = 0, exitAt, startFrom }) => {
  const frame = useCurrentFrame();

  const enter = interpolate(frame, [enterAt, enterAt + 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const exit = exitAt
    ? interpolate(frame, [exitAt, exitAt + 20], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : 1;
  const p = Math.min(enter, exit);
  if (p <= 0) return null;

  // Revelado por máscara diagonal, no por deslizamiento.
  const slant = Math.tan((WIPE_ANGLE * Math.PI) / 180) * 100;
  const y = interpolate(p, [0, 1], [100 + slant, 0]);

  return (
    <>
      {/* Costura */}
      <div
        style={{
          position: 'absolute',
          top: LAYOUT.seamY,
          left: 0,
          width: CANVAS.width,
          height: STROKE,
          background: COLOR.seam,
          opacity: p,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: LAYOUT.facePane.y,
          left: 0,
          width: CANVAS.width,
          height: LAYOUT.facePane.height,
          overflow: 'hidden',
          background: COLOR.bg,
          clipPath: `polygon(0% ${y + slant}%, 100% ${y}%, 100% 200%, 0% 200%)`,
        }}
      >
        <OffthreadVideo
          src={staticFile(src)}
          startFrom={startFrom}
          style={{
            position: 'absolute',
            width: CANVAS.width * scale,
            left: (CANVAS.width - CANVAS.width * scale) / 2,
            top: offsetY,
            objectFit: 'cover',
          }}
        />
      </div>
    </>
  );
};

/**
 * Contenedor del pane de animación. Cambia de alto según el modo.
 * En FULL el contenido legible sigue confinado a y < SAFE.bottom;
 * el espacio de abajo es solo fondo, grano y elementos decorativos.
 *
 * SOLO es FULL para un bloque compuesto para el split: conserva la caja
 * de 960 para que el encuadre no se estire, pero centrada.
 */
export const AnimPane: React.FC<{
  mode: Mode;
  children: React.ReactNode;
}> = ({ mode, children }) => {
  const box =
    mode === 'split' ? LAYOUT.splitPane : mode === 'solo' ? LAYOUT.soloPane : LAYOUT.fullPane;
  return (
    <AbsoluteFill style={{ top: box.y, height: box.height, overflow: 'hidden' }}>
      {children}
    </AbsoluteFill>
  );
};

/** Barra de marca. Sacrificable: asumí que la UI la tapa. */
export const BrandBar: React.FC<{ episode: string }> = ({ episode }) => (
  <div
    style={{
      position: 'absolute',
      top: 0,
      left: LAYOUT.margin,
      height: 140,
      display: 'flex',
      alignItems: 'center',
      gap: 20,
    }}
  >
    <div
      style={{
        fontFamily: "'Archivo Black', sans-serif",
        fontSize: 34,
        letterSpacing: '-0.02em',
        color: COLOR.bone,
      }}
    >
      {/* El wordmark va MONOCROMO dentro del episodio. Si "ask" fuera
          rojo, el acento estaría en pantalla los 5 minutos y la regla
          de los 4 usos dejaría de significar algo. El logo a color vive
          en la portada y en el end card, no acá. */}
      mu<span style={{ opacity: 0.55 }}>ask</span>
    </div>
    <div style={{ width: STROKE, height: 26, background: COLOR.hairline }} />
    <div
      style={{
        fontFamily: "'Archivo', sans-serif",
        fontSize: 24,
        fontWeight: 600,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'rgba(242,239,233,0.46)',
      }}
    >
      {episode}
    </div>
  </div>
);
