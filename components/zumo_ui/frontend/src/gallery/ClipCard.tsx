/** Una tarjeta = un clip. React puro: props y callbacks, nada de host. */
import React, { useRef, useState } from "react";
import type { Clip, FormatDef } from "./types";
import { CropOverlay, FormatGlyph } from "../Crop";
import { clock, dur, type Tokens } from "../theme";

export interface CardProps {
  clip: Clip;
  formats: FormatDef[];
  types: string[];
  videoUrl: string;
  sourceAspect: number;
  t: Tokens;
  /** Si se elige qué clips entran al corte. Con false la tarjeta no se apaga. */
  pickable: boolean;
  /** Si esta es la tarjeta en foco (la que el host acompaña con sus controles). */
  focused: boolean;
  /** commit=false acumula el cambio; true lo manda al host en el acto. */
  onChange: (id: number, patch: Partial<Clip>, commit: boolean) => void;
  onFocus: (id: number) => void;
}

export const ClipCard: React.FC<CardProps> = ({
  clip, formats, types, videoUrl, sourceAspect, t, pickable, focused, onChange, onFocus,
}) => {
  const [thumbIdx, setThumbIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [hover, setHover] = useState(false);
  const [openReason, setOpenReason] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const fmt = formats.find((f) => f.key === clip.format);
  const thumbs = clip.thumbs || [];
  const thumb = thumbs[Math.min(thumbIdx, Math.max(0, thumbs.length - 1))];
  const shot = clip.shot;
  const suggested = shot?.suggestion;
  const off = pickable && !clip.selected;

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onMouseDown={() => onFocus(clip.id)}
      style={{
        background: t.card,
        border: `1px solid ${focused ? t.primary : (pickable && clip.selected) ? t.borderStrong : t.border}`,
        borderRadius: t.radius,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        boxShadow: hover ? t.shadow : "none",
        opacity: off ? 0.52 : 1,
        transition: "opacity .15s, box-shadow .15s, border-color .15s, transform .15s",
        transform: hover ? "translateY(-2px)" : "none",
      }}
    >
      {/* Foto del tramo + el recorte que hace el formato */}
      <div style={{ position: "relative", width: "100%", aspectRatio: String(sourceAspect), background: "#05070b" }}>
        {playing ? (
          <video
            ref={videoRef}
            src={clip.clipUrl || `${videoUrl}#t=${clip.start.toFixed(2)},${clip.end.toFixed(2)}`}
            autoPlay
            controls
            playsInline
            preload="metadata"
            onLoadedMetadata={(e) => {
              if (!clip.clipUrl) e.currentTarget.currentTime = clip.start;
            }}
            onTimeUpdate={(e) => {
              if (!clip.clipUrl && e.currentTarget.currentTime > clip.end) {
                e.currentTarget.pause();
                setPlaying(false);
              }
            }}
            style={{ width: "100%", height: "100%", objectFit: "contain", background: "#000" }}
          />
        ) : (
          <>
            {thumb ? (
              <img
                src={thumb.url}
                alt={thumb.label}
                loading="lazy"
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            ) : (
              <div style={{ ...center, color: t.sub, fontSize: 12 }}>sin fotos del tramo</div>
            )}
            <CropOverlay id={clip.id} fmt={fmt} centersX={shot?.centersX || []} sourceAspect={sourceAspect} t={t} />

            {pickable ? (
              <button
                onClick={() => onChange(clip.id, { selected: !clip.selected }, true)}
                title={clip.selected ? "Sacar del corte" : "Incluir en el corte"}
                style={{
                  position: "absolute", top: 8, left: 8, width: 24, height: 24,
                  borderRadius: 6, cursor: "pointer", display: "grid", placeItems: "center",
                  background: clip.selected ? t.primary : "rgba(6,8,12,0.66)",
                  border: `1px solid ${clip.selected ? t.primary : "rgba(255,255,255,0.28)"}`,
                  color: clip.selected ? t.onPrimary : "#fff",
                  fontSize: 13, lineHeight: 1, padding: 0,
                }}
              >
                {clip.selected ? "✓" : ""}
              </button>
            ) : (
              <div style={{ position: "absolute", top: 8, left: 8, ...pill }}>{clip.index}</div>
            )}

            <div style={{ position: "absolute", top: 8, right: 8, ...pill }}>{dur(clip.start, clip.end)}</div>

            {thumbs.length > 0 && (
              <button
                onClick={() => setPlaying(true)}
                title="Ver el tramo"
                style={{ ...playBtn, opacity: hover ? 1 : 0 }}
              >
                {"▶"}
              </button>
            )}

            {thumbs.length > 1 && (
              <div style={{ position: "absolute", right: 8, bottom: 8, display: "flex", gap: 4 }}>
                {thumbs.map((th, i) => (
                  <button
                    key={i}
                    onMouseEnter={() => setThumbIdx(i)}
                    onClick={() => setThumbIdx(i)}
                    title={th.label}
                    style={{
                      width: 16, height: 4, padding: 0, borderRadius: 2, cursor: "pointer", border: "none",
                      background: i === thumbIdx ? "#fff" : "rgba(255,255,255,0.38)",
                    }}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <div style={{ padding: "10px 12px 12px", display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        <input
          value={clip.title}
          title={clip.title}
          placeholder="Titulo del clip"
          onChange={(e) => onChange(clip.id, { title: e.target.value }, false)}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "transparent";
            e.currentTarget.style.background = "transparent";
            onChange(clip.id, {}, true);
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = t.borderStrong;
            e.currentTarget.style.background = "rgba(127,127,127,0.10)";
          }}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
          style={{
            font: "inherit", fontSize: 13.5, fontWeight: 600, lineHeight: 1.35, color: t.text,
            background: "transparent", border: "1px solid transparent", borderRadius: 6,
            padding: "3px 5px", margin: "0 -5px", width: "calc(100% + 10px)", outline: "none",
          }}
        />

        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: t.sub, flexWrap: "wrap" }}>
          <span style={{ fontVariantNumeric: "tabular-nums" }}>
            {clock(clip.start)} {"→"} {clock(clip.end)}
          </span>
          <span style={{ opacity: 0.4 }}>·</span>
          <select
            value={clip.type}
            onChange={(e) => onChange(clip.id, { type: e.target.value }, true)}
            style={{
              font: "inherit", fontSize: 11.5, color: t.sub, background: "transparent",
              border: "none", cursor: "pointer", outline: "none", padding: 0,
            }}
          >
            {types.map((ty) => (
              <option key={ty} value={ty} style={{ background: t.card, color: t.text }}>{ty}</option>
            ))}
          </select>
        </div>

        <ShotEvidence shot={shot} t={t} />

        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {formats.map((f) => {
            const active = f.key === clip.format;
            const star = f.key === suggested && !active;
            return (
              <button
                key={f.key}
                onClick={() => onChange(clip.id, { format: f.key }, true)}
                title={f.label + (f.key === suggested ? " — sugerido por el analisis" : "")}
                style={{
                  display: "flex", alignItems: "center", gap: 5, cursor: "pointer",
                  padding: "4px 7px", borderRadius: 7, fontSize: 11, lineHeight: 1,
                  whiteSpace: "nowrap", height: 26,
                  font: "inherit", fontWeight: active ? 600 : 400,
                  background: active ? t.primary : "transparent",
                  color: active ? t.onPrimary : t.sub,
                  border: `1px solid ${active ? t.primary : t.border}`,
                }}
              >
                <FormatGlyph fmt={f} color={active ? t.onPrimary : t.sub} />
                {f.short}
                {star && <span style={{ color: t.warn, fontWeight: 700 }}>{"★"}</span>}
              </button>
            );
          })}
        </div>

        {fmt?.crop && (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11, color: t.sub }}>
            {fmt.autoLayout && (
              <Toggle
                on={clip.speakerFollow}
                label="sigue al hablante"
                title="El recorte se desplaza para acompanar a quien habla."
                t={t}
                onClick={() => onChange(clip.id, { speakerFollow: !clip.speakerFollow }, true)}
              />
            )}
            <Toggle
              on={clip.followShot}
              label="sigue la toma"
              title="El recorte cambia dentro del clip: split cuando estan los dos, cerrado cuando la camara va a uno."
              t={t}
              onClick={() => onChange(clip.id, { followShot: !clip.followShot }, true)}
            />
          </div>
        )}

        {clip.reason && (
          <div
            onClick={() => setOpenReason((v) => !v)}
            title={openReason ? "" : clip.reason}
            style={{
              fontSize: 11, lineHeight: 1.45, color: t.sub, cursor: "pointer", marginTop: "auto",
              paddingTop: 6, borderTop: `1px solid ${t.border}`,
              display: "-webkit-box", WebkitBoxOrient: "vertical",
              WebkitLineClamp: openReason ? 99 : 2, overflow: "hidden",
            }}
          >
            {clip.reason}
          </div>
        )}
      </div>
    </div>
  );
};

/** La evidencia del analisis de la toma, con la barra que la respalda. */
const ShotEvidence: React.FC<{ shot: Clip["shot"]; t: Tokens }> = ({ shot, t }) => {
  if (!shot || !shot.samples) {
    return <div style={{ fontSize: 11, color: t.sub, opacity: 0.7 }}>toma sin analizar</div>;
  }
  const parts = [
    { v: shot.twoShot, c: t.primary, label: "2 personas" },
    { v: shot.solo, c: "#5b8def", label: "1 persona" },
    { v: shot.empty, c: t.sub, label: "sin caras" },
  ];
  const top = [...parts].sort((a, b) => b.v - a.v)[0];
  const text = shot.mixed
    ? `cambia de plano · 2 personas el ${Math.round(shot.twoShot * 100)}%`
    : `${top.label} el ${Math.round(top.v * 100)}% del clip`;
  return (
    <div title={`${shot.samples} muestras, una cada ~3 s`}>
      <div style={{ display: "flex", height: 3, borderRadius: 2, overflow: "hidden", background: "rgba(127,127,127,0.18)" }}>
        {parts.map((p, i) => (
          <div key={i} style={{ width: `${p.v * 100}%`, background: p.c, opacity: p.c === t.sub ? 0.45 : 0.9 }} />
        ))}
      </div>
      <div style={{ fontSize: 11, color: shot.mixed ? t.warn : t.sub, marginTop: 4 }}>{text}</div>
    </div>
  );
};

const Toggle: React.FC<{ on: boolean; label: string; title: string; t: Tokens; onClick: () => void }> = ({
  on, label, title, t, onClick,
}) => (
  <button
    onClick={onClick}
    title={title}
    style={{
      display: "flex", alignItems: "center", gap: 6, cursor: "pointer",
      background: "transparent", border: "none", padding: 0, font: "inherit",
      fontSize: 11, color: on ? t.text : t.sub,
    }}
  >
    <span
      style={{
        width: 24, height: 13, borderRadius: 999, position: "relative", flex: "0 0 auto",
        background: on ? t.primary : "rgba(127,127,127,0.32)", transition: "background .15s",
      }}
    >
      <span
        style={{
          position: "absolute", top: 2, left: on ? 13 : 2, width: 9, height: 9,
          borderRadius: "50%", background: on ? t.onPrimary : "#fff",
          transition: "left .15s",
        }}
      />
    </span>
    {label}
  </button>
);

const center: React.CSSProperties = { position: "absolute", inset: 0, display: "grid", placeItems: "center" };

const pill: React.CSSProperties = {
  padding: "2px 7px", borderRadius: 999, fontSize: 10.5, fontVariantNumeric: "tabular-nums",
  background: "rgba(6,8,12,0.66)", color: "rgba(255,255,255,0.88)",
  border: "1px solid rgba(255,255,255,0.16)",
};

const playBtn: React.CSSProperties = {
  position: "absolute", display: "grid", placeItems: "center",
  width: 42, height: 42, top: "50%", left: "50%",
  transform: "translate(-50%,-50%)", borderRadius: "50%", cursor: "pointer",
  background: "rgba(6,8,12,0.72)", border: "1px solid rgba(255,255,255,0.3)",
  color: "#fff", fontSize: 15, padding: 0, transition: "opacity .15s",
};
