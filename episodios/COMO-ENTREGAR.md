# Cómo entregar el material de un episodio

Un episodio = una carpeta acá adentro. Todo lo que me pasás va en su
`_entrada/`; todo lo que sale del proyecto va en `out/`. Si el material
llega así, empezar a trabajar no requiere ninguna arqueología.

```
episodios/<nombre>/
├── _entrada/          ← ESTO LO DEJÁS VOS
│   ├── guion.md       ← el guion, con las palabras-cue en negrita
│   ├── vo.mp3         ← la locución
│   ├── brief.md       ← qué querés que pase visualmente
│   ├── aroll/         ← clips a cámara (si hay)
│   └── assets/        ← logos, capturas, referencias
├── src/ public/       ← el proyecto Remotion
└── out/               ← el render final
```

## Arrancar un episodio nuevo

```bash
cp -r episodios/_plantilla episodios/<nombre>
cd episodios/<nombre> && npm install
# dejás el material en _entrada/
npm run ingest        # lo copia a donde el proyecto lo espera
npm run transcribe    # VO → captions.json (palabra por palabra)
npm run cues          # verifica que cada cue haya matcheado
npm run dev           # Remotion Studio
```

La plantilla ya trae toda la maquinaria funcionando: medición de la voz,
textura de fondo, pane animado, resolución de cues por palabra y
subtítulos. Lo que se escribe por episodio es el copy y los bloques.

---

## Las cuatro cosas

### 1 · `vo.mp3` — la locución

**Una sola toma, sin edición.** No necesito calidad de estudio, necesito
tu cadencia real: el VO es el reloj de todo el episodio. Cada animación
cuelga de una palabra, así que si después regrabás, se retranscribe y
todo se reacomoda solo sin tocar una línea de código.

- Formato: mp3 o wav, como salga.
- Si al final del archivo queda silencio, no importa: se recorta solo.
- Si regrabás una parte suelta y la pegás, avisame — los timestamps de la
  transcripción se calculan sobre el archivo entero.

### 2 · `guion.md` — el guion con los cues marcados

Lo más importante de toda la entrega. Dos reglas:

**a) Las palabras-cue en negrita.** Cada negrita es un momento visual:

```markdown
Hoy una búsqueda te pide **10 años** de experiencia
y filtra a todo el que tiene más de **45**.
```

**b) Tiene que decir lo que realmente dijiste.** Los cues se buscan
literalmente en la transcripción del VO. En Criterio, cuatro de veintitrés
no matchearon por diferencias mínimas entre el guion y la grabación:

| El guion decía | Vos dijiste |
|---|---|
| `diez años` | **10 años** |
| `cuarenta y cinco` | **45** |
| `veinte dólares` | **20 dólares** |
| `plausible` | *(esa frase no se grabó)* |

Ninguna rompe nada —lo que no matchea se ubica proporcionalmente y sigue— 
pero cada una es un visual que cae unos segundos corrido hasta que lo
corrijo a mano. Si grabaste distinto del guion, la forma más rápida de
arreglarlo es pasarme el guion **actualizado a lo grabado**.

Elegí como cue **palabras poco frecuentes**: "costumbre", "desarmados",
"remate". Una palabra que aparece cinco veces en el guion funciona igual
(la búsqueda avanza en orden), pero es más frágil si cambia el orden.

### 3 · `brief.md` — qué querés que pase

Puede ser desprolijo, en punteo, o dictado. Lo que sirve:

- **La tesis en una línea.** Si el episodio se resume en una frase, esa
  frase decide el 80% de las decisiones visuales.
- **Qué NO querés.** Es más útil que lo que sí. "Nada de karaoke amarillo",
  "sin stock footage", "el rojo casi no se usa".
- **Los momentos que tienen que pegar.** Dos o tres, no diez.
- **Datos duros** con su fuente, si el episodio los muestra en pantalla.

### 4 · `aroll/` y `assets/`

- **`aroll/`** — los clips a cámara. Si está vacío, el lugar del rostro lo
  ocupa un pane animado con la voz dibujada, y el episodio funciona igual.
  Cuando existan, se copian con `npm run ingest` y el bloque vuelve al
  split sin tocar animación. **Encuadre:** los ojos a `y ≈ 1290` del
  canvas de 1920.
- **`assets/`** — logos, capturas, figuras. Todo activo externo entra
  enmarcado y con pie de fuente; si vas a mostrar algo de un tercero,
  pasame también de dónde salió.

---

## Lo que te devuelvo

En `out/` el mp4, y en el README del episodio el estado real: cuántos
cues matchearon, dónde quedó cada bloque y qué falta. Si algo no se pudo
hacer, va escrito ahí — no en un mensaje que se pierde.

## Nombres

Carpeta del episodio en minúscula y sin espacios: `criterio`, `simile`,
`multiasking`. Es también el nombre que queda en el render.
