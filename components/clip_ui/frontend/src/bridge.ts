/**
 * La interfaz que separa la UI de su host.
 *
 * Las pantallas hablan SOLO este contrato. Hoy lo implementa `bridge.streamlit.ts`
 * (iframe + postMessage); mañana, cuando exista la API, lo implementa un
 * `bridge.http.ts` que hace fetch/SSE. Ningún otro archivo del frontend
 * importa nada de Streamlit — esa es la regla que hace la mudanza barata.
 */
import type { Theme } from "./types";

/** `A` es el contrato de la pantalla que se esté montando. */
export interface HostPayload<A = unknown> {
  args: A;
  theme?: Theme;
}

export interface Host {
  /** Se llama con los datos cada vez que el host los refresca. Devuelve el "desuscribir". */
  subscribe(cb: (payload: HostPayload<any>) => void): () => void;
  /** Manda el estado editado de vuelta al host. */
  commit(value: unknown): void;
  /** Avisa cuánto mide el contenido (el iframe no se autodimensiona). */
  setHeight(px: number): void;
  /** El host ya puede mandar datos. */
  ready(): void;
}
