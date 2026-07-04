import { existsSync } from "node:fs";
import { cp, mkdir } from "node:fs/promises";

await mkdir("dist", { recursive: true });
await cp("site", "dist", { recursive: true });
if (existsSync("data/data.json")) {
  await mkdir("dist/data", { recursive: true });
  await cp("data/data.json", "dist/data/data.json");
}
console.log("Built static site to dist/");
