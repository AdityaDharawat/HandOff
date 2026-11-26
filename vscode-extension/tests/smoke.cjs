const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const vscode = require("vscode");

exports.run = async function () {
  const extension = vscode.extensions.getExtension("handoff-local.handoff-project-intelligence");
  assert.ok(extension, "HandOff extension is visible to the development host");
  await extension.activate();
  const commands = await vscode.commands.getCommands(true);
  for (const name of ["analyze", "dashboard", "refresh", "generate", "export", "features", "architecture", "validate", "risks"]) {
    assert.ok(commands.includes("handoff." + name), name + " is registered");
  }
  await vscode.workspace.getConfiguration("handoff").update("pythonPath",
    process.env.HANDOFF_SMOKE_PYTHON, vscode.ConfigurationTarget.Global);
  const result = await vscode.commands.executeCommand("handoff.analyze");
  assert.equal(result?.snapshot.project, path.basename(vscode.workspace.workspaceFolders[0].uri.fsPath));
  assert.ok(result?.counts.files > 0 && result?.edges.length > 0);
  await vscode.commands.executeCommand("handoff.architecture");
  assert.ok(vscode.window.tabGroups.all.some(group => group.tabs.some(tab =>
    tab.input instanceof vscode.TabInputWebview && tab.label === "HandOff")), "HandOff webview is open");
  if (process.env.HANDOFF_SMOKE_RESULT) {
    await fs.writeFile(process.env.HANDOFF_SMOKE_RESULT, JSON.stringify({
      files: result.counts.files, edges: result.edges.length, commands: 9, webview: true,
    }));
  }
};
