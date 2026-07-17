import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin, {
  Region,
} from "wavesurfer.js/dist/plugins/regions.esm.js";

interface ClipIn {
  start: number;
  end: number;
  title?: string;
  type?: string;
}

interface Meta {
  title: string;
  type: string;
}

const DEFAULT_TYPES = ["insight", "advice", "humor", "stat", "story"];
const REGION_COLOR = "rgba(74,144,217,0.22)";
const REGION_COLOR_SEL = "rgba(255,159,64,0.32)";

const fmtTime = (s: number): string => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const cs = Math.floor((s - Math.floor(s)) * 10);
  return `${m}:${sec.toString().padStart(2, "0")}.${cs}`;
};

const ClipEditorRaw: React.FC<ComponentProps> = ({ args, theme }) => {
  const videoUrl: string = args.video_url;
  const duration: number = args.duration || 0;
  const peaks: number[] | null = args.peaks || null;
  const types: string[] = args.types || DEFAULT_TYPES;
  const initialClips: ClipIn[] = args.clips || [];

  const videoRef = useRef<HTMLVideoElement>(null);
  const waveRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  const metaRef = useRef<Map<string, Meta>>(new Map());
  const initedRef = useRef<string>("");
  const seededRef = useRef(false);
  const stopAtRef = useRef<number | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [, force] = useState(0);
  const rerender = useCallback(() => force((n) => n + 1), []);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("");

  const dark =
    (theme && theme.base === "dark") ||
    (typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-color-scheme: dark)").matches);

  const paintSelection = useCallback((id: string | null) => {
    const regs = regionsRef.current?.getRegions() || [];
    regs.forEach((r) =>
      r.setOptions({ color: r.id === id ? REGION_COLOR_SEL : REGION_COLOR })
    );
  }, []);

  const selectRegion = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      paintSelection(id);
    },
    [paintSelection]
  );

  const ensureMeta = (id: string): Meta => {
    let m = metaRef.current.get(id);
    if (!m) {
      m = { title: "", type: types[0] || "insight" };
      metaRef.current.set(id, m);
    }
    return m;
  };

  // ── Setup de wavesurfer (una vez por video) ─────────────────────────────────
  useEffect(() => {
    if (!videoRef.current || !waveRef.current) return;
    if (initedRef.current === videoUrl) return;
    initedRef.current = videoUrl;

    wsRef.current?.destroy();
    metaRef.current.clear();
    seededRef.current = false;

    const peaksData = peaks && peaks.length ? peaks : undefined;
    const ws = WaveSurfer.create({
      container: waveRef.current,
      media: videoRef.current, // audio + playback + cursor sincronizados
      height: 88,
      waveColor: dark ? "#5a6b7a" : "#9db3c4",
      progressColor: "#4a90d9",
      cursorColor: dark ? "#fff" : "#333",
      normalize: true,
      interact: true,
      ...(peaksData ? { peaks: [peaksData], duration: duration || undefined } : {}),
    });
    wsRef.current = ws;

    const regions = ws.registerPlugin(RegionsPlugin.create());
    regionsRef.current = regions;
    regions.enableDragSelection({ color: REGION_COLOR });

    // Sembrar regiones iniciales SOLO cuando la duración es conocida; si se
    // agregan antes, wavesurfer las clampa a 0 y se pierden.
    const seedRegions = () => {
      if (seededRef.current) return;
      const dur = ws.getDuration() || videoRef.current?.duration || 0;
      if (!dur || !isFinite(dur)) return;
      seededRef.current = true;
      initialClips.forEach((cl) => {
        const start = Math.max(0, cl.start);
        const end = Math.min(dur, Math.max(start + 1, cl.end));
        const r = regions.addRegion({
          start,
          end,
          drag: true,
          resize: true,
          color: REGION_COLOR,
        });
        metaRef.current.set(r.id, {
          title: cl.title || "",
          type: cl.type || types[0] || "insight",
        });
      });
      setReady(true);
      rerender();
    };

    regions.on("region-created", (r: Region) => {
      ensureMeta(r.id);
      selectRegion(r.id);
      rerender();
    });
    regions.on("region-updated", () => rerender());
    regions.on("region-clicked", (r: Region, e: MouseEvent) => {
      e.stopPropagation();
      selectRegion(r.id);
    });

    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));
    ws.on("ready", () => {
      setReady(true);
      seedRegions();
    });
    ws.on("timeupdate", (t: number) => {
      const stopAt = stopAtRef.current;
      if (stopAt != null && t >= stopAt) {
        ws.pause();
        stopAtRef.current = null;
      }
    });

    const v = videoRef.current;
    const onMeta = () => seedRegions();
    v.addEventListener("loadedmetadata", onMeta);
    if (v.readyState >= 1) seedRegions();

    return () => {
      v.removeEventListener("loadedmetadata", onMeta);
      ws.destroy();
      wsRef.current = null;
      regionsRef.current = null;
      initedRef.current = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoUrl]);

  useEffect(() => {
    Streamlit.setFrameHeight();
  });
  useEffect(() => {
    const onResize = () => Streamlit.setFrameHeight();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // ── Acciones ────────────────────────────────────────────────────────────────
  const getSelected = (): Region | null => {
    if (!selectedId) return null;
    return regionsRef.current?.getRegions().find((r) => r.id === selectedId) || null;
  };

  const currentTime = (): number =>
    wsRef.current?.getCurrentTime() || videoRef.current?.currentTime || 0;

  const addRegion = () => {
    const regions = regionsRef.current;
    if (!regions) return;
    const dur = wsRef.current?.getDuration() || duration || 0;
    const t = currentTime();
    const end = dur ? Math.min(dur, t + 15) : t + 15;
    const r = regions.addRegion({
      start: t,
      end: Math.max(end, t + 1),
      drag: true,
      resize: true,
      color: REGION_COLOR,
    });
    ensureMeta(r.id);
    selectRegion(r.id);
    setStatus("Corte agregado");
  };

  const markIn = () => {
    const r = getSelected();
    if (!r) {
      addRegion();
      return;
    }
    r.setOptions({ start: Math.min(currentTime(), r.end - 0.2), end: r.end });
    rerender();
  };

  const markOut = () => {
    const r = getSelected();
    if (!r) return;
    r.setOptions({ start: r.start, end: Math.max(currentTime(), r.start + 0.2) });
    rerender();
  };

  const deleteRegion = () => {
    const r = getSelected();
    if (!r) return;
    metaRef.current.delete(r.id);
    r.remove();
    selectRegion(null);
    setStatus("Corte eliminado");
    rerender();
  };

  const togglePlay = () => {
    stopAtRef.current = null;
    wsRef.current?.playPause();
  };

  const playRegion = () => {
    const r = getSelected();
    const ws = wsRef.current;
    if (!r || !ws) {
      togglePlay();
      return;
    }
    ws.setTime(r.start);
    stopAtRef.current = r.end;
    ws.play();
  };

  const apply = () => {
    const regions = regionsRef.current?.getRegions() || [];
    const out = regions
      .map((r) => {
        const m = ensureMeta(r.id);
        return {
          start: Math.round(r.start * 100) / 100,
          end: Math.round(r.end * 100) / 100,
          title: m.title,
          type: m.type,
        };
      })
      .filter((cl) => cl.end - cl.start >= 0.5)
      .sort((a, b) => a.start - b.start);
    Streamlit.setComponentValue(out);
    setStatus(`✓ ${out.length} corte(s) enviados`);
  };

  const selected = getSelected();
  const selMeta = selected ? ensureMeta(selected.id) : null;
  const regionCount = regionsRef.current?.getRegions().length || 0;

  // ── Estilos ─────────────────────────────────────────────────────────────────
  const c = {
    fg: dark ? "#e6e6e6" : "#1a1a1a",
    sub: dark ? "#9aa7b2" : "#5a6a76",
    panel: dark ? "#1c2530" : "#f4f7fa",
    border: dark ? "#33414f" : "#d6dee6",
    accent: "#4a90d9",
  };
  const btn: React.CSSProperties = {
    background: c.panel,
    color: c.fg,
    border: `1px solid ${c.border}`,
    borderRadius: 6,
    padding: "6px 12px",
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
  };
  const btnPrimary: React.CSSProperties = {
    ...btn,
    background: c.accent,
    color: "#fff",
    border: "none",
    fontWeight: 600,
  };

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", color: c.fg, padding: 4 }}>
      <video
        ref={videoRef}
        src={videoUrl}
        playsInline
        preload="metadata"
        style={{
          width: "100%",
          maxHeight: 320,
          background: "#000",
          borderRadius: 8,
          display: "block",
        }}
      />

      <div ref={waveRef} style={{ marginTop: 10 }} />

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
        <button style={btn} onClick={togglePlay}>
          {playing ? "⏸ Pausa" : "▶ Play"}
        </button>
        <button style={btn} onClick={markIn} title="Fijar inicio en el tiempo actual">
          ⇤ Marcar IN
        </button>
        <button style={btn} onClick={markOut} title="Fijar fin en el tiempo actual">
          Marcar OUT ⇥
        </button>
        <button style={btn} onClick={addRegion}>
          ＋ Añadir corte
        </button>
        <button style={btn} onClick={playRegion} disabled={!selected}>
          ▶ Reproducir corte
        </button>
        <button style={btn} onClick={deleteRegion} disabled={!selected}>
          🗑 Borrar
        </button>
        <div style={{ flex: 1 }} />
        <button style={btnPrimary} onClick={apply}>
          ✓ Aplicar {regionCount} cortes
        </button>
      </div>

      <div style={{ fontSize: 12, color: c.sub, marginTop: 6 }}>
        {ready
          ? "Arrastrá sobre la onda para crear un corte. Clic en un corte para seleccionarlo; arrastrá sus bordes para ajustar inicio/fin. "
          : "Cargando video… "}
        {status}
      </div>

      {selected && selMeta ? (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: c.panel,
            border: `1px solid ${c.border}`,
            borderRadius: 8,
          }}
        >
          <div style={{ fontSize: 12, color: c.sub, marginBottom: 8 }}>
            Corte seleccionado · {fmtTime(selected.start)} → {fmtTime(selected.end)} ·{" "}
            {fmtTime(selected.end - selected.start)} de duración
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input
              value={selMeta.title}
              placeholder="Título del corte"
              onChange={(e) => {
                selMeta.title = e.target.value;
                rerender();
              }}
              style={{
                flex: 3,
                minWidth: 200,
                padding: "7px 10px",
                borderRadius: 6,
                border: `1px solid ${c.border}`,
                background: dark ? "#0f1620" : "#fff",
                color: c.fg,
                fontSize: 13,
              }}
            />
            <select
              value={selMeta.type}
              onChange={(e) => {
                selMeta.type = e.target.value;
                rerender();
              }}
              style={{
                flex: 1,
                minWidth: 120,
                padding: "7px 10px",
                borderRadius: 6,
                border: `1px solid ${c.border}`,
                background: dark ? "#0f1620" : "#fff",
                color: c.fg,
                fontSize: 13,
              }}
            >
              {types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 12, fontSize: 13, color: c.sub }}>
          {regionCount === 0
            ? "No hay cortes todavía. Arrastrá sobre la onda o usá “Añadir corte”."
            : "Seleccioná un corte para editar su título y tipo."}
        </div>
      )}
    </div>
  );
};

const ClipEditor = withStreamlitConnection(ClipEditorRaw);
export default ClipEditor;
