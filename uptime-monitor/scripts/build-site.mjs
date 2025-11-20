import { cp, mkdir } from "node:fs/promises";

await mkdir("dist", { recursive: true });
await cp("site", "dist", { recursive: true });
// data/data.json is written by check.mjs
console.log("Built static site to dist/");

