/**
 * Paso 5: elegir un clip y dejar sus textos listos para publicar.
 *
 * Antes eran 20 expanders abiertos a la vez (31,5 pantallas de scroll y 20
 * <video> cargados al mismo tiempo). Ahora es lista + detalle: una sola tarjeta
 * abierta, un solo video cargado, y la lista como mapa del episodio.
 *
 * React puro: props y callbacks. La atadura al host vive en bridge.*.ts.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PublishArgs, PublishClip, PublishValue } from "./types";
import type { Theme } from "../types";
import { FormatGlyph } from "../Crop";
import { clock, tokens, type Tokens } from "../theme";

export interface PublishProps {
  args: PublishArgs;
  theme?: Theme;
  onCommit: (value: PublishValue) => void;
  onHeight: (px: number) => void;
}

/** Firma de lo editable: sirve para saber si el host mandó datos distintos. */
const signature = (clips: PublishClip[]): string =>
  clips
    .map((c) => [c.id, c.format, JSON.stringify(c.captions)].join("|"))
    .join("\n");

const toPatch = (c: PublishClip) => ({ id: c.id, format: c.format, captions: c.captions });

export const ClipPublish: React.FC<PublishProps> = ({ args, theme, onCommit, onHeight }) => {
  const t = tokens(theme);
  const incoming = args.clips || [];

  const [clips, setClipsState] = useState<PublishClip[]>(incoming);
  const [selected, setSelected] = useState<number>(incoming[0]?.id ?? 0);
  /** Ultimo intento de copiado: que boton, y si funciono. */
  const [copied, setCopied] = useState<{ key: string; ok: boolean } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const clipsRef = useRef<PublishClip[]>(incoming);
  const selectedRef = useRef<number>(selected);
  const nonceRef = useRef(Date.now());
  const pendingRef = useRef<string | null>(null);
  const missesRef = useRef(0);

  const setClips = useCallback((next: PublishClip[]) => {
    clipsRef.current = next;
    setClipsState(next);
  }, []);

  // Mismo criterio que la galería: los datos del host mandan, salvo mientras
  // hay un commit en vuelo — su eco viejo pisaría lo que el usuario acaba de
  // escribir. Ver el comentario largo en gallery/ClipGallery.tsx.
  useEffect(() => {
    const fresh = args.clips || [];
    const sig = signature(fresh);

    const mergeMedia = () =>
      setClips(
        clipsRef.current.map((p) => {
          const f = fresh.find((c) => c.id === p.id);
          return f ? { ...p, videoUrl: f.videoUrl, coverUrl: f.coverUrl, aspect: f.aspect } : p;
        }),
      );

    if (pendingRef.current !== null) {
      if (sig === pendingRef.current) {
        pendingRef.current = null;
        missesRef.current = 0;
      } else if (missesRef.current < 3) {
        missesRef.current += 1;
        mergeMedia();
        return;
      } else {
        pendingRef.current = null;
        missesRef.current = 0;
      }
    }

    if (sig !== signature(clipsRef.current)) setClips(fresh);
    else mergeMedia();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args]);

  const commit = useCallback(
    (list: PublishClip[], action: PublishValue["action"] = null, sel = selectedRef.current) => {
      pendingRef.current = signature(list);
      missesRef.current = 0;
      nonceRef.current += 1;
      onCommit({ clips: list.map(toPatch), selected: sel, action, nonce: nonceRef.current });
    },
    [onCommit],
  );

  const change = useCallback(
    (id: number, patch: Partial<PublishClip>, doCommit: boolean) => {
      const next = clipsRef.current.map((c) => (c.id === id ? { ...c, ...patch } : c));
      setClips(next);
      if (doCommit) commit(next);
    },
    [commit, setClips],
  );

  const select = useCallback(
    (id: number) => {
      selectedRef.current = id;
      setSelected(id);
      commit(clipsRef.current, null, id);
    },
    [commit],
  );

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const report = () => onHeight(Math.ceil(el.getBoundingClientRect().height) + 8);
    report();
    const ro = new ResizeObserver(report);
    ro.observe(el);
    return () => ro.disconnect();
  }, [onHeight]);

  const current = useMemo(
    () => clips.find((c) => c.id === selected) || clips[0],
    [clips, selected],
  );
  const platforms = args.platforms || [];
  const formats = args.formats || [];

  /**
   * Copiar al portapapeles, por el camino sincrono.
   *
   * `navigator.clipboard.writeText` parece lo correcto, pero dentro de un
   * iframe que no tiene el foco la promesa NO se resuelve ni se rechaza: se
   * queda colgada. Si el aviso de "copiado" cuelga de ese await, nunca llega.
   * El textarea + execCommand es viejo pero es sincrono y devuelve si funciono;
   * la API moderna queda de respaldo, sin bloquear el aviso.
   */
  const copy = useCallback((key: string, text: string) => {
    let ok = false;
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.top = "0";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      ok = document.execCommand("copy");
      document.body.removeChild(ta);
    } catch {
      ok = false;
    }
    if (!ok) {
      // Solo pasa si el documento no tiene el foco, que despues de un clic no
      // deberia pasar. Se intenta igual, pero el boton no dice que copio algo
      // que quiza no copio: el texto esta ahi para seleccionarlo a mano.
      try { void navigator.clipboard?.writeText(text); } catch { /* sin portapapeles */ }
    }
    setCopied({ key, ok });
    setTimeout(() => setCopied(null), 1800);
  }, []);

  const move = useCallback(
    (delta: number) => {
      const i = clips.findIndex((c) => c.id === selectedRef.current);
      const next = clips[Math.min(Math.max(i + delta, 0), clips.length - 1)];
      if (next && next.id !== selectedRef.current) select(next.id);
    },
    [clips, select],
  );

  if (!current) {
    return <div style={{ font: `14px ${t.font}`, color: t.sub, padding: 24 }}>No hay clips todavía.</div>;
  }

  const sinVideo = !current.videoUrl;

  return (
    <div
      ref={rootRef}
      style={{ font: `14px ${t.font}`, color: t.text, display: "flex", gap: 14, alignItems: "flex-start" }}
    >
      {/* ── Lista: el mapa del episodio ──────────────────────────────────── */}
      <div
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
          if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
        }}
        style={{
          width: 250, flex: "0 0 250px", maxHeight: 620, overflowY: "auto",
          display: "flex", flexDirection: "column", gap: 6, paddingRight: 4, outline: "none",
        }}
      >
        {clips.map((c) => {
          const on = c.id === current.id;
          return (
            <button
              key={c.id}
              onClick={() => select(c.id)}
              title={c.title}
              style={{
                display: "flex", gap: 9, alignItems: "center", textAlign: "left", cursor: "pointer",
                padding: 7, borderRadius: 9, font: "inherit", width: "100%",
                background: on ? t.card : "transparent",
                border: `1px solid ${on ? t.primary : "transparent"}`,
                color: t.text,
              }}
            >
              <span
                style={{
                  width: 34, height: 46, flex: "0 0 34px", borderRadius: 5, overflow: "hidden",
                  background: "#05070b", display: "grid", placeItems: "center",
                }}
              >
                {c.coverUrl ? (
                  <img src={c.coverUrl} alt="" loading="lazy"
                       style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <span style={{ fontSize: 9, color: t.sub }}>—</span>
                )}
              </span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span
                  style={{
                    display: "block", fontSize: 12, fontWeight: on ? 600 : 400, lineHeight: 1.3,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}
                >
                  <span style={{ color: t.sub, fontVariantNumeric: "tabular-nums" }}>{c.index}.</span>{" "}
                  {c.title}
                </span>
                <span style={{ display: "block", fontSize: 10.5, color: t.sub, marginTop: 2 }}>
                  {clock(c.duration)} · {formats.find((f) => f.key === c.format)?.short || c.format}
                  {!c.videoUrl && <span style={{ color: t.warn }}> · sin render</span>}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* ── Detalle: un clip por vez ─────────────────────────────────────── */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div
            style={{
              height: 360, aspectRatio: String(current.aspect || 9 / 16),
              borderRadius: 10, overflow: "hidden", background: "#05070b", flex: "0 0 auto",
              border: `1px solid ${t.border}`, display: "grid", placeItems: "center",
            }}
          >
            {sinVideo ? (
              <span style={{ fontSize: 12, color: t.sub, padding: 12, textAlign: "center" }}>
                Este clip todavía no tiene render.
              </span>
            ) : (
              <video
                key={current.videoUrl}
                src={current.videoUrl}
                poster={current.coverUrl || undefined}
                controls
                playsInline
                preload="metadata"
                style={{ width: "100%", height: "100%", objectFit: "contain", background: "#000" }}
              />
            )}
          </div>

          <div style={{ flex: 1, minWidth: 260, display: "flex", flexDirection: "column", gap: 9 }}>
            <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.3 }}>
              <span style={{ color: t.sub }}>Clip {current.index} · </span>
              {current.title}
            </div>
            <div style={{ fontSize: 11.5, color: t.sub, fontVariantNumeric: "tabular-nums" }}>
              {clock(current.start)} {"→"} {clock(current.end)} · dura {clock(current.duration)} · {current.type}
            </div>
            {current.reason && (
              <div style={{ fontSize: 11.5, color: t.sub, lineHeight: 1.5 }}>{current.reason}</div>
            )}

            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 2 }}>
              {formats.map((f) => {
                const active = f.key === current.format;
                return (
                  <button
                    key={f.key}
                    onClick={() => change(current.id, { format: f.key }, true)}
                    title={f.label}
                    style={{
                      display: "flex", alignItems: "center", gap: 5, cursor: "pointer",
                      padding: "4px 7px", borderRadius: 7, fontSize: 11, lineHeight: 1, height: 26,
                      font: "inherit", fontWeight: active ? 600 : 400, whiteSpace: "nowrap",
                      background: active ? t.primary : "transparent",
                      color: active ? "#fff" : t.sub,
                      border: `1px solid ${active ? t.primary : t.border}`,
                    }}
                  >
                    <FormatGlyph fmt={f} color={active ? "#fff" : t.sub} />
                    {f.short}
                  </button>
                );
              })}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
              <button
                onClick={() => commit(clipsRef.current, { kind: "rerender", id: current.id })}
                style={{
                  font: "inherit", fontSize: 12, cursor: "pointer", padding: "6px 12px",
                  borderRadius: 7, background: "transparent", color: t.text,
                  border: `1px solid ${t.borderStrong}`,
                }}
              >
                Re-renderizar este clip
              </button>
              <span style={{ fontSize: 11, color: t.sub }}>
                Cambiar el formato no requiere volver a cortar.
              </span>
            </div>
          </div>
        </div>

        {/* ── Textos, uno por plataforma ─────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 10 }}>
          {platforms.map((p) => {
            const text = current.captions?.[p.key] ?? "";
            const key = `${current.id}:${p.key}`;
            return (
              <div
                key={p.key}
                style={{
                  background: t.card, border: `1px solid ${t.border}`, borderRadius: t.radius,
                  padding: 10, display: "flex", flexDirection: "column", gap: 7,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <strong style={{ fontSize: 12.5 }}>{p.label}</strong>
                  <span style={{ fontSize: 10.5, color: t.sub, fontVariantNumeric: "tabular-nums" }}>
                    {text.length} caracteres
                  </span>
                  <span style={{ flex: 1 }} />
                  <Copiar t={t} estado={copied?.key === key ? copied : null} onClick={() => copy(key, text)} />
                </div>
                <textarea
                  value={text}
                  onChange={(e) =>
                    change(current.id, { captions: { ...current.captions, [p.key]: e.target.value } }, false)
                  }
                  onBlur={() => commit(clipsRef.current)}
                  spellCheck={false}
                  style={{
                    font: "inherit", fontSize: 12, lineHeight: 1.5, color: t.text, resize: "vertical",
                    minHeight: 120, background: "rgba(127,127,127,0.10)",
                    border: `1px solid ${t.border}`, borderRadius: 7, padding: 8, outline: "none",
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

/** El boton de copiar, que dice lo que de verdad paso. */
const Copiar: React.FC<{
  t: Tokens;
  estado: { key: string; ok: boolean } | null;
  onClick: () => void;
}> = ({ t, estado, onClick }) => {
  const color = estado ? (estado.ok ? t.ok : t.warn) : null;
  return (
    <button
      onClick={onClick}
      title={estado && !estado.ok ? "No se pudo acceder al portapapeles: seleccioná el texto y copialo a mano." : "Copiar el texto"}
      style={{
        font: "inherit", fontSize: 11, cursor: "pointer", padding: "3px 9px",
        borderRadius: 6, whiteSpace: "nowrap",
        background: color || "transparent",
        color: color ? "#fff" : t.sub,
        border: `1px solid ${color || t.border}`,
      }}
    >
      {estado ? (estado.ok ? "copiado" : "no se pudo") : "copiar"}
    </button>
  );
};
