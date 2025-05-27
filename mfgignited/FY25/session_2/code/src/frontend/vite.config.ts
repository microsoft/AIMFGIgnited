import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    optimizeDeps: {
        esbuildOptions: {
            target: "esnext"
        }
    },
    build: {
        outDir: "../backend/static",
        emptyOutDir: true,
        sourcemap: true,
        target: "esnext"
    },
    server: {
        proxy: {
            "/chat": {
                target: "http://localhost:5000"
            },
            "/list_indexes": {
                target: "http://localhost:5000"
            },
            "/get_citation_doc": {
                target: "http://localhost:5000"
            }
        }
    }
});
