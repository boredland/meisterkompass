import { resolve } from "node:path";
import { defineConfig } from "vite";

// Repo root holds the checked-in data/ dir, which we import at build time.
const repoRoot = resolve(__dirname, "..");

// Base path: "/" for a custom domain (meisterkompass.de). For a GitHub Pages
// project site (user.github.io/<repo>/) set VITE_BASE=/<repo>/ in CI.
const base = process.env.VITE_BASE || "/";

export default defineConfig({
  root: __dirname,
  base,
  resolve: {
    alias: { "@data": resolve(repoRoot, "data") },
  },
  server: {
    fs: { allow: [repoRoot] },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: resolve(__dirname, "index.html"),
        afbg: resolve(__dirname, "afbg.html"),
        about: resolve(__dirname, "about.html"),
        imprint: resolve(__dirname, "imprint.html"),
      },
    },
  },
});
