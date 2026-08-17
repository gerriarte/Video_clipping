import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  random,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as loadCaveat } from "@remotion/google-fonts/Caveat";
import { loadFont as loadGochi } from "@remotion/google-fonts/GochiHand";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";

const { fontFamily: caveat } = loadCaveat();
const { fontFamily: gochi } = loadGochi();
const { fontFamily: inter } = loadInter();
const { fontFamily: mono } = loadMono();

/** Escena de apertura: 3.5 s = 105 frames a 30 fps. Sin audio: la música y la
 *  voz se montan después. Todo el dibujo es CSS/SVG, sin imágenes externas.
 *
 *  Las medidas viven en pieces.meta.ts para que Root.tsx pueda registrar esta
 *  composición sin importar este archivo (que carga tipografías de Google). Se
 *  re-exportan para no romper a quien las venía tomando de acá. */
export { COLD_OPEN_DURATION, COLD_OPEN_FPS } from "./pieces.meta";
import { COLD_OPEN_DURATION } from "./pieces.meta";

/** Límites de cada beat, en frames. El beat 2 arranca antes de que termine el 1:
 *  el push-in de la planilla se encadena con el zoom sin corte. */
export const BEATS = {
  one:   { from: 0,  to: 45  }, // la planilla en papel
  two:   { from: 30, to: 70  }, // zoom al "9"
  three: { from: 70, to: 105 }, // corte seco al ERP
} as const;

/** Curva del zoom del beat 2 (expo-out: arranca fuerte y frena suave). */
const ZOOM_EASE = Easing.bezier(0.16, 1, 0.3, 1);

// ═══ BEATS 1 y 2 — la planilla ═══════════════════════════════════════════════

// Geometría del papel (unidades locales; el papel se escala al viewport).
const PAPER_W = 900;
const PAPER_H = 1300;

const TABLE_X1  = 70;   // borde izquierdo de la tabla
const TABLE_X2  = 830;  // borde derecho
const TABLE_Y1  = 300;  // techo del encabezado
const HEAD_H    = 84;   // alto de la fila de encabezado
const ROW_H     = 118;  // alto de cada fila de producto
const DIVIDER_X = 636;  // separador producto | cantidad

interface Row {
  name: string;
  qty:  string;
  /** Cantidad garabateada: se escribe más grande, torcida y repasada. */
  scrawled?: boolean;
}

const ROWS: Row[] = [
  { name: "LECHE ENTERA", qty: "24" },
  { name: "PAN LACTAL",   qty: "12" },
  { name: "YOGUR VASO",   qty: "9", scrawled: true },
  { name: "GASEOSA 1.5",  qty: "18" },
  { name: "HUEVOS x30",   qty: "6" },
];

const SCRAWLED_INDEX = ROWS.findIndex((r) => r.scrawled);
const TABLE_Y2 = TABLE_Y1 + HEAD_H + ROWS.length * ROW_H;

/** Centro del "9" en coordenadas del papel: es el punto que el zoom persigue. */
const NINE_X = (DIVIDER_X + TABLE_X2) / 2;
const NINE_Y = TABLE_Y1 + HEAD_H + SCRAWLED_INDEX * ROW_H + ROW_H / 2;

/**
 * Path SVG de una línea "a mano": la recta (x1,y1)→(x2,y2) partida en segmentos
 * con jitter determinista (`random` de Remotion, mismo resultado en cada frame
 * y en cada worker de render) y suavizada con curvas cuadráticas.
 */
const inkLine = (
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  seed: string,
  amp = 3.2,
  segments = 7
): string => {
  const pts: [number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    // Los extremos tiemblan menos: el trazo arranca y termina apoyado.
    const edge = i === 0 || i === segments ? 0.35 : 1;
    pts.push([
      x1 + (x2 - x1) * t + (random(`${seed}x${i}`) - 0.5) * amp * edge,
      y1 + (y2 - y1) * t + (random(`${seed}y${i}`) - 0.5) * amp * edge,
    ]);
  }

  let d = `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [cx, cy] = pts[i];
    const mx = (pts[i][0] + pts[i + 1][0]) / 2;
    const my = (pts[i][1] + pts[i + 1][1]) / 2;
    d += ` Q ${cx.toFixed(2)} ${cy.toFixed(2)} ${mx.toFixed(2)} ${my.toFixed(2)}`;
  }
  const last = pts[pts.length - 1];
  d += ` L ${last[0].toFixed(2)} ${last[1].toFixed(2)}`;
  return d;
};

const INK = "#2f3a52";  // tinta azul-negra descolorida
const PENCIL = "#4a4235";

/** Renglones tenues de cuaderno. */
const RuledLines: React.FC = () => {
  const lines = [];
  for (let y = 180; y < PAPER_H - 90; y += 59) {
    lines.push(
      <path
        key={y}
        d={inkLine(52, y, PAPER_W - 52, y, `rule${y}`, 1.6, 4)}
        stroke="rgba(96,116,150,0.20)"
        strokeWidth={1.6}
        fill="none"
      />
    );
  }
  return <>{lines}</>;
};

/** Grilla de la tabla dibujada a mano: bordes irregulares, no perfectos. */
const HandDrawnTable: React.FC = () => (
  <>
    {/* Marco exterior: cuatro trazos independientes que no cierran perfecto. */}
    <path d={inkLine(TABLE_X1, TABLE_Y1, TABLE_X2 + 6, TABLE_Y1 - 3, "top")}    stroke={INK} strokeWidth={4} fill="none" strokeLinecap="round" />
    <path d={inkLine(TABLE_X2, TABLE_Y1 - 2, TABLE_X2 - 4, TABLE_Y2, "right")}  stroke={INK} strokeWidth={4} fill="none" strokeLinecap="round" />
    <path d={inkLine(TABLE_X1 - 3, TABLE_Y2, TABLE_X2 - 2, TABLE_Y2 + 5, "bot")} stroke={INK} strokeWidth={4} fill="none" strokeLinecap="round" />
    <path d={inkLine(TABLE_X1 + 2, TABLE_Y1 + 4, TABLE_X1 - 2, TABLE_Y2 + 2, "left")} stroke={INK} strokeWidth={4} fill="none" strokeLinecap="round" />

    {/* Separador del encabezado, repasado dos veces (queda más grueso). */}
    <path d={inkLine(TABLE_X1, TABLE_Y1 + HEAD_H, TABLE_X2, TABLE_Y1 + HEAD_H, "head1")} stroke={INK} strokeWidth={3.4} fill="none" />
    <path d={inkLine(TABLE_X1 + 4, TABLE_Y1 + HEAD_H + 2, TABLE_X2 - 6, TABLE_Y1 + HEAD_H + 3, "head2")} stroke={INK} strokeWidth={2.4} fill="none" opacity={0.75} />

    {/* Separadores de fila. */}
    {ROWS.slice(1).map((_, i) => {
      const y = TABLE_Y1 + HEAD_H + (i + 1) * ROW_H;
      return (
        <path
          key={y}
          d={inkLine(TABLE_X1 + 3, y, TABLE_X2 - 5, y + 2, `row${i}`)}
          stroke={INK}
          strokeWidth={2.8}
          fill="none"
          opacity={0.85}
        />
      );
    })}

    {/* Divisor vertical producto | cantidad: se pasa de largo abajo. */}
    <path
      d={inkLine(DIVIDER_X, TABLE_Y1 + 3, DIVIDER_X - 5, TABLE_Y2 + 11, "div")}
      stroke={INK}
      strokeWidth={3}
      fill="none"
    />
  </>
);

/** Subrayado garabateado bajo el "9": se anotó rápido y se remarcó. */
const Scribble: React.FC = () => (
  <svg
    width={112}
    height={54}
    viewBox="0 0 112 54"
    style={{ position: "absolute", left: -28, top: 74, overflow: "visible" }}
  >
    <path
      d={inkLine(8, 18, 104, 12, "scr1", 5)}
      stroke={INK}
      strokeWidth={3}
      fill="none"
      opacity={0.5}
      strokeLinecap="round"
    />
    <path
      d={inkLine(16, 30, 96, 23, "scr2", 6)}
      stroke={INK}
      strokeWidth={2.4}
      fill="none"
      opacity={0.35}
      strokeLinecap="round"
    />
  </svg>
);

/** El "9" garabateado. Vive fuera de la capa desenfocada: es lo único que queda
 *  nítido cuando el beat 2 aísla el número. */
const ScrawledNine: React.FC = () => (
  <div
    style={{
      position:       "absolute",
      left:           DIVIDER_X,
      top:            TABLE_Y1 + HEAD_H + SCRAWLED_INDEX * ROW_H,
      width:          TABLE_X2 - DIVIDER_X,
      height:         ROW_H,
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
    }}
  >
    <div style={{ position: "relative", transform: "rotate(-9deg) translate(-6px, -4px)" }}>
      <Scribble />
      {/* Repasado: dos trazos apenas desalineados, como si se hubiera escrito
          rápido y remarcado encima. */}
      <span style={{ position: "absolute", left: 2, top: 3, fontFamily: gochi, fontSize: 104, color: INK, opacity: 0.45 }}>
        9
      </span>
      <span style={{ position: "relative", fontFamily: gochi, fontSize: 104, color: INK }}>
        9
      </span>
    </div>
  </div>
);

/** Puntos guía entre el nombre y la cantidad ("YOGUR VASO ...... 9"). */
const Leader: React.FC = () => (
  <div
    style={{
      flex: 1,
      alignSelf: "flex-end",
      marginBottom: 16,
      marginLeft: 14,
      marginRight: 10,
      height: 6,
      backgroundImage: `radial-gradient(circle, ${PENCIL} 1.6px, transparent 1.9px)`,
      backgroundSize: "22px 6px",
      backgroundRepeat: "repeat-x",
      opacity: 0.55,
    }}
  />
);

const PaperScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { width: vw, height: vh } = useVideoConfig();

  // El pliego es vertical: se escala para llenar el alto del cuadro dejando aire
  // arriba y abajo, y la mesa queda a los lados. Depender del viewport (y no de
  // un factor fijo) mantiene el mismo encuadre en 1920x1080 y en 1080x1920.
  // 0.84 y no más: con la rotación de -2deg el pliego "crece" unos 30 px de alto,
  // y el push-in le suma otro 4.5% — a 0.92 las esquinas tocaban el borde.
  const fit = Math.min((vh * 0.84) / PAPER_H, (vw * 0.84) / PAPER_W);

  // ── BEAT 1 (frames 0–45): la planilla, vista cenital ───────────────────────
  // Push-in lento: la cámara se acerca al papel apoyado en la mesa. Arranca ya
  // con contenido en pantalla (sin fundido desde negro) para que el primer
  // frame sirva de miniatura.
  const push = interpolate(frame, [BEATS.one.from, BEATS.one.to], [0, 1], {
    extrapolateLeft:  "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const scale  = fit * (1 + 0.045 * push);
  const rot    = interpolate(push, [0, 1], [-2.8, -2]); // asienta en -2deg
  const driftY = interpolate(push, [0, 1], [14, 0]);

  // ── BEAT 2 (frames 30–70): zoom sobre el "9" ──────────────────────────────
  const t = interpolate(frame, [BEATS.two.from, BEATS.two.to], [0, 1], {
    extrapolateLeft:  "clamp",
    extrapolateRight: "clamp",
    easing: ZOOM_EASE,
  });
  const zoom = 1 + 2.5 * t;  // 1x → 3.5x
  const blur = 4 * t;        // 0 → 4px

  // Dónde cae el "9" en pantalla: hay que aplicarle al punto la misma cadena de
  // transformaciones que al papel (escala → rotación → deriva) para que el zoom
  // quede clavado en el número y no en el centro del pliego.
  const rad = (rot * Math.PI) / 180;
  const dx  = (NINE_X - PAPER_W / 2) * scale;
  const dy  = (NINE_Y - PAPER_H / 2) * scale;
  const nineScreenX = vw / 2 + dx * Math.cos(rad) - dy * Math.sin(rad);
  const nineScreenY = vh / 2 + dx * Math.sin(rad) + dy * Math.cos(rad) + driftY;

  // Además de escalar sobre el "9", la cámara lo reencuadra: si se queda donde
  // estaba, al final del zoom entra el borde del papel y sobra mesa vacía. El
  // destino es apenas a la derecha del centro (0.57) porque el "9" está cerca
  // del borde derecho del pliego: centrarlo exacto deja más mesa a la vista.
  const panX = (vw * 0.57 - nineScreenX) * t;
  const panY = (vh * 0.5  - nineScreenY) * t;

  return (
    <AbsoluteFill style={{ background: "#241d16" }}>
      {/* Superficie de la mesa, apenas veteada, alrededor del papel. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(120% 90% at 50% 38%, #3a2f24 0%, #241d16 62%, #17120d 100%)",
        }}
      />

      {/* Cámara del beat 2: escala todo el plano tomando como pivote el "9". */}
      <AbsoluteFill
        style={{
          transform:       `translate(${panX.toFixed(2)}px, ${panY.toFixed(2)}px) scale(${zoom.toFixed(4)})`,
          transformOrigin: `${nineScreenX.toFixed(2)}px ${nineScreenY.toFixed(2)}px`,
        }}
      >
        <AbsoluteFill
          style={{
            display:        "flex",
            alignItems:     "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              position:  "relative",
              width:     PAPER_W,
              height:    PAPER_H,
              // AbsoluteFill es flex en columna: sin esto el papel (1300 px) se
              // comprime al alto del cuadro y la grilla deja de calzar con el texto.
              flexShrink: 0,
              transform: `translateY(${driftY.toFixed(2)}px) rotate(${rot.toFixed(2)}deg) scale(${scale.toFixed(4)})`,
              background:
                "linear-gradient(168deg, #f6efdc 0%, #f1e7d0 46%, #e9dcc0 100%)",
              boxShadow:
                "0 38px 90px rgba(0,0,0,0.55), 0 4px 12px rgba(0,0,0,0.35)",
              borderRadius: 3,
            }}
          >
            {/* Capa que se desenfoca en el beat 2: todo salvo el "9". */}
            <div
              style={{
                position: "absolute",
                inset:    0,
                filter:   blur > 0.01 ? `blur(${blur.toFixed(2)}px)` : undefined,
              }}
            >
              {/* Renglones + grilla dibujados a mano */}
              <svg
                width={PAPER_W}
                height={PAPER_H}
                viewBox={`0 0 ${PAPER_W} ${PAPER_H}`}
                style={{ position: "absolute", inset: 0 }}
              >
                <RuledLines />
                {/* Margen rojo del cuaderno, torcido. */}
                <path
                  d={inkLine(120, 60, 116, PAPER_H - 60, "margin", 3.5, 9)}
                  stroke="rgba(178,74,74,0.34)"
                  strokeWidth={2.4}
                  fill="none"
                />
                <HandDrawnTable />
              </svg>

              {/* Título */}
              <div
                style={{
                  position:   "absolute",
                  top:        150,
                  left:       TABLE_X1 + 8,
                  fontFamily: caveat,
                  fontSize:   96,
                  color:      INK,
                  transform:  "rotate(-1.1deg)",
                  letterSpacing: 2,
                }}
              >
                INVENTARIO
              </div>

              {/* Encabezado de la tabla */}
              <div
                style={{
                  position:   "absolute",
                  top:        TABLE_Y1 + 8,
                  left:       TABLE_X1 + 26,
                  width:      DIVIDER_X - TABLE_X1 - 40,
                  fontFamily: caveat,
                  fontSize:   50,
                  color:      INK,
                  opacity:    0.82,
                  transform:  "rotate(-0.5deg)",
                }}
              >
                producto
              </div>
              <div
                style={{
                  position:   "absolute",
                  top:        TABLE_Y1 + 8,
                  left:       DIVIDER_X + 34,
                  fontFamily: caveat,
                  fontSize:   50,
                  color:      INK,
                  opacity:    0.82,
                  transform:  "rotate(0.7deg)",
                }}
              >
                cant.
              </div>

              {/* Filas escritas a mano */}
              {ROWS.map((row, i) => {
                const top = TABLE_Y1 + HEAD_H + i * ROW_H;
                // Cada renglón se escribió con pulso distinto.
                const tilt   = (random(`tilt${i}`) - 0.5) * 2.4;
                const offset = (random(`off${i}`) - 0.5) * 10;

                return (
                  <div
                    key={row.name}
                    style={{
                      position: "absolute",
                      top,
                      left:     TABLE_X1,
                      width:    TABLE_X2 - TABLE_X1,
                      height:   ROW_H,
                      display:  "flex",
                      alignItems: "center",
                    }}
                  >
                    {/* Nombre + puntos guía */}
                    <div
                      style={{
                        display:     "flex",
                        alignItems:  "center",
                        width:       DIVIDER_X - TABLE_X1,
                        paddingLeft: 30,
                        transform:   `rotate(${tilt.toFixed(2)}deg) translateY(${offset.toFixed(1)}px)`,
                      }}
                    >
                      <span
                        style={{
                          fontFamily: caveat,
                          fontSize:   62,
                          color:      INK,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {row.name}
                      </span>
                      <Leader />
                    </div>

                    {/* Cantidad. El "9" garabateado no va acá: se dibuja aparte,
                        fuera del desenfoque. */}
                    <div
                      style={{
                        position:       "relative",
                        flex:           1,
                        display:        "flex",
                        alignItems:     "center",
                        justifyContent: "center",
                      }}
                    >
                      {row.scrawled ? null : (
                        <span
                          style={{
                            fontFamily: caveat,
                            fontSize:   62,
                            color:      INK,
                            transform:  `rotate(${(tilt * 1.4).toFixed(2)}deg)`,
                            display:    "inline-block",
                          }}
                        >
                          {row.qty}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* El "9": nítido siempre. */}
            <ScrawledNine />

            {/* Grano del papel: ruido sutil por encima de todo lo dibujado. */}
            <svg
              width={PAPER_W}
              height={PAPER_H}
              style={{
                position:      "absolute",
                inset:         0,
                mixBlendMode:  "multiply",
                opacity:       0.22,
                pointerEvents: "none",
              }}
            >
              <filter id="paper-grain">
                <feTurbulence
                  type="fractalNoise"
                  baseFrequency="0.85"
                  numOctaves={4}
                  stitchTiles="stitch"
                />
                <feColorMatrix type="saturate" values="0" />
              </filter>
              <rect width="100%" height="100%" filter="url(#paper-grain)" />
            </svg>

            {/* Sombra suave hacia los bordes: el papel no está perfectamente plano. */}
            <div
              style={{
                position:      "absolute",
                inset:         0,
                background:
                  "radial-gradient(125% 92% at 46% 38%, rgba(0,0,0,0) 66%, rgba(60,40,15,0.13) 100%)",
                pointerEvents: "none",
              }}
            />
          </div>
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ═══ BEAT 3 — la pantalla del ERP ════════════════════════════════════════════

const UI = {
  chrome:    "#1e2a3a",
  menu:      "#33445c",
  appBg:     "#eef1f5",
  panel:     "#ffffff",
  border:    "#c3ccd8",
  borderSub: "#dde3ea",
  headRow:   "#d9e1ea",
  altRow:    "#f5f8fb",
  selRow:    "#cfe0f5",
  text:      "#22303f",
  muted:     "#6b7a8c",
  accent:    "#2f6fbf",
} as const;

/** Timing del beat 3, en frames locales a la escena (0 = frame 70 global). */
const TYPE_9  = 6;   // aparece el "9"
const TYPE_0  = 14;  // aparece el "0" → queda "90"
const BLINK   = 8;   // medio ciclo del cursor

interface ErpRow {
  code:  string;
  desc:  string;
  depo:  string;
  stock: string;
  unit:  string;
}

const ERP_ROWS: ErpRow[] = [
  { code: "LAC-0114", desc: "LECHE ENTERA SACHET 1L",     depo: "DEP-01", stock: "24",  unit: "UN" },
  { code: "PAN-0071", desc: "PAN LACTAL BLANCO 550G",     depo: "DEP-01", stock: "12",  unit: "UN" },
  { code: "YOG-1250", desc: "YOGUR VASO FIRME 125G",      depo: "DEP-01", stock: "9",   unit: "UN" },
  { code: "GAS-1503", desc: "GASEOSA COLA 1.5L",          depo: "DEP-01", stock: "18",  unit: "UN" },
  { code: "HUE-0030", desc: "HUEVOS BLANCOS MAPLE x30",   depo: "DEP-01", stock: "6",   unit: "MP" },
  { code: "QUE-0220", desc: "QUESO CREMOSO HORMA",        depo: "DEP-02", stock: "31",  unit: "KG" },
  { code: "MAN-0100", desc: "MANTECA POTE 200G",          depo: "DEP-02", stock: "47",  unit: "UN" },
  { code: "DUL-0400", desc: "DULCE DE LECHE CLASICO",     depo: "DEP-01", stock: "22",  unit: "UN" },
  { code: "ACE-0900", desc: "ACEITE GIRASOL 900ML",       depo: "DEP-03", stock: "58",  unit: "UN" },
  { code: "ARR-1000", desc: "ARROZ LARGO FINO 1KG",       depo: "DEP-03", stock: "73",  unit: "UN" },
  { code: "FID-0500", desc: "FIDEOS GUISEROS 500G",       depo: "DEP-03", stock: "64",  unit: "UN" },
  { code: "YER-1000", desc: "YERBA MATE ELABORADA 1KG",   depo: "DEP-03", stock: "41",  unit: "UN" },
  { code: "AZU-1000", desc: "AZUCAR COMUN TIPO A 1KG",    depo: "DEP-03", stock: "88",  unit: "UN" },
  { code: "CAF-0250", desc: "CAFE MOLIDO TOSTADO 250G",   depo: "DEP-02", stock: "17",  unit: "UN" },
  { code: "GAL-0300", desc: "GALLETITAS SURTIDAS 300G",   depo: "DEP-01", stock: "35",  unit: "UN" },
];

const COLS: { key: keyof ErpRow; label: string; width: number; align?: "right" }[] = [
  { key: "code",  label: "CÓDIGO",      width: 190 },
  { key: "desc",  label: "DESCRIPCIÓN", width: 560 },
  { key: "depo",  label: "DEPÓSITO",    width: 190 },
  { key: "stock", label: "STOCK",       width: 140, align: "right" },
  { key: "unit",  label: "UM",          width: 100 },
];

/** Botón de barra de herramientas: solo rectángulos y texto. */
const ToolButton: React.FC<{ label: string; primary?: boolean }> = ({ label, primary }) => (
  <div
    style={{
      padding:      "9px 20px",
      fontSize:     19,
      fontFamily:   inter,
      color:        primary ? "#ffffff" : UI.text,
      background:   primary ? UI.accent : "linear-gradient(#ffffff, #eef1f5)",
      border:       `1px solid ${primary ? "#255a9c" : UI.border}`,
      borderRadius: 3,
    }}
  >
    {label}
  </div>
);

/** Campo de formulario. El de cantidad va enfocado: borde azul y cursor. */
const Field: React.FC<{
  label:     string;
  value:     string;
  width:     number;
  focused?:  boolean;
  cursor?:   boolean;
  highlight?: number;
}> = ({ label, value, width, focused, cursor, highlight = 0 }) => (
  <div style={{ width }}>
    <div style={{ fontFamily: inter, fontSize: 17, color: UI.muted, marginBottom: 7, letterSpacing: 0.3 }}>
      {label}
    </div>
    <div
      style={{
        position:     "relative",
        height:       54,
        display:      "flex",
        alignItems:   "center",
        padding:      "0 14px",
        background:   highlight > 0
          ? `rgba(255, 208, 92, ${(0.42 * highlight).toFixed(3)})`
          : focused ? "#ffffff" : "#f7f9fb",
        border:       `${focused ? 2 : 1}px solid ${focused ? UI.accent : UI.border}`,
        borderRadius: 3,
        boxShadow:    focused ? `0 0 0 3px rgba(47,111,191,0.18)` : undefined,
        fontFamily:   mono,
        fontSize:     30,
        color:        UI.text,
      }}
    >
      <span>{value}</span>
      {cursor ? (
        <span
          style={{
            display:    "inline-block",
            width:      2,
            height:     32,
            marginLeft: 3,
            background: UI.text,
          }}
        />
      ) : null}
    </div>
  </div>
);

const ErpScene: React.FC = () => {
  const frame = useCurrentFrame();

  // Tecleo: "9" y después "0" → "90".
  const typed = frame >= TYPE_0 ? "90" : frame >= TYPE_9 ? "9" : "";

  // El cursor parpadea salvo en el instante del tecleo (se "apoya" la tecla).
  const justTyped = (frame >= TYPE_9 && frame < TYPE_9 + 3) || (frame >= TYPE_0 && frame < TYPE_0 + 3);
  const cursorOn  = justTyped || Math.floor(frame / BLINK) % 2 === 0;

  // Resaltado del "90": entra rápido apenas se completa y se sostiene.
  const highlight = interpolate(frame, [TYPE_0, TYPE_0 + 4], [0, 1], {
    extrapolateLeft:  "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });

  return (
    <AbsoluteFill style={{ background: UI.appBg, fontFamily: inter, color: UI.text }}>
      {/* Barra de título */}
      <div
        style={{
          height:     58,
          background: UI.chrome,
          color:      "#dfe6ef",
          display:    "flex",
          alignItems: "center",
          padding:    "0 24px",
          fontSize:   19,
          letterSpacing: 0.4,
        }}
      >
        <span style={{ fontWeight: 600 }}>SIGES</span>
        <span style={{ opacity: 0.55, margin: "0 10px" }}>·</span>
        <span style={{ opacity: 0.8 }}>Gestión de Inventario — Ajuste de existencias</span>
        <div style={{ flex: 1 }} />
        <span style={{ opacity: 0.6, fontSize: 17 }}>SUC. CENTRO · usuario: mlopez · 18:42</span>
      </div>

      {/* Barra de menú */}
      <div
        style={{
          height:     40,
          background: UI.menu,
          color:      "#c9d5e4",
          display:    "flex",
          alignItems: "center",
          gap:        28,
          padding:    "0 24px",
          fontSize:   18,
        }}
      >
        {["Archivo", "Edición", "Movimientos", "Consultas", "Reportes", "Ventana", "Ayuda"].map((m) => (
          <span key={m}>{m}</span>
        ))}
      </div>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Panel lateral */}
        <div
          style={{
            width:       260,
            background:  "#e6eaf0",
            borderRight: `1px solid ${UI.border}`,
            padding:     "18px 0",
            fontSize:    18,
          }}
        >
          {[
            { t: "Artículos",        sel: false },
            { t: "Existencias",      sel: true  },
            { t: "  Ajustes",        sel: false },
            { t: "  Transferencias", sel: false },
            { t: "  Recuentos",      sel: false },
            { t: "Compras",          sel: false },
            { t: "Ventas",           sel: false },
            { t: "Proveedores",      sel: false },
            { t: "Configuración",    sel: false },
          ].map((it) => (
            <div
              key={it.t}
              style={{
                padding:    "9px 24px",
                whiteSpace: "pre",
                background: it.sel ? UI.selRow : undefined,
                borderLeft: `3px solid ${it.sel ? UI.accent : "transparent"}`,
                color:      it.sel ? UI.text : "#48586b",
              }}
            >
              {it.t}
            </div>
          ))}
        </div>

        {/* Área principal */}
        <div style={{ flex: 1, padding: 22, display: "flex", flexDirection: "column", minWidth: 0 }}>
          {/* Barra de herramientas */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
            <ToolButton label="Nuevo" />
            <ToolButton label="Buscar" />
            <ToolButton label="Filtrar" />
            <div style={{ flex: 1 }} />
            <ToolButton label="Guardar F10" primary />
          </div>

          {/* Tabla de datos densa */}
          <div style={{ border: `1px solid ${UI.border}`, background: UI.panel }}>
            {/* Encabezado */}
            <div style={{ display: "flex", background: UI.headRow, borderBottom: `1px solid ${UI.border}` }}>
              {COLS.map((c) => (
                <div
                  key={c.key}
                  style={{
                    width:      c.width,
                    padding:    "9px 14px",
                    fontSize:   16,
                    fontWeight: 600,
                    color:      "#3d4d61",
                    letterSpacing: 0.6,
                    textAlign:  c.align ?? "left",
                    borderRight: `1px solid ${UI.border}`,
                  }}
                >
                  {c.label}
                </div>
              ))}
            </div>

            {/* Filas */}
            {ERP_ROWS.map((r, i) => {
              const selected = r.code === "YOG-1250";
              return (
                <div
                  key={r.code}
                  style={{
                    display:      "flex",
                    background:   selected ? UI.selRow : i % 2 ? UI.altRow : UI.panel,
                    borderBottom: `1px solid ${UI.borderSub}`,
                  }}
                >
                  {COLS.map((c) => (
                    <div
                      key={c.key}
                      style={{
                        width:       c.width,
                        padding:     "7px 14px",
                        fontSize:    18,
                        fontFamily:  c.key === "desc" ? inter : mono,
                        textAlign:   c.align ?? "left",
                        color:       UI.text,
                        borderRight: `1px solid ${UI.borderSub}`,
                        whiteSpace:  "nowrap",
                        overflow:    "hidden",
                      }}
                    >
                      {r[c.key]}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>

          {/* Formulario de ajuste */}
          <div
            style={{
              marginTop:  20,
              border:     `1px solid ${UI.border}`,
              background: UI.panel,
              padding:    "18px 22px 22px",
            }}
          >
            <div style={{ fontSize: 18, fontWeight: 600, color: "#3d4d61", marginBottom: 16 }}>
              Detalle del ajuste
            </div>
            <div style={{ display: "flex", gap: 20, alignItems: "flex-end" }}>
              <Field label="ARTÍCULO"        value="YOG-1250" width={230} />
              <Field label="DEPÓSITO"        value="DEP-01"   width={190} />
              <Field label="STOCK SISTEMA"   value="9"        width={190} />
              <Field
                label="CANTIDAD CONTADA"
                value={typed}
                width={250}
                focused
                cursor={cursorOn}
                highlight={highlight}
              />
              <div style={{ flex: 1 }} />
            </div>
          </div>

          <div style={{ flex: 1 }} />
        </div>
      </div>

      {/* Barra de estado */}
      <div
        style={{
          height:      36,
          background:  "#dfe3e9",
          borderTop:   `1px solid ${UI.border}`,
          display:     "flex",
          alignItems:  "center",
          padding:     "0 24px",
          fontSize:    16,
          color:       UI.muted,
          gap:         28,
        }}
      >
        <span>Registro 3 de {ERP_ROWS.length}</span>
        <span>Modo: EDICIÓN</span>
        <span>F10 Guardar · ESC Cancelar</span>
      </div>
    </AbsoluteFill>
  );
};

// ═══ Composición ═════════════════════════════════════════════════════════════

export const ColdOpen: React.FC = () => (
  <AbsoluteFill>
    {/* Beats 1 y 2 */}
    <Sequence durationInFrames={BEATS.three.from} layout="none">
      <PaperScene />
    </Sequence>

    {/* Beat 3: corte seco, sin transición. */}
    <Sequence
      from={BEATS.three.from}
      durationInFrames={COLD_OPEN_DURATION - BEATS.three.from}
      layout="none"
    >
      <ErpScene />
    </Sequence>
  </AbsoluteFill>
);

// Export por defecto: Root.tsx lo carga con `lazyComponent`, que espera un
// módulo con `default` (ver pieces.meta.ts para el porqué de la carga diferida).
export default ColdOpen;
