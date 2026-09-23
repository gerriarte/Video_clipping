/** Tokens de estilo y helpers de tiempo, compartidos. Sin React, sin host. */
import type { Theme } from "./types";

export const FALLBACK_THEME: Theme = {
  base: "dark",
  primaryColor: "#ff4b4b",
  backgroundColor: "#0e1117",
  secondaryBackgroundColor: "#262730",
  textColor: "#fafafa",
  font: "sans-serif",
};

export interface Tokens {
  bg: string;
  card: string;
  cardHover: string;
  border: string;
  borderStrong: string;
  text: string;
  sub: string;
  primary: string;
  ok: string;
  warn: string;
  font: string;
  radius: number;
  shadow: string;
}

export function tokens(theme: Theme | undefined): Tokens {
  const t = theme || FALLBACK_THEME;
  const dark = t.base !== "light";
  return {
    bg: "transparent",
    card: t.secondaryBackgroundColor,
    cardHover: dark ? "#31333f" : "#eceff3",
    border: dark ? "rgba(250,250,250,0.10)" : "rgba(15,17,23,0.10)",
    borderStrong: dark ? "rgba(250,250,250,0.26)" : "rgba(15,17,23,0.26)",
    text: t.textColor,
    sub: dark ? "rgba(250,250,250,0.55)" : "rgba(15,17,23,0.55)",
    primary: t.primaryColor,
    ok: "#2bb673",
    warn: "#e8a33d",
    font: t.font || FALLBACK_THEME.font,
    radius: 10,
    shadow: dark
      ? "0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.28)"
      : "0 1px 2px rgba(15,17,23,.06), 0 8px 24px rgba(15,17,23,.08)",
  };
}

/** 97.1 → "1:37". Timecode, no segundos con decimales. */
export function clock(s: number): string {
  if (!isFinite(s) || s < 0) s = 0;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return `${h ? h + ":" : ""}${mm}:${String(sec).padStart(2, "0")}`;
}

/** Duración corta: "1:06". */
export const dur = (a: number, b: number) => clock(Math.max(0, b - a));

/** Suma de duraciones en "12 min 30 s". */
export function totalLabel(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (!m) return `${s} s`;
  return s ? `${m} min ${s} s` : `${m} min`;
}
