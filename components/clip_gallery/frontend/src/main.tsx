/**
 * Monta la galeria sobre un host concreto.
 *
 * Es el unico lugar que elige la implementacion: cambiar `createStreamlitHost`
 * por `createHttpHost` el dia que exista la API es todo lo que hace falta aca.
 */
import React, { useCallback, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { createStreamlitHost } from "./bridge.streamlit";
import type { HostPayload } from "./bridge";
import { ClipGallery } from "./ClipGallery";

const host = createStreamlitHost();

const App: React.FC = () => {
  const [payload, setPayload] = useState<HostPayload | null>(null);

  useEffect(() => {
    const off = host.subscribe(setPayload);
    host.ready();
    return off;
  }, []);

  const onCommit = useCallback((value: unknown) => host.commit(value), []);
  const onHeight = useCallback((px: number) => host.setHeight(px), []);

  if (!payload) return null;
  return (
    <ClipGallery
      args={payload.args}
      theme={payload.theme}
      onCommit={onCommit}
      onHeight={onHeight}
    />
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
