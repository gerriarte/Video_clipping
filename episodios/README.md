# Episodios

Videos animados verticales, sincronizados al VO. Cada episodio es un
proyecto Remotion independiente: se puede archivar, mover o rehacer sin
tocar a los demás ni a la app de cortes.

| Carpeta | Estado |
|---|---|
| [`criterio/`](criterio/) | ✅ Renderizado — 4:31, 39 cues contra el audio. Falta el A-roll (3 clips) |
| [`simile/`](simile/) | 📥 Solo material de entrada: guion, brief y assets. Falta el VO |
| [`_plantilla/`](_plantilla/) | Base para episodios nuevos. Se copia, no se edita |
| `_archivo/` | `criterio-v1`: la versión previa, sin sincronizar. Referencia visual, no se usa |

## Para entregar material

👉 **[COMO-ENTREGAR.md](COMO-ENTREGAR.md)** — qué va en `_entrada/` y por qué.

## Empezar uno nuevo

```bash
cp -r episodios/_plantilla episodios/<nombre>
cd episodios/<nombre> && npm install && npm run dev
```

## La idea del sistema

Nada de lo que se ve está atado a un frame escrito a mano: **cada estado
visual cuelga de una palabra del VO**. Se regraba la locución, se
retranscribe, y el episodio entero se reacomoda solo — duración de cada
bloque incluida. Lo que se corrige cuando algo no cae donde va es la
palabra en la tabla de cues, nunca el frame.

Detalle en el README de cada episodio y en [`_plantilla/README.md`](_plantilla/README.md).
