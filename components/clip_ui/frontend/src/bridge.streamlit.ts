/**
 * Implementación del Host sobre Streamlit.
 *
 * ES EL ÚNICO ARCHIVO DEL FRONTEND QUE IMPORTA `streamlit-component-lib`.
 * Si algún día grep encuentra ese import en otro lado, la mudanza a la API
 * dejó de ser gratis.
 */
import { Streamlit, RenderData } from "streamlit-component-lib";
import type { Host, HostPayload } from "./bridge";
import type { Theme } from "./types";

export function createStreamlitHost(): Host {
  return {
    subscribe(cb: (payload: HostPayload) => void) {
      const handler = (event: Event) => {
        const data = (event as CustomEvent<RenderData>).detail;
        cb({
          args: data.args,
          theme: data.theme as unknown as Theme | undefined,
        });
      };
      Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, handler);
      return () =>
        Streamlit.events.removeEventListener(Streamlit.RENDER_EVENT, handler);
    },
    commit(value: unknown) {
      Streamlit.setComponentValue(value);
    },
    setHeight(px: number) {
      Streamlit.setFrameHeight(px);
    },
    ready() {
      Streamlit.setComponentReady();
    },
  };
}
