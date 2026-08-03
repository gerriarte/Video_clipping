# Episodio · Criterio — mapa de cues

Estado real contra el VO grabado (`public/audio/vo-criterio.mp3`,
268.8 s de voz). Los 39 cues matchean contra la transcripción; ninguno
quedó interpolado. Verificar con `npm run cues`.

**La palabra manda, el frame no.** Si al regrabar cambiaste una
formulación, se corrige el `needle` en `CUE_SCRIPT` (`src/shared/cues.ts`),
nunca un frame.

---

## C1 · Arranque — 0:00–0:50

| Cue | Momento | Dispara |
|---|---|---|
| *(entrada)* | 0:00 | Placa de apertura: "Una contradicción que nadie ve" |
| `10 años` | 0:07 | Panel superior: "Todo aviso pide · 10 años de experiencia" |
| `45` | 0:11 | Panel inferior en rojo, y el trazo que los une **se parte** |
| `impecable` | 0:19 | Wipe. "Impecable." |
| `perfecto` | 0:21 | "Perfecto." |
| `pulido` | 0:22 | "Pulido." |
| `descarta` | 0:31 | Wipe. La pregunta que queda abierta |

El hueco en el trazo es todo el bloque. Una balanza habría dicho "una
pesa más" y el argumento no es ese: es que las dos son verdad a la vez.

Las tres cualidades entran **una por palabra**, no escalonadas a ojo: el
VO las dispara en tres segundos y ese ritmo es el chiste.

## C2 · Qué es esto en serio — 0:50–1:32

| Cue | Momento | Dispara |
|---|---|---|
| `no es información` | 0:51 | "Información acumulada" en muted |
| *(+36f)* | | El tachado **se dibuja** encima. El borrado se ve en vivo |
| `error acumulado` | 0:55 | La definición real, en displayXL |
| `decisión` | 1:00 | "Haber tomado una decisión" |
| `equivocarte` | 1:03 | "Haber pagado el costo de equivocarte" |
| `cuerpo` | 1:06 | "Y que te haya quedado en el cuerpo" |
| `nunca perdió un cliente` | 1:17 | Wipe. Las dos columnas de acumulación |
| `consecuencias` | 1:26 | Wipe. Frase de cierre |

Las columnas son el visual central: izquierda se llena sola, continua e
ilegible de densa; derecha suma pocas marcas y cada una entra de golpe.
**La asimetría de ritmo es el argumento**, no la altura. El ritmo de las
dos se calcula sobre lo que dura el tramo, así que la izquierda siempre
termina de cargar antes del wipe.

Las tres condiciones del medio no estaban en el plan original: el VO
tarda veinte segundos en desplegar la definición y la placa se quedaba
quieta todo ese tramo.

## C3 · Lo que cambió de precio — 1:32–2:25

| Cue | Momento | Dispara |
|---|---|---|
| `tendió a cero` | 1:32 | Se dibujan las dos curvas y el punto de cruce |
| `escaso` | 1:46 | La frase de la mudanza del valor |
| `trampa` | 1:54 | Wipe. "No toda experiencia es criterio" |
| `costumbre` | 2:01 | **Rojo 2/4.** El bloque descartado por el filtro |
| `datos incompletos` | 2:08 | Lo que sí pasa el filtro (1) |
| `explicar` | 2:13 | Lo que sí pasa el filtro (2) |
| `conviene` | 2:16 | Lo que sí pasa el filtro (3) |
| `disparó` | 2:20 | Wipe. Cierre del bloque |

Sin el filtro, este bloque se lee como "la experiencia vale" — que es
exactamente lo que el guion no dice.

## C4 · El absurdo — 2:25–3:18

| Cue | Momento | Dispara |
|---|---|---|
| `lo tira` | 2:25 | Se dibuja la línea de vida productiva (20 → 85) |
| `los 65` | 2:38 | **Rojo 3/4.** El tramo descartado se marca en punteado |
| `de vos` | 2:45 | Wipe. El giro: "Te vengo a hablar de vos" |
| `sueldos de guerra` | 2:55 | Wipe. La primera etiqueta de precio |
| `remate` | 3:04 | La segunda etiqueta |
| `ingrediente equivocado` | 3:10 | Wipe. Veredicto |

Todo el bloque va a cámara cuando exista el A-roll; mientras tanto, el
pane de abajo lo ocupa el motivo del descarte. En voz en off suena a
denuncia; a cámara suena a acusación amable, que es lo que corresponde.

## C5 · La traba y la salida — 3:18–4:31

| Cue | Momento | Dispara |
|---|---|---|
| `identidad` | 3:19 | "La traba no es capacidad. Es identidad." |
| `20 dólares` | 3:30 | Contador a USD 20 |
| `caro y lento` | 3:37 | Wipe. El espejo del lado del espectador |
| `era lo difícil` | 3:41 | La segunda línea del espejo |
| `desarmados` | 3:52 | **El rostro sale.** Modo FULL. Los dos círculos |
| `existe` (1ª) | 3:55 | Etiqueta izquierda: criterio para resolverlo |
| `existe` (2ª) | 3:58 | Etiqueta derecha: capacidad de ejecutarlo |
| `pueden` | 4:06 | **Rojo 4/4.** Los círculos se solapan y el área común se pinta |
| `producís` | 4:14 | Wipe. Primera pregunta *(el rostro vuelve)* |
| `ejecución` | 4:20 | Segunda pregunta |
| `plata` | 4:25 | Veredicto de cierre |

Es el único bloque que cambia de modo por dentro. No es capricho de
layout: marca el único momento del video donde el argumento deja de ser
diagnóstico y pasa a ser salida. El área de solape queda **vacía** a
propósito — lo que va ahí lo pone el espectador.

El corte a las preguntas va en `producís` y no en `último trimestre`
(que está en la tabla y se puede volver a usar): entre una cosa y la otra
el VO mete cuatro segundos de bisagra y la pantalla quedaba vacía.

---

## Presupuesto del acento

Cuatro usos en cuatro minutos y medio. Están marcados en el código.

1. **C1** — el corte en 45 años
2. **C3** — "Costumbre"
3. **C4** — el tramo de vida productiva descartado
4. **C5** — el solape de los dos círculos

Los tres primeros son el villano estructural. El cuarto es activación:
es lo único en todo el video que se lee como salida.

## Reparto de bloques

Los bloques duran lo que tarda el VO en decirlos. Estos números salen de
`npm run cues`, no de una planilla:

| Bloque | Frames | Tiempo |
|---|---|---|
| C1 · Arranque | 1515 | 0:00–0:50 |
| C2 · Qué es | 1245 | 0:50–1:32 |
| C3 · Precio | 1595 | 1:32–2:25 |
| C4 · Absurdo | 1608 | 2:25–3:18 |
| C5 · Salida | 2262 | 3:18–4:31 |

**Total: 8135 frames · 4:31.** El archivo de VO dura 5:47, pero los
últimos 78 segundos son silencio (ahí Whisper alucinaba el crédito de
Amara, que el script de transcripción descarta).

## Puesta en marcha

```bash
npm install
npm run transcribe      # si se regrabó el VO
npm run cues            # verificar los 39 cues
npm run dev             # abrir CriterioMaster
npm run render
```
