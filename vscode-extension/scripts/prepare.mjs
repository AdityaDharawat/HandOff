import { copyFile, mkdir, readdir } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const extension = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repo = resolve(extension, "..");
const python = process.env.HANDOFF_BUILD_PYTHON || "python";
const assets = resolve(repo, "src/handoff/dashboard");
const media = resolve(extension, "media");
const engine = resolve(extension, "engine");
await mkdir(engine, { recursive: true });
for (const name of ["index.html", "style.css", "app.js"]) {
  await copyFile(resolve(assets, name), resolve(media, name));
}
await copyFile(resolve(repo, "LICENSE"), resolve(extension, "LICENSE"));
const build = spawnSync(python, ["-m", "build", "--wheel", "--no-isolation", "--outdir", engine],
  { cwd: repo, stdio: "inherit", shell: false, env: { ...process.env, SOURCE_DATE_EPOCH: "315532800" } });
if (build.error || build.status !== 0) throw build.error || Error("Engine wheel build failed.");
if (!(await readdir(engine)).some((name) => name.endsWith(".whl"))) throw Error("Engine wheel is missing.");
