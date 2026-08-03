# PROYECTO
Episodio vertical de la serie MultiAsking sobre la empresa Simile.
Formato 9:16, 5:00 exactos, split-screen colapsable (animación arriba /
rostro abajo). Audiencia: operadores senior. La estética tiene que leerse
como pieza editorial de autor, NO como contenido de TikTok. Cada decisión
de movimiento se justifica o no existe.

# 1 · SPECS
- Canvas 1080 × 1920
- fps 30 (igualar la cámara; no subir a 60)
- durationInFrames total 9000
- Salida: MP4 H.264 main profile, CRF 18, yuv420p
- 5 composiciones concatenadas en un <Series> dentro de <EpisodeMaster>

# 2 · ZONAS SEGURAS (INVIOLABLES)
La UI de la plataforma se monta encima. Ningún dato crítico puede vivir en:
- y 0–140      → barra de marca, sacrificable
- y 1570–1920  → bloque de caption de la plataforma
- x 940–1080   → columna de acciones

Canvas útil real: y 140 → 1570 (1430px de alto).
En modo FULL la animación se extiende visualmente hasta 1920 pero solo
con fondo, grano y elementos decorativos. Nada legible bajo y=1570.

# 3 · MODOS DE LAYOUT
MODO SPLIT (38% del episodio)
  - Pane animación: 1080 × 960, y 140–1100
  - Costura: línea de 2px bone al 18% de opacidad en y=1100
  - Pane rostro: <OffthreadVideo> 1080 × 820, y 1100–1920
  - Encuadre obligatorio: ojos en y ≈ 1290. Los últimos 350px son
    pecho y fondo, sacrificables.
  - Encuadre FIJO. Prohibido punch-in, prohibido reframing dinámico.

MODO FULL (62%)
  - Pane animación: 1080 × 1780, y 140–1920
  - Rostro ausente, voz en off

TRANSICIÓN ENTRE MODOS
  Wipe diagonal del sistema, 20 frames, con easing.inOut(easing.cubic).
  El pane de rostro no se desliza: es revelado/ocultado por la máscara.
  Componente compartido <ModeTransition mode="split|full" progress={n} />

# 4 · TOKENS
Importar del theme existente de la serie. NO redefinir.
Fallbacks solo si no existen:
  bg      #0A0A0A
  bone    #F2EFE9
  accent  (rojo del sistema)
  muted   bone @ 46%
  hairline bone @ 14%

REGLA DEL ACENTO: el rojo aparece exactamente 4 veces en 5 minutos.
  1. "SEIS SEMANAS"                    (B1)
  2. Badge de confianza "Media"        (B2)
  3. Borde de "comportamiento revelado"(B4)
  4. Tercera pregunta de cierre        (B5)
Ningún otro uso. Ni bordes, ni acentos, ni hover states, ni subrayados.

# 5 · ESCALA TIPOGRÁFICA (calibrada para 1080 de ancho)
  Display XL  132px / line-height 0.92 / tracking -0.03em  Archivo Black
  Display L    96px / 0.94 / -0.025em                      Archivo Black
  Display M    72px / 1.00 / -0.02em                       Archivo Black
  Body         40px / 1.35 / 0                             sans secundario
  Label        28px / 1.30 / 0.08em / uppercase            sans secundario
  Footnote     22px / 1.30 / 0.04em                        sans secundario, muted

Margen lateral: 72px. Grilla de línea base: 12px.
Números SIEMPRE con font-variant-numeric: tabular-nums para evitar
que el ancho salte durante los contadores.

# 6 · REGLAS DE MOVIMIENTO — ESTA ES LA SECCIÓN QUE DEFINE LA CALIDAD

6.1 GRILLA TEMPORAL
Toda duración es múltiplo de 6 frames (0.2s). Sin excepciones.
  Entrada de elemento    18f
  Salida                 12f
  Sostén mínimo          60f
  Transición de modo     20f
  Wipe de sección        24f

6.2 EASING
Prohibido `linear` salvo: rotación constante y desplazamiento del grano.
  Entradas:   spring({ damping: 200, mass: 0.55, stiffness: 120 })
  Contadores: interpolate + Easing.out(Easing.cubic)
  Trazos:     Easing.inOut(Easing.cubic)
  Salidas:    Easing.in(Easing.quad)
Sin rebote visible. El spring está sobreamortiguado a propósito: el
overshoot cartoon rompe el registro editorial.

6.3 REVELADO DE TIPOGRAFÍA
Prohibido el fade de opacidad puro en display type. Siempre:
  clipPath: inset(100% 0 0 0) → inset(0% 0 0 0)
  + translateY(28 → 0)
  + letterSpacing(-0.05em → valor final)
  18 frames, spring.
El body text sí puede usar opacidad + translateY(12 → 0), 12f.

6.4 ESCALA
Nada escala desde 0. Mínimo 0.94 → 1.
Nada escala por encima de 1.06.

6.5 TEXTURA (crítico para que el negro no se vea plano)
  a) Grano: overlay a pantalla completa, PNG de ruido de 512px tileado,
     opacidad 0.035, blend-mode overlay. Desplazar el tile en X e Y con
     random(`grain-${frame}`) * 512 en cada frame. Reproducible.
  b) Viñeta: radial-gradient desde el centro, transparente al 40% del
     radio → rgba(0,0,0,0.55) en los bordes. Estática.
  c) Ambas capas se aplican en <EpisodeMaster>, no por composición.

6.6 NITIDEZ
  - Grosor mínimo de trazo: 2px. A 1080 de ancho un 1px titila tras la
    compresión de la plataforma.
  - Math.round() en todo translateX/Y de elementos con bordes.
  - Sin blur animado salvo el borde emplumado del wipe.

6.7 CONTINUIDAD
El wipe diagonal usa UN SOLO ángulo en todo el episodio (el del sistema).
Implementar como <DiagonalWipe progress={0..1} feather={60} /> compartido.
Todas las transiciones de sección usan ese componente. Sin variantes.

6.8 DENSIDAD (regla de retención)
El pane de animación cambia de estado cada 90–150 frames (3–5s).
"Cambio de estado" = entra o sale un elemento, no un movimiento continuo.
Un contador corriendo 20 segundos NO cuenta como cambio de estado.
Si un bloque supera 150f sin cambio, partirlo.

# 7 · TIMING POR TRANSCRIPCIÓN (no hardcodear frames)
Cargar public/captions.json generado con:
  @remotion/install-whisper-cpp → transcribe({ tokenLevelTimestamps: true })
  → toCaptions()

Helper compartido:
  const useCue = (needle: string, fallbackFrame: number) => {
    const { fps } = useVideoConfig();
    const c = captions.find(x =>
      x.text.trim().toLowerCase().includes(needle.toLowerCase()));
    return c ? Math.round((c.startMs / 1000) * fps) : fallbackFrame;
  };

Los frames que doy abajo son FALLBACK. La verdad la manda el audio.
durationInFrames de cada composición vía calculateMetadata() sobre la
duración real del track.

# 8 · SUBTÍTULOS QUEMADOS
Componente <Subtitles /> montado en <EpisodeMaster>, encima de todo.
  - Posición: y 980–1140 (borde inferior del pane de animación en SPLIT,
    misma posición en FULL para continuidad)
  - Estilo: Body 40px, bone, sin fondo, sin caja, sombra text-shadow
    0 2px 12px rgba(0,0,0,0.9) para legibilidad sobre animación
  - Agrupado por frase (createTikTokStyleCaptions con ~28 caracteres),
    NO palabra por palabra
  - Sin karaoke, sin resaltado, sin color. Estático por frase.
  - Prohibido amarillo, prohibido stroke negro, prohibido pop-in animado

# 9 · ACTIVOS EXTERNOS
Todo activo externo (captura, logo, figura de paper) entra vía
<QuotedAsset /> — componente compartido:
  - Marco: borde bone 2px
  - Escala: 55–70% del ancho del pane
  - Rotación: entre -2° y +2°, fija por instancia
  - Sombra: 0 24px 64px rgba(0,0,0,0.8)
  - Filtro: grayscale(1) + contrast(1.15) para capturas a color
  - Pie obligatorio en Footnote 22px muted (fuente + fecha)
  - Entrada: clipPath diagonal + translateY(20 → 0), 18f
Cargar de public/assets/. Nunca a sangre. Nunca sin pie.

# ══════════════════════════════════════════════════════════
# 10 · LAS CINCO COMPOSICIONES
# ══════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────┐
│ BLOQUE 1 — B1_Apertura · SPLIT · 750f (0:00–0:25)        │
└──────────────────────────────────────────────────────────┘
Pane 1080×960. Contenido: la latencia del research.

f0–90     Título de sección. Label "EPISODIO / SIMILE" arriba a la
          izquierda con margen 72px. Entra con revelado 6.3.
f90–450   <LatencyTimeline /> RECOMPUESTO EN VERTICAL: los 5 pasos
          dejan de ser una barra horizontal y pasan a ser una columna
          de 5 filas, cada una de 120px de alto, alineadas a la
          izquierda con margen 72px.
            "Brief" · "Reclutar panel" · "Campo" · "Análisis" · "Decisión"
          Cada fila: Display M a la izquierda, y a la derecha un trazo
          horizontal de 2px hairline que se dibuja con strokeDashoffset
          de derecha a izquierda en 24f.
          Stagger de 60f entre filas. Cue: cada paso entra con la palabra.
f450–540  Las 5 filas se comprimen verticalmente (scale Y 1 → 0.55,
          24f) para hacer lugar abajo. NO desaparecen: siguen visibles
          en muted como contexto.
f540–660  "SEIS SEMANAS" Display XL en ROJO (uso 1/4), centrado en el
          espacio liberado. Revelado 6.3 + pulso de escala 1→1.05→1
          en 18f, una sola vez. Cue: "seis".
f660–750  <QuotedAsset /> con la captura del post de Serie B entrando
          desde abajo, tapando parcialmente el conjunto. Rotación -1.5°.
          Pie: "simile.com/blog · 30 jul 2026".
          Corta con el fin del bloque, sin resolver → tensión.

┌──────────────────────────────────────────────────────────┐
│ BLOQUE 2 — B2_DatoYAgentes · FULL · 2850f (0:25–2:00)    │
└──────────────────────────────────────────────────────────┘
Pane 1080×1780, contenido legible confinado a y 140–1570.
Este bloque es el más largo: aplicar 6.8 con rigor. 22 estados mínimo.

FASE A · La ronda (f0–540)
f0–20     Transición SPLIT→FULL. El rostro sale por wipe diagonal.
f20–200   Contador 0 → 200.000.000 en Display XL, tabular-nums,
          formateado "USD 200.000.000". Easing.out(Easing.cubic).
          El contador NO es el único elemento: mientras corre, abajo
          entran en stagger de 40f tres líneas Body:
            "Valuación post-money: USD 2.000 millones"
            "Co-liderada por Greenoaks e Index Ventures"
            "5 meses desde el lanzamiento"
f200–340  Las tres líneas colapsan a una sola en muted. Entra
          <QuotedAsset /> con el headline real del sitio, re-tipografiado:
            «Simulate 8 billion people, accurately.»
          Marco bone, pie "simile.com".
f340–540  Los tres fundadores. NO como lista. Como tres cards
          verticales apiladas de 1080×160 con separador hairline:
            [ Joon Sung Park ]  Label: "Agentes generativos, UIST 2023"
            [ Michael Bernstein ] Label: "Computación social"
            [ Percy Liang ]     Label: "Acuñó 'foundation models'"
          Cada card entra desde la izquierda, 18f, stagger 60f.
          Al completarse las tres, un trazo vertical de 2px las une
          por la izquierda y aparece "STANFORD" en Label rotado -90°
          sobre ese trazo.
f540–564  Wipe diagonal de sección.

FASE B · Smallville (f564–1500)
f564–900  Recomposición vertical del pueblo. Grilla isométrica en
          hairline ocupando 1080×900. 25 puntos bone de 10px se
          encienden con random("smallville") determinístico, stagger
          de 8f. Sin labels.
f900–1080 Seis clusters se forman: los puntos se desplazan hacia sus
          centroides con spring, 36f. Entre puntos del mismo cluster
          se dibujan líneas hairline con strokeDashoffset.
f1080–1200 Un cluster se ilumina (bone 100% vs 40% del resto) y sobre
          él aparece un label pequeño: "una fiesta que nadie organizó".
f1200–1380 <QuotedAsset /> con la figura del mapa de Smallville del
          paper, desaturada, entrando por encima de la simulación.
          Pie: "Park et al., UIST 2023 · arXiv 2304.03442".
f1380–1500 Card tipográfica a pantalla: "AGENTES GENERATIVOS" Display XL,
          revelado 6.3. Debajo, Footnote: "UIST, 2023".

FASE C · Arquitectura del agente (f1500–2400)
f1500–1560 Wipe. Aparece un único punto bone centrado a y=700.
f1560–2100 Ciclo de 5 nodos EN VERTICAL, no circular: una columna
          descendente con retorno lateral.
            Memory stream → Retrieve → Reflect → Plan → Act
          Cada nodo es un rect de 720×110 con borde hairline, centrado,
          separados 40px. Entran de arriba hacia abajo, stagger 90f,
          revelado 6.3. Entre nodo y nodo, una flecha vertical de 2px
          se dibuja en 12f.
          Al llegar a "Act", una línea sale por la derecha, sube por
          x=980 y vuelve a "Memory stream" — el loop se cierra. 36f.
          Luego el loop entero pulsa una vez recorriendo el circuito
          con un segmento bone brillante (offset animado), 120f.
f2100–2400 Confianza. El conjunto de nodos se reduce a scale 0.7 y sube.
          Debajo entra <ComparativeGauge /> vertical, dos filas:
            "RESULTADO"  → barra bone 100%
            "CONFIANZA"  → badge que cicla 3 estados, 90f cada uno:
               "Alta" (bone) → "Moderada-alta" (bone) → "Media" (ROJO 2/4)
          El rojo entra en el tercer estado y se queda hasta el corte.

FASE D · Cierre del bloque (f2400–2850)
f2400–2550 Todo sale por wipe. Queda negro con grano.
f2550–2850 Frase puente en Display L, centrada, revelado 6.3:
          "Etiquetar cada resultado con su propia precisión esperada."
          Sostiene hasta el corte. Transición FULL→SPLIT en los
          últimos 20f.

┌──────────────────────────────────────────────────────────┐
│ BLOQUE 3 — B3_Escepticismo · SPLIT · 600f (2:00–2:20)    │
└──────────────────────────────────────────────────────────┘
Pane 1080×960. Bloque deliberadamente austero: el rostro carga el peso.

f0–180    Pane casi vacío. Solo un signo de interrogación tipográfico
          gigante (Display XL a 280px) en hairline, alineado a la
          derecha, saliendo parcialmente del canvas por x=1080.
          NO es un emoji ni un icono: es el carácter tipográfico de
          Archivo Black.
f180–420  Entra, alineada a la izquierda, en Display M, línea por línea
          con stagger de 90f:
            "¿Suena bien?"
            "Pregunta equivocada."
f420–600  Las dos líneas salen. Entra en Display L:
            "¿Contra qué se validó?"
          Sostiene hasta el corte.

┌──────────────────────────────────────────────────────────┐
│ BLOQUE 4 — B4_ValidacionYLimite · FULL · 2700f (2:20–3:50)│
└──────────────────────────────────────────────────────────┘
El bloque de credibilidad. Máxima densidad de dato, mínima decoración.

FASE A · Mil personas (f0–720)
f0–20     Transición SPLIT→FULL.
f20–400   1.000 puntos en grilla vertical 25 × 40 (25 columnas,
          40 filas), punto de 8px, gap 24px. Ocupa 1080×1400 dentro
          de la zona segura. Entran con delay = i * 0.35f.
f400–520  Cada punto genera un gemelo desplazado 7px en X e Y, bone
          al 45%. El efecto lee como "duplicación", no como sombra.
f520–720  Label centrado sobre el conjunto, con fondo de negro sólido
          de 900×120 para legibilidad:
            "1.000 personas → 1.000 agentes"
          Footnote: "Park et al., 2024".

FASE B · El 85% (f720–1320)
f720–780  La grilla se desatura a hairline y baja a scale 0.85,
          quedando como textura de fondo. NO desaparece.
f780–1020 <RPMGauge /> recompuesto vertical: arco de 240° ocupando
          720×720, centrado. Aguja con spring hasta 85.
          Centro: "85%" en Display XL, tabular-nums.
f1020–1320 Debajo del gauge, sublínea OBLIGATORIA en Body, dos líneas,
          revelado con stagger 24f:
            "de la precisión con la que un humano"
            "se responde a sí mismo dos semanas después"
          Sin rojo. Este número es evidencia, no villano.

FASE C · Finetuning (f1320–1740)
f1320–1380 Wipe.
f1380–1620 <ComparativeGauge /> en dos barras horizontales apiladas:
            "Modelo base"        → barra bone al 62%
            "Modelo finetuneado" → barra bone al 88%, se dibuja después
          Delta "+26%" en Display L entrando a la derecha.
f1620–1740 Footnote: "EMNLP 2025 · 2.9M respuestas · 210 experimentos".

FASE D · Clientes (f1740–2100)
f1740–2040 Grilla 2×3 de logos en <QuotedAsset /> sin marco individual
          (excepción: los logos van sin borde, solo monocromo bone 70%),
          fade-in con stagger 30f:
            CVS Health · Gallup · Deloitte · Itaú · Wealthfront · Suntory
f2040–2100 Sobreimpreso abajo, Footnote muted, OBLIGATORIO:
            "Datos reportados por la compañía."

FASE E · El límite (f2100–2700)
f2100–2160 Wipe. Split VERTICAL (no diagonal — acá el corte es
          conceptual y merece otra sintaxis): dos mitades apiladas,
          separadas por una línea hairline en y=850.
f2160–2460 Mitad superior: "COMPORTAMIENTO DECLARADO" en Label, y una
          barra bone llena de 936×80.
          Mitad inferior: "COMPORTAMIENTO REVELADO" en Label, y una
          barra al 60% con BORDE PUNTEADO ROJO de 2px (uso 3/4).
          El dash del borde rojo se desplaza lentamente (offset animado,
          linear permitido acá) — es el único movimiento continuo del
          episodio, y marca inestabilidad.
f2460–2700 Entra debajo, en Body:
            "El modelo de confianza es una admisión de incertidumbre."
          Transición FULL→SPLIT en los últimos 20f.

┌──────────────────────────────────────────────────────────┐
│ BLOQUE 5 — B5_Cierre · SPLIT · 2100f (3:50–5:00)         │
└──────────────────────────────────────────────────────────┘
70 segundos en split. Es el bloque más largo a cámara: el pane superior
tiene que sostener con cambios cada 3–4s sin robar atención.

FASE A · El reprecio (f0–720)
f0–360    <SeriesMap /> como loop cerrado de 4 nodos, recompuesto en
          rombo vertical dentro de 1080×960:
            Hipótesis (arriba) → Simulación (derecha) →
            Lectura (abajo) → Decisión (izquierda) → vuelve
          Primera vuelta: 240f. Cada vuelta siguiente acelera con
          interpolate hasta 30f. Contador de vueltas arriba a la
          derecha, tabular-nums: 1 → 14.
f360–540  Mientras el loop sigue girando rápido, entra sobre él, con
          fondo negro sólido de 900×200:
            "El diferencial ya no es validar."
f540–720  Reemplaza a:
            "Es qué preguntás y cómo leés."

FASE B · Frase ancla (f720–1200)
f720–780  El loop sale por wipe. Negro con grano.
f780–1080 Frase ancla de la serie, palabra por palabra, Display L,
          alineada a la izquierda con margen 72px, stagger 14f,
          revelado 6.3:
            "No gana el que tiene mejor estrategia,
             gana el que da más vueltas."
f1080–1200 Sostiene. Sin movimiento. 4 segundos de quietud deliberada:
          es el punto de mayor densidad del episodio y necesita aire.

FASE C · Las tres preguntas (f1200–2100)
Entran de a una, 240f cada una, y se ACUMULAN en pantalla.
Display M, alineadas a la izquierda, con un numeral en Footnote al
lado izquierdo (01 / 02 / 03) en hairline.
f1200–1440  01 "¿Cuántas versiones probaste este año?"      bone
f1440–1680  02 "¿Cuánto costó cada vuelta?"                 bone
f1680–1920  03 "¿Cuántas darías si costaran cero?"          ROJO (4/4)
f1920–2100  Las tres sostienen. El pane de rostro sigue activo.
            Corte seco a negro en f2100. Sin fade. Sin end card.

# ══════════════════════════════════════════════════════════
# 11 · ESTRUCTURA DE ARCHIVOS
# ══════════════════════════════════════════════════════════
src/
  Root.tsx                      registro de composiciones
  compositions/simile/
    EpisodeMaster.tsx           <Series> + grano + viñeta + subtítulos
    B1_Apertura.tsx
    B2_DatoYAgentes.tsx
    B3_Escepticismo.tsx
    B4_ValidacionYLimite.tsx
    B5_Cierre.tsx
  shared/
    ModeTransition.tsx
    DiagonalWipe.tsx
    QuotedAsset.tsx
    Subtitles.tsx
    FaceP≥ane.tsx               <OffthreadVideo> + encuadre fijo
    Grain.tsx
    Vignette.tsx
    useCue.ts
  components/                   los existentes de la serie, extendidos
    LatencyTimeline.tsx         + variante vertical
    SeriesMap.tsx               + variante rombo
    RPMGauge.tsx                + variante arco 240°
    ComparativeGauge.tsx        + variante apilada
public/
  captions.json
  audio/vo-master.wav
  video/aroll-b1.mp4, aroll-b3.mp4, aroll-b5.mp4
  assets/grain-512.png, smallville-map.png, seriesb-screenshot.png,
         logos/*.svg

# 12 · PROPS
Todas las composiciones con props tipadas con zod: textos, cues de
fallback y duraciones. El objetivo es poder retimear y corregir copy
sin tocar una línea de lógica de animación.

# 13 · CRITERIO DE ACEPTACIÓN
Antes de dar por terminado cada bloque, verificar:
  [ ] Ningún elemento legible por debajo de y=1570
  [ ] Ningún intervalo mayor a 150f sin cambio de estado
  [ ] Ninguna duración fuera de la grilla de 6f
  [ ] Ningún `linear` fuera de las dos excepciones autorizadas
  [ ] Ningún trazo menor a 2px
  [ ] El acento rojo aparece exactamente 4 veces en el episodio
  [ ] Todo activo externo tiene marco y pie de fuente