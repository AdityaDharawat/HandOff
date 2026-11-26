import * as vscode from "vscode";
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { readFile, readdir, realpath, stat } from "node:fs/promises";
import * as path from "node:path";

type EngineCommand = "analyze" | "generate" | "validate" | "version";
type View = "overview" | "architecture" | "features" | "debt" | "dependencies" | "quality" | "risks" | "handover";
const views = new Set<View>(["overview", "architecture", "features", "debt", "dependencies", "quality", "risks", "handover"]);
type Analysis = {
  schema_version: 1;
  snapshot: { project: string; files: { path: string }[]; evidence: unknown[]; findings: unknown[] };
  edges: unknown[];
  packages: unknown[];
  counts: { files: number; bytes: number; evidence: number; status: Record<string, number> };
  languages: Record<string, number>;
  analysis_notes: string[];
};
type Executable = { command: string; prefix: string[] };
type ArtifactSet = { directory: string; files: string[] };
type State = { model?: Analysis; artifacts?: ArtifactSet };

function object(input: unknown): Record<string, unknown> {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw Error("Invalid engine data.");
  return input as Record<string, unknown>;
}

function analysis(input: unknown): Analysis {
  const result = object(input);
  const snapshot = object(result.snapshot);
  const counts = object(result.counts);
  if (result.schema_version !== 1 || typeof snapshot.project !== "string" ||
    !Array.isArray(snapshot.files) || !snapshot.files.every((file: unknown) => typeof object(file).path === "string") ||
    !Array.isArray(snapshot.evidence) || !Array.isArray(snapshot.findings) ||
    !Array.isArray(result.edges) || !Array.isArray(result.packages) || !Array.isArray(result.analysis_notes) ||
    typeof counts.files !== "number" || typeof counts.evidence !== "number") throw Error("Unsupported analysis data.");
  return result as unknown as Analysis;
}

function artifacts(input: unknown): ArtifactSet {
  const result = object(input);
  if (typeof result.directory !== "string" || !Array.isArray(result.files) ||
    !result.files.every((name: unknown) => typeof name === "string")) throw Error("Invalid artifact list.");
  return { directory: result.directory, files: result.files };
}

function subprocess(executable: Executable, args: string[], cwd: string, timeout: number,
  token?: vscode.CancellationToken): Promise<string> {
  return new Promise((resolve, reject) => {
    const process = spawn(executable.command, [...executable.prefix, ...args], {
      cwd, windowsHide: true, shell: false, stdio: ["ignore", "pipe", "pipe"],
      env: { ...globalThis.process.env, PYTHONPATH: "", PYTHONHOME: "", PYTHONUTF8: "1" },
    });
    const buffers: Buffer[] = [];
    let size = 0;
    let settled = false;
    let cancellation: vscode.Disposable | undefined;
    const finish = (error?: Error, value = "") => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      cancellation?.dispose();
      if (error) reject(error); else resolve(value);
    };
    const stop = (error: Error) => { process.kill(); finish(error); };
    const timer = setTimeout(() => stop(Error("The local engine timed out. Check the workspace scan limits.")), timeout);
    process.stdout.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > 32 * 1024 * 1024) stop(Error("The local engine exceeded its output limit."));
      else if (!settled) buffers.push(chunk);
    });
    process.stderr.resume();
    process.on("error", () => finish(Error("Could not start the local Python engine.")));
    process.on("close", code => code === 0
      ? finish(undefined, Buffer.concat(buffers).toString("utf8"))
      : finish(Error("The local engine exited without a usable result.")));
    if (token?.isCancellationRequested) stop(new vscode.CancellationError());
    else cancellation = token?.onCancellationRequested(() => stop(new vscode.CancellationError()));
  });
}

async function engineCall(executable: Executable, extensionPath: string, command: EngineCommand,
  folder: vscode.WorkspaceFolder, output: string, token?: vscode.CancellationToken): Promise<unknown> {
  const raw = await subprocess(executable, ["-I", "-m", "handoff.bridge", command,
    "--path", folder.uri.fsPath, "--output", output], extensionPath, 180_000, token);
  const envelope = object(JSON.parse(raw));
  if (envelope.protocol !== 1) throw Error("This Python environment has an incompatible HandOff engine.");
  if (!envelope.ok) {
    const message = typeof envelope.error === "string" ? envelope.error : "The engine operation failed.";
    throw Error(message.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 1000));
  }
  return envelope.result;
}

async function workspacePath(folder: vscode.WorkspaceFolder, relative: string): Promise<vscode.Uri> {
  const parts = relative.split("/");
  if (!parts.length || parts.some((part) => !part || part === "." || part === ".." || /[\\:\u0000-\u001f]/.test(part))) {
    throw Error("The selected file is outside the workspace boundary.");
  }
  const root = await realpath(folder.uri.fsPath);
  const target = await realpath(path.join(root, ...parts));
  const difference = path.relative(root, target);
  if (!difference || difference === ".." || difference.startsWith(".." + path.sep) || path.isAbsolute(difference)) {
    throw Error("The selected file is outside the workspace boundary.");
  }
  if (!(await stat(target)).isFile()) throw Error("The evidence source is not a regular file.");
  return vscode.Uri.file(target);
}

class Sidebar extends vscode.TreeItem {}
const sidebarEntries: [string, string, string][] = [
  ["Analyze repository", "analyze", "play"], ["Overview", "dashboard", "dashboard"],
  ["Architecture", "architecture", "type-hierarchy"], ["Implementation", "features", "list-tree"],
  ["Risks and next steps", "risks", "warning"], ["Generate reports", "generate", "file-text"],
  ["Export package", "export", "package"], ["Validate analysis", "validate", "check"],
];

export function activate(context: vscode.ExtensionContext): void {
  const states = new Map<string, State>();
  const engineInstalls = new Map<string, Promise<void>>();
  let panel: vscode.WebviewPanel | undefined;
  let folder: vscode.WorkspaceFolder | undefined;
  let activeView: View = "overview";
  let busy = false;
  let notice = "";
  const extensionPath = context.extensionUri.fsPath;
  const state = (selected: vscode.WorkspaceFolder) => {
    const key = selected.uri.toString();
    if (!states.has(key)) states.set(key, {});
    return states.get(key)!;
  };

  function update(): void {
    if (panel && folder) void panel.webview.postMessage({
      type: "state", model: state(folder).model ?? null, busy, view: activeView, message: notice,
    });
  }

  async function chooseWorkspace(): Promise<vscode.WorkspaceFolder | undefined> {
    if (!vscode.workspace.isTrusted) {
      void vscode.window.showWarningMessage("HandOff analysis requires a trusted local workspace.");
      return;
    }
    const folders = (vscode.workspace.workspaceFolders ?? []).filter(item => item.uri.scheme === "file");
    if (!folders.length) {
      void vscode.window.showInformationMessage("Open a local folder in VS Code to analyze it.");
      return;
    }
    if (folders.length === 1) return folders[0];
    const editor = vscode.window.activeTextEditor?.document.uri;
    const current = editor && vscode.workspace.getWorkspaceFolder(editor);
    return (await vscode.window.showQuickPick(folders.map(item => ({
      label: item.name, description: item === current ? "Active editor workspace" : undefined, item,
    })), { placeHolder: "Choose a workspace to analyze" }))?.item;
  }

  async function interpreter(selected: vscode.WorkspaceFolder, token?: vscode.CancellationToken): Promise<Executable> {
    const explicit = vscode.workspace.getConfiguration("handoff", selected.uri).get<string>("pythonPath", "").trim();
    if (explicit && !path.isAbsolute(explicit)) throw Error("Configure handoff.pythonPath with an absolute Python path.");
    const candidates: Executable[] = explicit ? [{ command: explicit, prefix: [] }] :
      [...(process.platform === "win32" ? [{ command: "py", prefix: ["-3.11"] }, { command: "py", prefix: ["-3"] }] : []),
        { command: "python3", prefix: [] }, { command: "python", prefix: [] }];
    const engineDir = path.join(extensionPath, "engine");
    const wheels = (await readdir(engineDir).catch(() => [])).filter(name => /^handoff_continuity-.*\.whl$/.test(name));
    const wheel = wheels.length === 1 ? path.join(engineDir, wheels[0]) : undefined;
    const digest = wheel ? createHash("sha256").update(await readFile(wheel)).digest("hex").slice(0, 16) : undefined;
    const managedRoot = path.join(context.globalStorageUri.fsPath, `engine-${digest}`);
    const managed: Executable = {
      command: path.join(managedRoot, process.platform === "win32" ? "Scripts/python.exe" : "bin/python"), prefix: [],
    };
    let available: Executable | undefined;
    for (const candidate of [...(!explicit && wheel ? [managed] : []), ...candidates, ...(explicit && wheel ? [managed] : [])]) {
      try {
        const version = await subprocess(candidate, ["-I", "-c", "import sys; print(int(sys.version_info >= (3, 11)))"], extensionPath, 8_000, token);
        if (version.trim() !== "1") continue;
        if (candidate !== managed) available ??= candidate;
        if (candidate === managed || explicit) {
          await engineCall(candidate, extensionPath, "version", selected, ".handoff", token);
          return candidate;
        }
        break;
      } catch (error) {
        if (error instanceof vscode.CancellationError) throw error;
      }
    }
    if (!available) throw Error("Install Python 3.11 or newer, restart VS Code, or set handoff.pythonPath to its absolute executable path.");
    if (!wheel) throw Error("The bundled engine wheel is missing or ambiguous. Reinstall the GitHub Release VSIX.");
    let install = engineInstalls.get(managedRoot);
    if (!install) {
      const bootstrap = available;
      install = (async () => {
        const answer = await vscode.window.showInformationMessage(
          "Install the bundled HandOff engine in a dedicated environment? Python dependencies may be downloaded from your configured package index.",
          { modal: true }, "Install engine");
        if (!answer) throw new vscode.CancellationError();
        try {
          await subprocess(bootstrap, ["-I", "-m", "venv", managedRoot], extensionPath, 90_000);
          await subprocess(managed, ["-I", "-m", "pip", "--require-virtualenv", "install",
            "--disable-pip-version-check", wheel], extensionPath, 180_000);
          await engineCall(managed, extensionPath, "version", selected, ".handoff");
        } catch {
          throw Error("HandOff engine setup failed. Check that Python has venv and pip and that your package index is reachable. You can also set handoff.pythonPath to an environment with the engine installed.");
        }
      })().finally(() => engineInstalls.delete(managedRoot));
      engineInstalls.set(managedRoot, install);
    }
    await install;
    if (token?.isCancellationRequested) throw new vscode.CancellationError();
    return managed;
  }

  async function openDashboard(selected: vscode.WorkspaceFolder, view: View) {
    if (folder?.uri.toString() !== selected.uri.toString() && panel) panel.dispose();
    folder = selected;
    activeView = view;
    if (!busy && !state(selected).model) {
      const output = vscode.workspace.getConfiguration("handoff", selected.uri)
        .get<string>("outputDirectory", ".handoff");
      const saved = await workspacePath(selected, output + "/index.html").catch(() => undefined);
      if (saved) notice = "A saved handover exists. Analyze this workspace to refresh it.";
    }
    if (!panel) {
      const media = vscode.Uri.joinPath(context.extensionUri, "media");
      panel = vscode.window.createWebviewPanel("handoff.dashboard", "HandOff", vscode.ViewColumn.One,
        { enableScripts: true, localResourceRoots: [media], retainContextWhenHidden: true });
      const current = panel;
      const nonce = randomBytes(18).toString("base64");
      const template = await readFile(path.join(media.fsPath, "index.html"), "utf8");
      const scripts = panel.webview.asWebviewUri(vscode.Uri.joinPath(media, "app.js"));
      const css = panel.webview.asWebviewUri(vscode.Uri.joinPath(media, "style.css"));
      panel.webview.html = template.replace("{{POLICY}}", "default-src 'none'; style-src " + panel.webview.cspSource +
        "; script-src 'nonce-" + nonce + "';")
        .replace("{{STYLE}}", '<link href="' + css + '" rel="stylesheet">')
        .replace("{{SCRIPT}}", '<script nonce="' + nonce + '" src="' + scripts + '"></script>')
        .replace("{{DATA}}", "");
      panel.onDidDispose(() => { if (panel === current) panel = undefined; }, undefined, context.subscriptions);
      panel.webview.onDidReceiveMessage(async (raw: unknown) => {
        try {
          const message = object(raw);
          if (message.type === "ready") update();
          else if (message.type === "analyze") await run("analyze", selected);
          else if (message.type === "generate") await run("generate", selected);
          else if (message.type === "export") await run("export", selected);
          else if (message.type === "validate") await run("validate", selected);
          else if (message.type === "artifacts") await openArtifacts(selected);
          else if (message.type === "source" && typeof message.path === "string") {
            if (!state(selected).model?.snapshot.files.some(item => item.path === message.path)) return;
            const uri = await workspacePath(selected, message.path);
            const document = await vscode.workspace.openTextDocument(uri);
            const line = Number.isSafeInteger(message.line) ? Math.min(document.lineCount, Math.max(1, Number(message.line))) : 1;
            await vscode.window.showTextDocument(document, { selection: new vscode.Range(line - 1, 0, line - 1, 0), preview: true });
          }
        } catch (error) {
          notice = error instanceof Error ? error.message : "The requested action could not be completed.";
          update();
          void vscode.window.showErrorMessage(notice);
        }
      }, undefined, context.subscriptions);
    } else panel.reveal();
    update();
  }

  async function openArtifacts(selected: vscode.WorkspaceFolder): Promise<void> {
    const generated = state(selected).artifacts;
    if (!generated) {
      void vscode.window.showInformationMessage("Generate reports to open the output files.");
      return;
    }
    const file = await vscode.window.showQuickPick(generated.files, { placeHolder: "Open a handover artifact" });
    if (file) await vscode.commands.executeCommand("revealFileInOS", await workspacePath(selected, generated.directory + "/" + file));
  }

  async function run(action: EngineCommand | "export", selected: vscode.WorkspaceFolder): Promise<Analysis | ArtifactSet | undefined> {
    if (busy) {
      void vscode.window.showInformationMessage("A HandOff operation is already running.");
      return;
    }
    const settings = vscode.workspace.getConfiguration("handoff", selected.uri);
    const output = settings.get<string>("outputDirectory", ".handoff");
    busy = true;
    notice = "";
    try {
      if (action === "generate" || action === "export") {
        const answer = await vscode.window.showInformationMessage(
          "Write the HandOff package inside this workspace? The ZIP includes any manual notes in its reports.",
          { modal: true }, "Generate package");
        if (!answer) return;
      }
      await openDashboard(selected, action === "analyze" ? activeView : "handover");
      return await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: action === "analyze" ? "HandOff: Analyzing repository" : "HandOff: Preparing handover",
        cancellable: action === "analyze",
      }, async (progress, token) => {
        progress.report({ message: "Checking local engine" });
        const engine = await interpreter(selected, token);
        progress.report({ message: action === "analyze" ? "Reading repository evidence" : "Checking and writing artifacts" });
        const result = await engineCall(engine, extensionPath, action === "export" ? "generate" : action, selected, output, token);
        if (action === "analyze") {
          const model = analysis(result);
          state(selected).model = model;
          notice = "Analysis ready.";
          return model;
        } else if (action === "validate") {
          const issues = object(result).issues;
          if (!Array.isArray(issues) || !issues.every((item: unknown) => typeof item === "string")) throw Error("Invalid validation response.");
          notice = issues.length ? "Validation found " + issues.length + " issue(s). " + issues.slice(0, 3).join(" ") : "Handover package validated.";
        } else {
          const generated = artifacts(result);
          state(selected).artifacts = generated;
          notice = "Handover package saved to " + generated.directory + ".";
          if (action === "export") await vscode.commands.executeCommand("revealFileInOS",
            await workspacePath(selected, generated.directory + "/handover.zip"));
          return generated;
        }
      });
    } catch (error) {
      notice = error instanceof vscode.CancellationError ? "Analysis cancelled." :
        (error instanceof Error ? error.message : "HandOff operation failed.");
      if (!(error instanceof vscode.CancellationError)) void vscode.window.showErrorMessage(notice);
    } finally { busy = false; update(); }
  }

  const provider: vscode.TreeDataProvider<Sidebar> = {
    getTreeItem: item => item,
    getChildren: () => sidebarEntries.map(([label, command, icon]) => {
      const item = new Sidebar(label);
      item.iconPath = new vscode.ThemeIcon(icon);
      item.command = { title: label, command: "handoff." + command };
      return item;
    }),
  };
  context.subscriptions.push(vscode.window.registerTreeDataProvider("handoff.workspace", provider));
  const routes: Record<string, View> = { dashboard: "overview", features: "features", architecture: "architecture", risks: "risks" };
  for (const command of ["analyze", "dashboard", "refresh", "generate", "export", "features", "architecture", "validate", "risks"]) {
    context.subscriptions.push(vscode.commands.registerCommand("handoff." + command, async () => {
      try {
        const selected = await chooseWorkspace();
        if (!selected) return;
        if (routes[command] && views.has(routes[command])) await openDashboard(selected, routes[command]);
        else if (command === "analyze" || command === "refresh") return await run("analyze", selected);
        else if (command === "generate" || command === "export" || command === "validate") return await run(command, selected);
      } catch (error) { void vscode.window.showErrorMessage(error instanceof Error ? error.message : "Could not open HandOff."); }
    }));
  }
}
