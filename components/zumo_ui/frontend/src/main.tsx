/**
 * Monta la pantalla que pida el host, sobre un host concreto.
 *
 * Es el unico lugar que elige la implementacion del Host: cambiar
 * `createStreamlitHost` por `createHttpHost` el dia que exista la API es todo
 * lo que hace falta aca. Y es el unico que sabe que hay mas de una pantalla:
 * cada una recibe sus props y no se entera del resto.
 */
import React, { useCallback, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { createStreamlitHost } from "./bridge.streamlit";
import type { HostPayload } from "./bridge";
import { ClipGallery } from "./gallery/ClipGallery";
import type { GalleryArgs } from "./gallery/types";
import { ClipPublish } from "./publish/ClipPublish";
import type { PublishArgs } from "./publish/types";

const host = createStreamlitHost();

type Args = (GalleryArgs & { screen?: "gallery" }) | PublishArgs;

const App: React.FC = () => {
  const [payload, setPayload] = useState<HostPayload<Args> | null>(null);

  useEffect(() => {
    const off = host.subscribe(setPayload);
    host.ready();
    return off;
  }, []);

  const onCommit = useCallback((value: unknown) => host.commit(value), []);
  const onHeight = useCallback((px: number) => host.setHeight(px), []);

  if (!payload) return null;

  if (payload.args?.screen === "publish") {
    return (
      <ClipPublish
        args={payload.args as PublishArgs}
        theme={payload.theme}
        onCommit={onCommit}
        onHeight={onHeight}
      />
    );
  }

  return (
    <ClipGallery
      args={payload.args as GalleryArgs}
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
