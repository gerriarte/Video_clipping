import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Streamlit,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin, {
  Region,
} from "wavesurfer.js/dist/plugins/regions.esm.js";

interface ClipIn { start: number; end: number; title?: string; type?: string }
interface Cue { start: number; end: number; text: string }
interface Meta { title: string; type: string }
interface Snap { start: number; end: number; title: string; type: string }

const DEFAULT_TYPES = ["insight", "advice", "humor", "stat", "story"];
const REGION_COLOR = "rgba(74,144,217,0.22)";
const REGION_COLOR_SEL = "rgba(255,159,64,0.34)";
const REGION_COLOR_BAD = "rgba(220,70,70,0.30)";
const SNAP_THRESH = 0.4; // seg
const MIN_OK = 8;        // duración mínima recomendada
const MAX_OK = 90;       // duración máxima recomendada

const fmtTime = (s: number): string => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const cs = Math.floor((s - Math.floor(s)) * 10);
  return `${m}:${sec.toString().padStart(2, "0")}.${cs}`;
};

const fmtClock = (s: number): string => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
};

const ClipEditorRaw: React.FC<ComponentProps> = ({ args, theme }) => {
  const videoUrl: string = args.video_url;
  const duration: number = args.duration || 0;
  const peaks: number[] | null = args.peaks || null;
  const cues: Cue[] = args.cues || [];
  const types: string[] = args.types || DEFAULT_TYPES;
  const initialClips: ClipIn[] = args.clips || [];
  const storageKey: string = args.storage_key || videoUrl;
  const lsKey = `clipedit:${storageKey}`;

  const videoRef = useRef<HTMLVideoElement>(null);
  const waveRef = useRef<HTMLDivElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  const metaRef = useRef<Map<string, Meta>>(new Map());
  const initedRef = useRef<string>("");
  const seededRef = useRef(false);
  const suppressRef = useRef(false); // no registrar historial durante seed/restore
  const stopAtRef = useRef<number | null>(null);
  const histRef = useRef<Snap[][]>([]);
  const histIdxRef = useRef<number>(-1);
  const histTimerRef = useRef<number | null>(null);
  const invalidRef = useRef<Set<string>>(new Set());

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [, force] = useState(0);
  const rerender = useCallback(() => force((n) => n + 1), []);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("");
  const [currentT, setCurrentT] = useState(0);
  const [activeCue, setActiveCue] = useState(-1);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [pxPerSec, setPxPerSec] = useState(0);

  const dark =
    (theme && theme.base === "dark") ||
    (typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-color-scheme: dark)").matches);

  // Límites de frase para "snap" (todos los start/end de los cues, ordenados).
  const boundaries = useMemo(() => {
    const b = new Set<number>();
    cues.forEach((c) => { b.add(+c.start.toFixed(3)); b.add(+c.end.toFixed(3)); });
    return Array.from(b).sort((a, z) => a - z);
  }, [cues]);

  const snapTime = useCallback((t: number): number => {
    if (!boundaries.length) return t;
    let lo = 0, hi = boundaries.length - 1, best = boundaries[0];
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (Math.abs(boundaries[mid] - t) < Math.abs(best - t)) best = boundaries[mid];
      if (boundaries[mid] < t) lo = mid + 1; else hi = mid - 1;
    }
    return Math.abs(best - t) <= SNAP_THRESH ? best : t;
  }, [boundaries]);

  const ensureMeta = (id: string): Meta => {
    let m = metaRef.current.get(id);
    if (!m) { m = { title: "", type: types[0] || "insight" }; metaRef.current.set(id, m); }
    return m;
  };

  // ── Snapshot / historial / autosave ─────────────────────────────────────────
  const snapshot = useCallback((): Snap[] => {
    const regs = regionsRef.current?.getRegions() || [];
    return regs.map((r) => {
      const m = ensureMeta(r.id);
      return { start: r.start, end: r.end, title: m.title, type: m.type };
    }).sort((a, b) => a.start - b.start);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveLocal = useCallback((snap: Snap[]) => {
    try { window.localStorage.setItem(lsKey, JSON.stringify({ v: 1, regions: snap })); } catch {}
  }, [lsKey]);

  const validate = useCallback(() => {
    const regs = (regionsRef.current?.getRegions() || []).slice().sort((a, b) => a.start - b.start);
    const invalid = new Set<string>();
    const msgs: string[] = [];
    for (let i = 0; i < regs.length; i++) {
      const d = regs[i].end - regs[i].start;
      if (d < MIN_OK) { invalid.add(regs[i].id); }
      if (d > MAX_OK) { invalid.add(regs[i].id); }
      if (i > 0 && regs[i].start < regs[i - 1].end - 0.05) {
        invalid.add(regs[i].id); invalid.add(regs[i - 1].id);
      }
    }
    const short = regs.filter((r) => r.end - r.start < MIN_OK).length;
    const long = regs.filter((r) => r.end - r.start > MAX_OK).length;
    let overlaps = 0;
    for (let i = 1; i < regs.length; i++) if (regs[i].start < regs[i - 1].end - 0.05) overlaps++;
    if (short) msgs.push(`${short} corte(s) muy corto(s) (<${MIN_OK}s)`);
    if (long) msgs.push(`${long} corte(s) muy largo(s) (>${MAX_OK}s)`);
    if (overlaps) msgs.push(`${overlaps} solapamiento(s) entre cortes`);
    invalidRef.current = invalid;
    setWarnings(msgs);
  }, []);

  const paint = useCallback((sel: string | null) => {
    const regs = regionsRef.current?.getRegions() || [];
    regs.forEach((r) =>
      r.setOptions({
        color: r.id === sel ? REGION_COLOR_SEL
          : invalidRef.current.has(r.id) ? REGION_COLOR_BAD
          : REGION_COLOR,
      })
    );
  }, []);

  const selectRegion = useCallback((id: string | null) => {
    setSelectedId(id);
    paint(id);
  }, [paint]);

  const pushHistory = useCallback(() => {
    if (suppressRef.current) return;
    validate();
    const snap = snapshot();
    const h = histRef.current.slice(0, histIdxRef.current + 1);
    h.push(snap);
    histRef.current = h;
    histIdxRef.current = h.length - 1;
    saveLocal(snap);
    paint(selectedId);
    rerender();
  }, [snapshot, saveLocal, validate, paint, selectedId, rerender]);

  const restore = useCallback((snap: Snap[]) => {
    const regions = regionsRef.current;
    if (!regions) return;
    suppressRef.current = true;
    regions.getRegions().forEach((r) => r.remove());
    metaRef.current.clear();
    snap.forEach((cl) => {
      const r = regions.addRegion({
        start: cl.start, end: cl.end, drag: true, resize: true, color: REGION_COLOR,
      });
      metaRef.current.set(r.id, { title: cl.title || "", type: cl.type || types[0] || "insight" });
    });
    suppressRef.current = false;
    setSelectedId(null);
    validate();
    paint(null);
    rerender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validate, paint, rerender]);

  const undo = useCallback(() => {
    if (histIdxRef.current <= 0) return;
    histIdxRef.current -= 1;
    restore(histRef.current[histIdxRef.current]);
    saveLocal(histRef.current[histIdxRef.current]);
    setStatus("Deshacer");
  }, [restore, saveLocal]);

  const redo = useCallback(() => {
    if (histIdxRef.current >= histRef.current.length - 1) return;
    histIdxRef.current += 1;
    restore(histRef.current[histIdxRef.current]);
    saveLocal(histRef.current[histIdxRef.current]);
    setStatus("Rehacer");
  }, [restore, saveLocal]);

  // ── Setup de wavesurfer (una vez por video) ─────────────────────────────────
  useEffect(() => {
    if (!videoRef.current || !waveRef.current) return;
    if (initedRef.current === videoUrl) return;
    initedRef.current = videoUrl;

    wsRef.current?.destroy();
    metaRef.current.clear();
    seededRef.current = false;
    histRef.current = [];
    histIdxRef.current = -1;

    const peaksData = peaks && peaks.length ? peaks : undefined;
    const ws = WaveSurfer.create({
      container: waveRef.current,
      media: videoRef.current,
      height: 88,
      waveColor: dark ? "#5a6b7a" : "#9db3c4",
      progressColor: "#4a90d9",
      cursorColor: dark ? "#fff" : "#333",
      normalize: true,
      interact: true,
      minPxPerSec: 1,
      ...(peaksData ? { peaks: [peaksData], duration: duration || undefined } : {}),
    });
    wsRef.current = ws;

    const regions = ws.registerPlugin(RegionsPlugin.create());
    regionsRef.current = regions;
    regions.enableDragSelection({ color: REGION_COLOR });

    const seedOrRestore = () => {
      if (seededRef.current) return;
      const dur = ws.getDuration() || videoRef.current?.duration || 0;
      if (!dur || !isFinite(dur)) return;
      seededRef.current = true;

      // Autosave previo (localStorage) tiene prioridad sobre la semilla.
      let base: Snap[] | null = null;
      try {
        const raw = window.localStorage.getItem(lsKey);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed && Array.isArray(parsed.regions) && parsed.regions.length) {
            base = parsed.regions;
            setStatus("Restaurado tu trabajo previo");
          }
        }
      } catch {}
      if (!base) {
        base = initialClips.map((cl) => ({
          start: Math.max(0, cl.start),
          end: Math.min(dur, Math.max(cl.start + 1, cl.end)),
          title: cl.title || "",
          type: cl.type || types[0] || "insight",
        }));
      }

      suppressRef.current = true;
      base.forEach((cl) => {
        const r = regions.addRegion({
          start: cl.start, end: cl.end, drag: true, resize: true, color: REGION_COLOR,
        });
        metaRef.current.set(r.id, { title: cl.title || "", type: cl.type || types[0] || "insight" });
      });
      suppressRef.current = false;

      histRef.current = [snapshot()];
      histIdxRef.current = 0;
      validate();
      paint(null);
      setReady(true);
      rerender();
    };

    regions.on("region-created", (r: Region) => {
      if (suppressRef.current) return;
      ensureMeta(r.id);
      selectRegion(r.id);
      pushHistory();
    });
    regions.on("region-updated", () => {
      // Coalescer una edición (drag/resize) en una sola entrada de historial.
      if (histTimerRef.current != null) window.clearTimeout(histTimerRef.current);
      histTimerRef.current = window.setTimeout(() => { pushHistory(); }, 350);
      rerender();
    });
    regions.on("region-clicked", (r: Region, e: MouseEvent) => {
      e.stopPropagation();
      selectRegion(r.id);
    });

    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));
    ws.on("ready", () => { setReady(true); seedOrRestore(); });
    ws.on("timeupdate", (t: number) => {
      setCurrentT(t);
      const stopAt = stopAtRef.current;
      if (stopAt != null && t >= stopAt) { ws.pause(); stopAtRef.current = null; }
    });

    const v = videoRef.current;
    const onMeta = () => {
      seedOrRestore();
      // Poster: mostrar un frame en vez de negro.
      if (v.currentTime < 0.05) {
        try { v.currentTime = Math.min(1, (v.duration || duration || 2) / 2); } catch {}
      }
    };
    v.addEventListener("loadedmetadata", onMeta);
    if (v.readyState >= 1) onMeta();

    return () => {
      v.removeEventListener("loadedmetadata", onMeta);
      ws.destroy();
      wsRef.current = null;
      regionsRef.current = null;
      initedRef.current = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoUrl]);

  // Cue activo según el playhead (búsqueda binaria) + auto-scroll del transcript.
  useEffect(() => {
    if (!cues.length) return;
    let lo = 0, hi = cues.length - 1, idx = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (cues[mid].start <= currentT) { idx = mid; lo = mid + 1; } else hi = mid - 1;
    }
    if (idx !== activeCue) {
      setActiveCue(idx);
      const cont = transcriptRef.current;
      if (cont) {
        const el = cont.querySelector<HTMLElement>(`[data-idx="${idx}"]`);
        if (el) cont.scrollTop = el.offsetTop - cont.clientHeight / 2 + el.clientHeight / 2;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentT]);

  useEffect(() => { Streamlit.setFrameHeight(); });
  useEffect(() => {
    const onResize = () => Streamlit.setFrameHeight();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // ── Acciones ────────────────────────────────────────────────────────────────
  const getSelected = (): Region | null =>
    selectedId ? regionsRef.current?.getRegions().find((r) => r.id === selectedId) || null : null;

  const currentTime = (): number =>
    wsRef.current?.getCurrentTime() || videoRef.current?.currentTime || 0;

  const seek = (t: number) => {
    const dur = wsRef.current?.getDuration() || duration || 0;
    const nt = Math.max(0, Math.min(dur || t, t));
    wsRef.current?.setTime(nt);
    if (videoRef.current) videoRef.current.currentTime = nt;
  };

  const addRegionAt = (start: number, end: number, select = true): Region | null => {
    const regions = regionsRef.current;
    if (!regions) return null;
    const dur = wsRef.current?.getDuration() || duration || 0;
    const s = Math.max(0, start);
    const e = dur ? Math.min(dur, Math.max(s + 1, end)) : Math.max(s + 1, end);
    const r = regions.addRegion({ start: s, end: e, drag: true, resize: true, color: REGION_COLOR });
    ensureMeta(r.id);
    if (select) selectRegion(r.id);
    return r;
  };

  const addRegion = () => {
    const t = snapTime(currentTime());
    addRegionAt(t, t + 30);
    setStatus("Corte agregado");
  };

  const markIn = () => {
    const r = getSelected();
    if (!r) { addRegion(); return; }
    r.setOptions({ start: snapTime(Math.min(currentTime(), r.end - 0.2)), end: r.end });
    pushHistory();
  };

  const markOut = () => {
    const r = getSelected();
    if (!r) return;
    r.setOptions({ start: r.start, end: snapTime(Math.max(currentTime(), r.start + 0.2)) });
    pushHistory();
  };

  const snapEdges = () => {
    const r = getSelected();
    if (!r) return;
    r.setOptions({ start: snapTime(r.start), end: snapTime(r.end) });
    pushHistory();
    setStatus("Pegado a frases");
  };

  const deleteRegion = () => {
    const r = getSelected();
    if (!r) return;
    metaRef.current.delete(r.id);
    r.remove();
    setSelectedId(null);
    pushHistory();
    setStatus("Corte eliminado");
  };

  const togglePlay = () => { stopAtRef.current = null; wsRef.current?.playPause(); };

  const playRange = (start: number, end: number) => {
    const ws = wsRef.current;
    if (!ws) return;
    ws.setTime(start);
    stopAtRef.current = end;
    ws.play();
  };

  const playRegion = () => {
    const r = getSelected();
    if (!r) { togglePlay(); return; }
    playRange(r.start, r.end);
  };

  const resetToSeed = () => {
    try { window.localStorage.removeItem(lsKey); } catch {}
    const dur = wsRef.current?.getDuration() || duration || 0;
    const snap = initialClips.map((cl) => ({
      start: Math.max(0, cl.start),
      end: Math.min(dur, Math.max(cl.start + 1, cl.end)),
      title: cl.title || "", type: cl.type || types[0] || "insight",
    }));
    restore(snap);
    histRef.current = [snap]; histIdxRef.current = 0;
    setStatus("Reiniciado a la selección original");
  };

  // Zoom
  const applyZoom = (px: number) => {
    const p = Math.max(1, px);
    setPxPerSec(p);
    try { wsRef.current?.zoom(p); } catch {}
  };
  const zoomIn = () => applyZoom((pxPerSec || 4) * 1.6);
  const zoomOut = () => applyZoom(Math.max(1, (pxPerSec || 4) / 1.6));
  const zoomFit = () => { setPxPerSec(0); try { wsRef.current?.zoom(1); } catch {} };

  // Crear corte desde selección de texto del transcript.
  const onTranscriptMouseUp = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !transcriptRef.current) return;
    const within = (n: Node | null) =>
      n && transcriptRef.current!.contains(n.nodeType === 1 ? n : n.parentNode);
    if (!within(sel.anchorNode) || !within(sel.focusNode)) return;
    const cueEl = (n: Node | null): HTMLElement | null => {
      let el = (n && (n.nodeType === 1 ? (n as HTMLElement) : n.parentElement)) || null;
      while (el && !el.dataset.idx) el = el.parentElement;
      return el;
    };
    const a = cueEl(sel.anchorNode), b = cueEl(sel.focusNode);
    if (!a || !b) return;
    const ia = +a.dataset.idx!, ib = +b.dataset.idx!;
    const lo = Math.min(ia, ib), hi = Math.max(ia, ib);
    const start = cues[lo].start, end = cues[hi].end;
    sel.removeAllRanges();
    const r = addRegionAt(start, end);
    if (r) playRange(r.start, r.end); // reproducir el fragmento recién creado
    setStatus("Corte creado desde el transcript — reproduciendo");
  };

  const apply = () => {
    const out = snapshot()
      .map((cl) => ({
        start: Math.round(cl.start * 100) / 100,
        end: Math.round(cl.end * 100) / 100,
        title: cl.title, type: cl.type,
      }))
      .filter((cl) => cl.end - cl.start >= 0.5);
    Streamlit.setComponentValue(out);
    setStatus(`✓ ${out.length} corte(s) enviados`);
  };

  // Atajos de teclado
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA")) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); redo(); return; }
      switch (e.key) {
        case " ": case "k": e.preventDefault(); togglePlay(); break;
        case "i": case "I": markIn(); break;
        case "o": case "O": markOut(); break;
        case "ArrowLeft": e.preventDefault(); seek(currentTime() - 5); break;
        case "ArrowRight": e.preventDefault(); seek(currentTime() + 5); break;
        case "j": case "J": seek(currentTime() - 10); break;
        case "l": case "L": seek(currentTime() + 10); break;
        case "Delete": case "Backspace": deleteRegion(); break;
        default: break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, pxPerSec]);

  const selected = getSelected();
  const selMeta = selected ? ensureMeta(selected.id) : null;
  const regionCount = regionsRef.current?.getRegions().length || 0;
  const canUndo = histIdxRef.current > 0;
  const canRedo = histIdxRef.current < histRef.current.length - 1;

  // ── Estilos ─────────────────────────────────────────────────────────────────
  const c = {
    fg: dark ? "#e6e6e6" : "#1a1a1a",
    sub: dark ? "#9aa7b2" : "#5a6a76",
    panel: dark ? "#1c2530" : "#f4f7fa",
    border: dark ? "#33414f" : "#d6dee6",
    accent: "#4a90d9",
    hi: dark ? "rgba(74,144,217,0.28)" : "rgba(74,144,217,0.18)",
  };
  const btn: React.CSSProperties = {
    background: c.panel, color: c.fg, border: `1px solid ${c.border}`,
    borderRadius: 6, padding: "6px 11px", fontSize: 13, cursor: "pointer", fontFamily: "inherit",
  };
  const btnP: React.CSSProperties = { ...btn, background: c.accent, color: "#fff", border: "none", fontWeight: 600 };
  const inp: React.CSSProperties = {
    padding: "7px 10px", borderRadius: 6, border: `1px solid ${c.border}`,
    background: dark ? "#0f1620" : "#fff", color: c.fg, fontSize: 13,
  };

  return (
    <div style={{ fontFamily: "Inter, system-ui, sans-serif", color: c.fg, padding: 4 }}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: "2 1 420px", minWidth: 320 }}>
          <video ref={videoRef} src={videoUrl} playsInline controls preload="metadata"
            style={{ width: "100%", maxHeight: 300, background: "#000", borderRadius: 8, display: "block" }} />
        </div>

        {/* Transcript */}
        <div style={{ flex: "1 1 260px", minWidth: 240 }}>
          <div style={{ fontSize: 12, color: c.sub, marginBottom: 4 }}>
            📝 Transcript — clic para saltar · seleccioná texto para crear un corte
          </div>
          <div
            ref={transcriptRef}
            onMouseUp={onTranscriptMouseUp}
            style={{
              height: 288, overflowY: "auto", border: `1px solid ${c.border}`,
              borderRadius: 8, padding: 6, background: c.panel, fontSize: 13, lineHeight: 1.4,
            }}
          >
            {cues.length === 0 ? (
              <div style={{ color: c.sub }}>Sin transcript disponible.</div>
            ) : cues.map((q, i) => (
              <div
                key={i}
                data-idx={i}
                onClick={() => seek(q.start)}
                style={{
                  cursor: "pointer",
                  display: "flex",
                  gap: 8,
                  padding: "3px 6px",
                  marginBottom: 5,
                  borderRadius: 6,
                  background: i === activeCue ? c.hi : "transparent",
                  borderLeft: `3px solid ${i === activeCue ? c.accent : "transparent"}`,
                }}
              >
                <button
                  onClick={(e) => { e.stopPropagation(); playRange(q.start, q.end); }}
                  title="Reproducir esta frase"
                  style={{
                    flexShrink: 0, background: "transparent", border: "none", cursor: "pointer",
                    color: c.sub, fontSize: 11, padding: 0, fontFamily: "inherit",
                    minWidth: 44, textAlign: "left", fontVariantNumeric: "tabular-nums",
                  }}
                >
                  ▶ {fmtClock(q.start)}
                </button>
                <span style={{ flex: 1 }}>{q.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div ref={waveRef} style={{ marginTop: 10 }} />

      {/* Barra de tiempo + zoom */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: 12, color: c.sub }}>
        <span>⏱ {fmtTime(currentT)} / {fmtTime(duration)}</span>
        <div style={{ flex: 1 }} />
        <span>Zoom</span>
        <button style={btn} onClick={zoomOut}>−</button>
        <button style={btn} onClick={zoomFit}>Fit</button>
        <button style={btn} onClick={zoomIn}>＋</button>
      </div>

      {/* Toolbar */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
        <button style={btn} onClick={togglePlay}>{playing ? "⏸ Pausa" : "▶ Play"}</button>
        <button style={btn} onClick={markIn} title="Fijar inicio (I)">⇤ IN</button>
        <button style={btn} onClick={markOut} title="Fijar fin (O)">OUT ⇥</button>
        <button style={btn} onClick={addRegion}>＋ Añadir</button>
        <button style={btn} onClick={playRegion} disabled={!selected}>▶ Corte</button>
        <button style={btn} onClick={snapEdges} disabled={!selected} title="Pegar bordes a frases">🧲 Frases</button>
        <button style={btn} onClick={deleteRegion} disabled={!selected}>🗑</button>
        <button style={btn} onClick={undo} disabled={!canUndo} title="Deshacer (Ctrl+Z)">↶</button>
        <button style={btn} onClick={redo} disabled={!canRedo} title="Rehacer (Ctrl+Y)">↷</button>
        <button style={btn} onClick={resetToSeed} title="Volver a la selección original">↺</button>
        <div style={{ flex: 1 }} />
        <button style={btnP} onClick={apply}>✓ Aplicar {regionCount} cortes</button>
      </div>

      {warnings.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: "#e0894a" }}>
          ⚠️ {warnings.join(" · ")}
        </div>
      )}

      <div style={{ fontSize: 12, color: c.sub, marginTop: 6 }}>
        {ready ? "Arrastrá sobre la onda para crear un corte; arrastrá los bordes para ajustar. " : "Cargando video… "}
        {status}
      </div>

      {selected && selMeta ? (
        <div style={{ marginTop: 12, padding: 12, background: c.panel, border: `1px solid ${c.border}`, borderRadius: 8 }}>
          <div style={{ fontSize: 12, color: c.sub, marginBottom: 8 }}>
            Corte · {fmtTime(selected.start)} → {fmtTime(selected.end)} · {fmtTime(selected.end - selected.start)}
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input value={selMeta.title} placeholder="Título del corte"
              onChange={(e) => { selMeta.title = e.target.value; saveLocal(snapshot()); rerender(); }}
              style={{ ...inp, flex: 3, minWidth: 200 }} />
            <select value={selMeta.type}
              onChange={(e) => { selMeta.type = e.target.value; saveLocal(snapshot()); rerender(); }}
              style={{ ...inp, flex: 1, minWidth: 120 }}>
              {types.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 12, fontSize: 13, color: c.sub }}>
          {regionCount === 0
            ? "No hay cortes. Arrastrá sobre la onda, seleccioná texto del transcript, o usá “Añadir”."
            : "Seleccioná un corte para editar su título y tipo."}
        </div>
      )}
    </div>
  );
};

const ClipEditor = withStreamlitConnection(ClipEditorRaw);
export default ClipEditor;
