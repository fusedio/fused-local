// build.js
import esbuild from "esbuild";

esbuild.build({
    entryPoints: ["./js/index.tsx"],
    bundle: true,
    // minify: true,
    target: ["es2022"],
    outdir: "src/fused_local/frontend",
    format: "esm",
    sourcemap: true,
});