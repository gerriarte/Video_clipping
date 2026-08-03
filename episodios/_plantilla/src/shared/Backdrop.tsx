import React from 'react';
import { AbsoluteFill, random, useCurrentFrame } from 'remotion';
import { CANVAS, COLOR, LAYOUT, STROKE, TYPE } from '../theme';
import { Grain } from './Texture';
import { useVoice } from './voice';

/**
 * EL FONDO DEL EPISODIO.
 *
 * Un negro plano durante cuatro minutos y medio se lee como una placa,
 * no como un video. Esto es lo que hace que el cuadro esté vivo sin
 * competirle al texto: una trama de filetes que deriva despacio y
 * respira con la voz, la retícula editorial que sostiene la
 * composición, y el reloj del episodio.
 *
 * Todo acá vive por debajo de 0.10 de opacidad. Si algo de esto se
 * "ve", está mal calibrado: tiene que notarse cuando no está.
 */

/** Filetes horizontales que derivan. Es la textura base de todo el video. */
const DriftLines: React.FC<{ density: number }> = ({ density }) => {
  const frame = useCurrentFrame();
  const { energy } = useVoice();

  const spacing = 46;
  const count = Math.ceil(CANVAS.height / spacing) + 2;
  // La deriva es continua —como el grano— pero la voz la empuja: en los
  // silencios el cuadro casi se queda quieto.
  const drift = (frame * (0.22 + energy * 0.5)) % spacing;
  const lift = 0.62 + energy * 0.55;

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {Array.from({ length: count }).map((_, i) => {
        const seed = random(`drift-${i}`);
        // Cada filete late a su propio ritmo: si respiran todos juntos,
        // el fondo pulsa y se transforma en un elemento más.
        const breath = 0.55 + 0.45 * Math.sin(frame * 0.012 + i * 0.7);
        const opacity = (0.022 + seed * 0.05) * density * lift * breath;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: Math.round(i * spacing - drift),
              height: STROKE,
              background: COLOR.bone,
              opacity,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/**
 * Retícula editorial. Los ejes sobre los que está compuesto todo el
 * episodio, dejados a la vista. No decora: explica por qué el texto cae
 * donde cae.
 */
const EditorialGrid: React.FC = () => {
  const cols = [LAYOUT.margin, CANVAS.width / 2, CANVAS.width - LAYOUT.margin];
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {cols.map((x, i) => (
        <div
          key={x}
          style={{
            position: 'absolute',
            left: x,
            top: 0,
            bottom: 0,
            width: STROKE,
            background: COLOR.bone,
            opacity: i === 1 ? 0.03 : 0.055,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

/**
 * Reloj del episodio: un filete que avanza bajo la barra de marca.
 * Es la tercera y última excepción a la regla del `linear` —como el
 * grano, un reloj que acelera miente.
 */
const ProgressRule: React.FC<{ total: number }> = ({ total }) => {
  const frame = useCurrentFrame();
  const p = Math.min(1, Math.max(0, frame / total));
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: LAYOUT.progressY,
          height: STROKE,
          background: COLOR.bone,
          opacity: 0.07,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: LAYOUT.progressY,
          width: Math.round(CANVAS.width * p),
          height: STROKE,
          background: COLOR.bone,
          opacity: 0.3,
        }}
      />
    </>
  );
};

/** Folio: en qué bloque de los cinco estamos. Dato, no adorno. */
const Folio: React.FC<{ index: number; total: number }> = ({ index, total }) => (
  <div
    style={{
      position: 'absolute',
      right: LAYOUT.margin,
      top: 52,
      ...TYPE.footnote,
      color: 'rgba(242,239,233,0.38)',
      letterSpacing: '0.18em',
    }}
  >
    {String(index + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}
  </div>
);

/** Viñeta que respira con la voz. */
const LiveVignette: React.FC = () => {
  const { energy } = useVoice();
  const open = 45 + energy * 10;
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse 78% 58% at 50% 45%, transparent ${open}%, rgba(0,0,0,0.6) 100%)`,
        pointerEvents: 'none',
      }}
    />
  );
};

/**
 * @param density  cuánta trama pide el bloque. Los bloques con visual
 *                 denso (columnas, curvas) piden menos fondo.
 */
export const Backdrop: React.FC<{
  total: number;
  blockIndex: number;
  blockCount: number;
  density?: number;
}> = ({ total, blockIndex, blockCount, density = 1 }) => (
  <AbsoluteFill style={{ pointerEvents: 'none' }}>
    <EditorialGrid />
    <DriftLines density={density} />
    <ProgressRule total={total} />
    <Folio index={blockIndex} total={blockCount} />
  </AbsoluteFill>
);

/** Capas que van ARRIBA de todo el contenido. */
export const BackdropTop: React.FC = () => (
  <>
    <LiveVignette />
    <Grain />
  </>
);
