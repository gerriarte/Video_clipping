import React from 'react';
import { createSmoothSvgPath } from '@remotion/media-utils';
import { CANVAS, COLOR, STROKE } from '../theme';
import { useVoice } from './voice';

/**
 * LA VOZ, DIBUJADA.
 *
 * El trazo central del pane de abajo. No es un visualizador pegado
 * encima: es la forma de onda del VO en ese instante, que es lo único
 * que de verdad está pasando en el tiempo en un episodio sin rostro.
 *
 * Cuando el VO calla, la línea se aplana. Eso es correcto y es el punto:
 * el cuadro se queda quieto exactamente cuando se queda quieto el que
 * habla.
 */
export const VoiceTrace: React.FC<{
  height: number;
  /** Amplitud en px del pico. */
  amp?: number;
  opacity?: number;
  /** Eje de silencio. En la cinta de fondo se saca: sería una línea más. */
  axis?: boolean;
}> = ({ height, amp = 300, opacity = 1, axis = true }) => {
  const { wave, energy, ready } = useVoice();
  const mid = height / 2;

  const points =
    ready && wave.length > 1
      ? wave.map((v, i) => ({
          x: (i / (wave.length - 1)) * CANVAS.width,
          y: mid - v * amp,
        }))
      : [
          { x: 0, y: mid },
          { x: CANVAS.width, y: mid },
        ];

  return (
    <svg
      width={CANVAS.width}
      height={height}
      style={{ position: 'absolute', left: 0, top: 0, opacity }}
    >
      {axis ? (
        <line
          x1={0}
          y1={mid}
          x2={CANVAS.width}
          y2={mid}
          stroke={COLOR.bone}
          strokeWidth={STROKE}
          opacity={0.14}
        />
      ) : null}
      <path
        d={createSmoothSvgPath({ points })}
        fill="none"
        stroke={COLOR.bone}
        strokeWidth={STROKE * 1.5}
        strokeLinecap="round"
        opacity={0.4 + energy * 0.45}
      />
    </svg>
  );
};

/**
 * La misma voz, como cinta al pie, para los tramos que corren a pane
 * completo. Va en la franja que la UI de la plataforma tapa: no lleva
 * información, sostiene el cuadro.
 */
export const VoiceRibbon: React.FC<{ y?: number; height?: number }> = ({
  y = 1440,
  height = 380,
}) => (
  <div style={{ position: 'absolute', left: 0, top: y, width: CANVAS.width, height }}>
    <VoiceTrace height={height} amp={150} opacity={0.5} axis={false} />
  </div>
);
