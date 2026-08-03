import React from 'react';
import { Img, staticFile } from 'remotion';
import { COLOR, STROKE, TYPE } from '../theme';
import { useDiagonalMask } from './DiagonalWipe';
import { FadeUp, px, useSpringAt } from './anim';

/**
 * Todo activo externo (captura, logo, figura de paper) entra por acá.
 *
 * El marco es lo que dice "esto es una cita, no es mío". Sin marco y sin
 * pie, una captura de un sitio blanco dentro de un sistema negro se lee
 * como pantallazo de tutorial y baja la posición de autor.
 *
 * Nunca a sangre. Nunca sin pie de fuente.
 */
export const QuotedAsset: React.FC<{
  at: number;
  src: string;
  /** Fuente + fecha. Obligatorio. */
  source: string;
  /** Ancho como fracción del pane. 0.55–0.70 */
  scale?: number;
  /** Rotación fija por instancia, entre -2 y 2 grados. */
  rotate?: number;
  paneWidth?: number;
  desaturate?: boolean;
  style?: React.CSSProperties;
  out?: number;
}> = ({
  at,
  src,
  source,
  scale = 0.62,
  rotate = -1.5,
  paneWidth = 1080,
  desaturate = true,
  style,
  out,
}) => {
  const mask = useDiagonalMask(at, 18);
  const p = useSpringAt(at, 18);
  const width = Math.round(paneWidth * scale);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        transform: `rotate(${rotate}deg) translateY(${px((1 - p) * 20)}px)`,
        ...style,
      }}
    >
      <div
        style={{
          ...mask,
          width,
          border: `${STROKE}px solid ${COLOR.bone}`,
          boxShadow: '0 24px 64px rgba(0,0,0,0.8)',
          background: COLOR.bg,
          overflow: 'hidden',
        }}
      >
        <Img
          src={staticFile(src)}
          style={{
            width: '100%',
            display: 'block',
            filter: desaturate ? 'grayscale(1) contrast(1.15)' : undefined,
          }}
        />
      </div>
      <FadeUp at={at + 12} style={{ marginTop: 16, width }}>
        <div style={TYPE.footnote}>{source}</div>
      </FadeUp>
    </div>
  );
};

/**
 * Cita textual re-tipografiada. Para el headline del sitio: el texto es
 * real, la tipografía es tuya. Evita meter un bloque blanco en el sistema.
 */
export const QuoteCard: React.FC<{
  at: number;
  quote: string;
  source: string;
  width?: number;
  style?: React.CSSProperties;
}> = ({ at, quote, source, width = 840, style }) => {
  const mask = useDiagonalMask(at, 18);
  return (
    <div style={style}>
      <div
        style={{
          ...mask,
          width,
          border: `${STROKE}px solid ${COLOR.bone}`,
          padding: '48px 44px',
          background: COLOR.bg,
        }}
      >
        <div style={{ ...TYPE.displayM, fontSize: 56, lineHeight: 1.12 }}>
          «{quote}»
        </div>
      </div>
      <FadeUp at={at + 12} style={{ marginTop: 16 }}>
        <div style={TYPE.footnote}>{source}</div>
      </FadeUp>
    </div>
  );
};
