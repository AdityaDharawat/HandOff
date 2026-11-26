import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const [browser, html, capture, architectureCapture] = process.argv.slice(2);
assert(browser && html && capture, "Pass Chromium executable, exported index.html, and PNG destination");
const profile = await mkdtemp(resolve(".verification-browser-"));
const processHandle = spawn(browser, [
  "--headless", "--disable-gpu", "--disable-extensions", "--no-first-run",
  "--disable-background-networking", "--disable-sync", "--remote-debugging-port=0",
  "--user-data-dir=" + profile, pathToFileURL(resolve(html)).href,
], { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const endpoint = new Promise((resolve, reject) => {
  processHandle.on("error", reject);
  processHandle.stderr.setEncoding("utf8");
  processHandle.stderr.on("data", (data) => {
    const match = data.match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (match) resolve(match[1]);
  });
});
try {
  const root = new URL(await Promise.race([endpoint, sleep(10000).then(() => { throw Error("Chromium startup timed out."); })]));
  const targets = await (await fetch("http://" + root.host + "/json")).json();
  const page = targets.find(item => item.type === "page" && item.url.startsWith("file:"));
  assert(page);
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let serial = 0;
  const pending = new Map();
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) { pending.get(message.id)?.(message); pending.delete(message.id); }
  };
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, (message) => message.error ? reject(Error(message.error.message)) : resolve(message.result));
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evalPage = async (expression) => {
    const result = await call("Runtime.evaluate", { expression, returnByValue: true });
    if (result.exceptionDetails) throw Error(result.exceptionDetails.text);
    return result.result.value;
  };
  await call("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await sleep(750);
  assert.equal(await evalPage("document.querySelectorAll('nav button').length"), 8);
  assert.equal(await evalPage("document.querySelectorAll('.metrics .metric').length"), 4);
  assert(await evalPage("document.querySelectorAll('svg [role=button]').length"), "graph contains selectable nodes");
  const desktop = await call("Page.captureScreenshot", { format: "png" });
  await writeFile(capture, Buffer.from(desktop.data, "base64"));
  assert(await evalPage(`
    document.querySelector('svg [role=button]').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    document.querySelector('.graph-tools + .row a.source') !== null
  `), "Keyboard graph selection reveals source links");
  assert(await evalPage(`
    const graph = document.querySelector('svg.graph');
    const initial = graph.getAttribute('viewBox');
    document.querySelector('.graph-tools button').click();
    graph.getAttribute('viewBox') !== initial
  `), "Zoom changes the graph viewport");
  if (architectureCapture) {
    await evalPage("document.querySelectorAll('nav button')[1].click()");
    const architecture = await call("Page.captureScreenshot", { format: "png" });
    await writeFile(architectureCapture, Buffer.from(architecture.data, "base64"));
  }
  for (const index of [1, 2, 3, 4, 5, 6, 7]) {
    assert(await evalPage("document.querySelectorAll('nav button')[" + index + "].click(); document.querySelector('main h1').textContent"));
  }
  assert(await evalPage("document.querySelector('a[download][href=\"reports/HANDOFF.md\"]') !== null"));
  assert(await evalPage(`
    document.querySelectorAll('nav button')[2].click();
    const search = document.querySelector('input[type=search]');
    search.value = 'no-possible-record';
    search.dispatchEvent(new Event('input'));
    document.querySelector('main').textContent.includes('No implementation records match')
  `));
  await call("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert(await evalPage("document.documentElement.scrollWidth === window.innerWidth"), "mobile view fits viewport");
  socket.close();
  console.log("Offline dashboard passed 8-view, graph, search, download and mobile layout checks.");
} finally {
  processHandle.kill();
}
