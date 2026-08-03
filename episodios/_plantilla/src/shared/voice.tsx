import React, { createContext, useContext, useMemo } from 'react';
import { staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { useAudioData, visualizeAudio, visualizeAudioWaveform } from '@remotion/media-utils';

/**
 * LA VOZ, MEDIDA.
 *
 * El episodio no tiene rostro. Lo único que pasa de verdad en el tiempo
 * es la voz, así que la textura de fondo y el pane de abajo se mueven con
 * ella: no es un visualizador de música pegado encima, es lo mismo que se
 * está escuchando, dibujado.
 *
 * Se mide UNA vez por frame, acá arriba, y se reparte por contexto. Si
 * cada componente llamara a visualizeAudio() por su cuenta, el render
 * decodificaría el mismo mp3 varias veces por frame.
 */
export type VoiceFrame = {
  /** 0..1 — cuánta voz hay ahora. Ya viene comprimida y clampeada. */
  energy: number;
  /** Espectro en pocas bandas, para repartir movimiento sin que sincronice todo igual. */
  bands: number[];
  /** Forma de onda de la ventana alrededor del frame, -1..1. */
  wave: number[];
  /** false mientras el audio no cargó (preview): todo cae a valores neutros. */
  ready: boolean;
};

const SILENT: VoiceFrame = { energy: 0, bands: [], wave: [], ready: false };

const VoiceCtx = createContext<VoiceFrame>(SILENT);

export const useVoice = () => useContext(VoiceCtx);

/** Bandas del espectro. Pocas: es textura, no un analizador. */
const BANDS = 16;
/**
 * Muestras y ventana de la onda. Con más muestras el trazo se vuelve
 * sismógrafo —ruido, no voz—; con menos, una panza sin detalle.
 */
const WAVE_SAMPLES = 64;
const WAVE_WINDOW = 0.45;
/**
 * La voz hablada llega bajita al espectro. Sin ganancia, todo el
 * movimiento queda en el 5% inferior del rango y no se ve nada.
 */
const GAIN = 5.5;

/**
 * Sin VO todavía, todo cae a silencio en vez de romper: el esqueleto del
 * episodio se puede componer antes de que exista la grabación.
 */
export const VoiceProvider: React.FC<{
  src: string;
  startFrom?: number;
  children: React.ReactNode;
}> = ({ src, startFrom, children }) =>
  src ? (
    <VoiceFromAudio src={src} startFrom={startFrom}>
      {children}
    </VoiceFromAudio>
  ) : (
    <VoiceCtx.Provider value={SILENT}>{children}</VoiceCtx.Provider>
  );

const VoiceFromAudio: React.FC<{
  src: string;
  /** Frame del episodio en que arranca esta composición (previews de bloque). */
  startFrom?: number;
  children: React.ReactNode;
}> = ({ src, startFrom = 0, children }) => {
  const frame = useCurrentFrame() + startFrom;
  const { fps } = useVideoConfig();
  const audioData = useAudioData(staticFile(src));

  const value = useMemo<VoiceFrame>(() => {
    if (!audioData) return SILENT;

    const bands = visualizeAudio({
      audioData,
      frame,
      fps,
      numberOfSamples: BANDS,
      smoothing: true,
    });

    const wave = visualizeAudioWaveform({
      audioData,
      frame,
      fps,
      windowInSeconds: WAVE_WINDOW,
      numberOfSamples: WAVE_SAMPLES,
      normalize: false,
    });

    // La energía sale de las bandas bajas y medias: son las de la voz.
    // Las altas son consonantes y siseo, y hacen titilar todo.
    const voiced = bands.slice(0, 6);
    const raw = voiced.reduce((a, b) => a + b, 0) / Math.max(1, voiced.length);
    const energy = Math.min(1, Math.max(0, raw * GAIN));

    return { energy, bands, wave, ready: true };
  }, [audioData, frame, fps]);

  return <VoiceCtx.Provider value={value}>{children}</VoiceCtx.Provider>;
};
