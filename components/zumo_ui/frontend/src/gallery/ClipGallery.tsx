/**
 * La galeria de clips: una grilla de tarjetas en vez de una planilla.
 *
 * React puro. No sabe si atras hay Streamlit o una API: recibe `args` y avisa
 * por `onCommit` / `onHeight`. Toda la atadura al host vive en bridge.*.ts.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Clip, ClipPatch, GalleryAction, GalleryArgs, GalleryValue, Theme } from "./types";
import { ClipCard } from "./ClipCard";
import { FormatGlyph } from "../Crop";
import { tokens, totalLabel, type Tokens } from "../theme";

export interface GalleryProps {
  args: GalleryArgs;
  theme?: Theme;
  onCommit: (value: GalleryValue) => void;
  onHeight: (px: number) => void;
}

/** Firma de lo editable: sirve para saber si el host mando datos distintos. */
const signature = (clips: Clip[]): string =>
  clips
    .map((c) =>
      [c.id, c.title, c.start, c.end, c.type, c.selected, c.format, c.speakerFollow, c.followShot].join("|"),
    )
    .join("\n");

const toPatch = (c: Clip): ClipPatch => ({
  id: c.id,
  title: c.title,
  start: c.start,
  end: c.end,
  type: c.type,
  selected: c.selected,
  format: c.format,
  speakerFollow: c.speakerFollow,
  followShot: c.followShot,
});

export const ClipGallery: React.FC<GalleryProps> = ({ args, theme, onCommit, onHeight }) => {
  const t = tokens(theme);
  const incoming = args.clips || [];

  const [clips, setClipsState] = useState<Clip[]>(incoming);
  const [query, setQuery] = useState("");
  const [onlyPicked, setOnlyPicked] = useState(false);
  const [focused, setFocused] = useState<number>(incoming[0]?.id ?? 0);
  const rootRef = useRef<HTMLDivElement>(null);

  // El estado vive tambien en un ref: los handlers necesitan leer el valor de
  // AHORA sin esperar al proximo render (y sin colar efectos dentro de un
  // updater de useState).
  const clipsRef = useRef<Clip[]>(incoming);
  // Arranca en el reloj, no en 0: si el componente se vuelve a montar (p. ej.
  // al volver del editor de timeline) y el usuario repite la misma accion,
  // un contador desde 0 daria el MISMO nonce que la vez anterior y el host
  // la descartaria por repetida.
  const focusedRef = useRef<number>(focused);
  const nonceRef = useRef(Date.now());
  /** Firma del ultimo commit del que todavia esperamos el eco del host. */
  const pendingRef = useRef<string | null>(null);
  /** Ecos que llegaron sin coincidir: si son muchos, algo se desincronizo. */
  const missesRef = useRef(0);

  const setClips = useCallback((next: Clip[]) => {
    clipsRef.current = next;
    setClipsState(next);
  }, []);

  /**
   * Los datos del host mandan, salvo mientras hay un commit en vuelo.
   *
   * Sin esa salvedad, dos clics seguidos pierden el segundo: el host todavia
   * esta contestando al primero, y ese eco viejo llega DESPUES del segundo
   * clic y lo pisa. Esperamos a ver de vuelta lo que mandamos antes de volver
   * a aceptar datos de afuera.
   */
  useEffect(() => {
    const fresh = args.clips || [];
    const sig = signature(fresh);

    const mergeAnalysis = () =>
      setClips(
        clipsRef.current.map((p) => {
          const f = fresh.find((c) => c.id === p.id);
          return f ? { ...p, thumbs: f.thumbs, shot: f.shot, reason: f.reason } : p;
        }),
      );

    if (pendingRef.current !== null) {
      if (sig === pendingRef.current) {
        pendingRef.current = null;
        missesRef.current = 0;
      } else if (missesRef.current < 3) {
        missesRef.current += 1;
        mergeAnalysis(); // llego un eco viejo: nos quedamos con lo nuestro
        return;
      } else {
        pendingRef.current = null; // nos desincronizamos: manda el host
        missesRef.current = 0;
      }
    }

    if (sig !== signature(clipsRef.current)) setClips(fresh);
    else mergeAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [args]);

  const commit = useCallback(
    (list: Clip[], action: GalleryAction = null, sel = focusedRef.current) => {
      pendingRef.current = signature(list);
      missesRef.current = 0;
      nonceRef.current += 1;
      onCommit({ clips: list.map(toPatch), selected: sel, action, nonce: nonceRef.current });
    },
    [onCommit],
  );

  const change = useCallback(
    (id: number, patch: Partial<Clip>, doCommit: boolean) => {
      const next = clipsRef.current.map((c) => (c.id === id ? { ...c, ...patch } : c));
      setClips(next);
      if (doCommit) commit(next);
    },
    [commit, setClips],
  );

  const focus = useCallback(
    (id: number) => {
      if (id === focusedRef.current) return;
      focusedRef.current = id;
      setFocused(id);
      // Avisarle al host cuesta un rerun entero, así que solo se hace cuando
      // el host dibuja algo para el clip en foco — o sea, cuando no se eligen
      // clips (Paso 4, donde abajo va el encuadre del clip en foco).
      if (!args.pickable) commit(clipsRef.current, null, id);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [commit, args.pickable],
  );

  const applyAll = useCallback(
    (fn: (c: Clip) => Clip) => {
      const next = clipsRef.current.map(fn);
      setClips(next);
      commit(next);
    },
    [commit, setClips],
  );

  // El iframe no se autodimensiona: hay que decirle cuanto mide el contenido.
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const report = () => onHeight(Math.ceil(el.getBoundingClientRect().height) + 8);
    report();
    const ro = new ResizeObserver(report);
    ro.observe(el);
    return () => ro.disconnect();
  }, [onHeight]);

  const picked = clips.filter((c) => c.selected);
  const pickedSeconds = picked.reduce((a, c) => a + Math.max(0, c.end - c.start), 0);
  const pending = clips.filter((c) => c.shot?.suggestion && c.shot.suggestion !== c.format);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return clips.filter((c) => {
      if (onlyPicked && !c.selected) return false;
      if (!q) return true;
      return (c.title + " " + c.reason).toLowerCase().includes(q);
    });
  }, [clips, query, onlyPicked]);

  const formats = args.formats || [];
  const srcAspect = args.sourceAspect && args.sourceAspect > 0 ? args.sourceAspect : 16 / 9;

  return (
    <div
      ref={rootRef}
      style={{
        font: `14px ${t.font}`,
        color: t.text,
        background: t.bg,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      {/* Barra de acciones */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
          padding: "9px 12px", borderRadius: t.radius,
          background: t.card, border: `1px solid ${t.border}`,
        }}
      >
        <strong style={{ fontSize: 13.5 }}>
          {args.pickable ? `${picked.length} de ${clips.length} clips` : `${clips.length} clips`}
        </strong>
        <span style={{ fontSize: 12, color: t.sub }}>{totalLabel(pickedSeconds)} de video</span>

        {args.pickable && (
          <>
            <span style={{ width: 1, height: 18, background: t.border }} />
            <Btn t={t} onClick={() => applyAll((c) => ({ ...c, selected: true }))}>Todos</Btn>
            <Btn t={t} onClick={() => applyAll((c) => ({ ...c, selected: false }))}>Ninguno</Btn>
          </>
        )}
        {pending.length > 0 && (
          <Btn
            t={t}
            accent
            title="Poner en cada clip el formato que sugiere el analisis de la toma"
            onClick={() => applyAll((c) => (c.shot?.suggestion ? { ...c, format: c.shot.suggestion } : c))}
          >
            {"★"} Aplicar {pending.length} sugerencia{pending.length === 1 ? "" : "s"}
          </Btn>
        )}

        <span style={{ flex: 1 }} />

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar en titulos y razones"
          style={{
            font: "inherit", fontSize: 12, color: t.text, width: 190,
            background: "rgba(127,127,127,0.12)", border: `1px solid ${t.border}`,
            borderRadius: 7, padding: "5px 9px", outline: "none",
          }}
        />
        {args.pickable && (
          <Btn t={t} active={onlyPicked} onClick={() => setOnlyPicked((v) => !v)}>
            solo elegidos
          </Btn>
        )}
        {args.showTimeline && (
          <Btn t={t} title="Ajustar estos cortes en el editor de timeline"
               onClick={() => commit(clipsRef.current, "timeline")}>
            {"✂"} Timeline
          </Btn>
        )}
      </div>

      {/* Leyenda del recorte: que significa el marco sobre la foto */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: t.sub, flexWrap: "wrap" }}>
        <span>El marco sobre la foto es lo que se queda el formato; lo apagado se descarta.</span>
        {formats.map((f) => (
          <span key={f.key} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <FormatGlyph fmt={f} color={t.sub} />
            {f.label}
          </span>
        ))}
      </div>

      {/* Grilla */}
      {visible.length === 0 ? (
        <div style={{ padding: 28, textAlign: "center", color: t.sub, fontSize: 13 }}>
          Ningun clip coincide con el filtro.
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(268px, 1fr))",
            gap: 12,
            alignItems: "stretch",
          }}
        >
          {visible.map((c) => (
            <ClipCard
              key={c.id}
              clip={c}
              formats={formats}
              types={args.types || []}
              videoUrl={args.videoUrl}
              sourceAspect={srcAspect}
              t={t}
              pickable={args.pickable !== false}
              focused={!args.pickable && c.id === focused}
              onChange={change}
              onFocus={focus}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const Btn: React.FC<{
  t: Tokens;
  onClick: () => void;
  children: React.ReactNode;
  accent?: boolean;
  active?: boolean;
  title?: string;
}> = ({ t, onClick, children, accent, active, title }) => (
  <button
    onClick={onClick}
    title={title}
    style={{
      font: "inherit", fontSize: 12, cursor: "pointer", whiteSpace: "nowrap",
      padding: "5px 10px", borderRadius: 7, lineHeight: 1.3,
      background: active ? t.primary : accent ? "rgba(232,163,61,0.14)" : "transparent",
      color: active ? "#fff" : accent ? t.warn : t.sub,
      border: `1px solid ${active ? t.primary : accent ? "rgba(232,163,61,0.45)" : t.border}`,
    }}
  >
    {children}
  </button>
);
