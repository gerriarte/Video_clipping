import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" → assets con rutas relativas, así Streamlit los sirve bajo la URL
// del componente. Salida a "build/" (que se commitea para desplegar sin npm).
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "build",
    emptyOutDir: true,
  },
});
