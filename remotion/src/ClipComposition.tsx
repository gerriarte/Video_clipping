import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";

export interface Subtitle {
  start: number;
  end:   number;
  text:  string;
}

export interface ClipCompositionProps {
  clipPath:         string;
  subtitles:        Subtitle[];
  title:            string;
  width:            number;
  height:           number;
  fps:              number;
  durationInFrames?: number;
}

export const ClipComposition: React.FC<ClipCompositionProps> = ({ clipPath }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const opacity = interpolate(
    frame,
    [0, 8, durationInFrames - 8, durationInFrames],
    [0, 1, 1, 0],
    { easing: Easing.ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ background: "#000", opacity }}>

      {/* Fondo: video borroso que llena el frame 9:16 */}
      <AbsoluteFill>
        <OffthreadVideo
          src={clipPath}
          style={{
            width:     "100%",
            height:    "100%",
            objectFit: "cover",
            filter:    "blur(18px) brightness(0.35) saturate(1.3)",
            transform: "scale(1.08)",
          }}
        />
      </AbsoluteFill>

      {/* Video principal: letterbox centrado preservando 16:9 */}
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

    </AbsoluteFill>
  );
};
