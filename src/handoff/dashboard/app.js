"use strict";
(() => {
  const byId = (id) => document.getElementById(id);
  const main = byId("main");
  const host = typeof acquireVsCodeApi === "function" ? acquireVsCodeApi() : null;
  const send = (type, detail = {}) => host?.postMessage({ type, ...detail });
  const views = [
    ["overview", "Overview", "◫"], ["architecture", "Architecture", "⌘"],
    ["features", "Implementation", "▤"], ["debt", "Technical debt", "◈"],
    ["dependencies", "Dependencies", "⇄"], ["quality", "Testing & quality", "✓"],
    ["risks", "Risks & next steps", "↑"], ["handover", "Handover", "↗"],
  ];
  const statuses = {
    completed_verified: "Completed and verified", implemented_unverified: "Implemented, unverified",
    partially_implemented: "Partial implementation", not_started: "Not started",
    blocked: "Blocked", unknown: "Unknown",
  };
  const artifacts = [
    "reports/HANDOFF.md", "reports/HANDOFF_AGENT.md", "reports/PROJECT_SUMMARY.md",
    "reports/ARCHITECTURE.md", "reports/IMPLEMENTATION_STATUS.md", "reports/TECHNICAL_DEBT.md",
    "reports/NEXT_STEPS.md", "visualizations/architecture.svg", "visualizations/dependency-graph.svg",
    "visualizations/feature-status.svg", "visualizations/technical-debt.svg", "visualizations/test-summary.svg",
    "data/project-analysis.json", "handover.zip",
  ];
  let model = byId("analysis-data") ? JSON.parse(byId("analysis-data").textContent) : null;
  let view = "overview";
  let busy = false;
  let evidence = new Map();
  const node = (tag, value, className) => {
    const element = document.createElement(tag);
    if (value !== undefined) element.textContent = value;
    if (className) element.className = className;
    return element;
  };
  const append = (target, ...children) => { target.append(...children); return target; };
  const list = (...rows) => append(node("div", undefined, "list"), ...rows);
  const empty = (value) => node("div", value, "empty");
  const number = (value) => new Intl.NumberFormat().format(value);
  const button = (label, run, style = "action") => {
    const el = node("button", label, style);
    el.type = "button";
    el.addEventListener("click", run);
    return el;
  };
  const navTo = (next, focus = true) => {
    if (!views.some(([id]) => id === next)) return;
    view = next;
    render();
    if (focus) main.focus();
  };
  const encoded = (path) => path.split("/").map(encodeURIComponent).join("/");
  const source = (path, line) => {
    const label = path + (line ? ":" + line : "");
    if (host) return button(label, () => send("source", { path, line }), "action source");
    const link = node("a", label, "source");
    const depth = Math.max(1, (model?.snapshot.output_dir || "").split("/").length - 1);
    link.href = "../".repeat(depth) + encoded(path) + (line ? "#L" + line : "");
    return link;
  };
  const badge = (label, warning = false) => node("span", label, "badge" + (warning ? " warn" : ""));
  const panel = (label, content, action) => {
    const header = append(node("div", undefined, "panel-head"), node("h2", label));
    if (action) header.append(action);
    return append(node("section", undefined, "panel"), header, content);
  };
  const header = (title, description, eyebrow = "Project analysis") => {
    const content = append(node("div"), node("div", eyebrow, "eyebrow"), node("h1", title), node("p", description));
    main.append(append(node("div", undefined, "heading"), content));
  };
  const rows = (items, make, message, limit = 200) =>
    items.length ? list(...items.slice(0, limit).map(make),
      ...(items.length > limit ? [empty("Showing " + limit + " of " + number(items.length) + " records. Refine the search.")] : []))
      : empty(message);
  const bars = (values, message) => {
    if (!values.length) return empty(message);
    const max = Math.max(1, ...values.map(([, value]) => value));
    return append(node("div", undefined, "panel-body bars"), ...values.map(([label, value]) => {
      const progress = node("progress");
      progress.value = value;
      progress.max = max;
      progress.title = label + ": " + value;
      progress.setAttribute("aria-label", label);
      return append(node("div", undefined, "bar"), node("span", label), progress, node("strong", number(value)));
    }));
  };
  const recordRow = (item) => {
    const row = node("article", undefined, "row");
    row.append(badge(item.priority ? item.priority + " priority" : item.confidence, item.priority === "high"));
    row.append(node("h3", item.summary));
    if (item.validation) row.append(node("p", item.validation));
    for (const id of item.evidence_ids.slice(0, 3)) {
      const ref = evidence.get(id);
      if (ref?.source_path) row.append(source(ref.source_path, ref.line_start));
    }
    return row;
  };
  const svgNode = (name, attributes) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) el.setAttribute(key, String(value));
    return el;
  };
  const graph = (expanded) => {
    if (!model.edges.length) return empty("No internal static imports could be resolved. Use the folder view to explore observed files.");
    const edges = model.edges.slice(0, expanded ? 45 : 14);
    const paths = [...new Set(edges.flatMap((edge) => [edge.source, edge.target]))].slice(0, expanded ? 30 : 12);
    const width = 720, height = Math.max(280, Math.ceil(paths.length / 3) * 55 + 40);
    const graph = svgNode("svg", { class: "graph", viewBox: "0 0 " + width + " " + height, "aria-label": "Static source imports" });
    const defs = svgNode("defs", {});
    const marker = svgNode("marker", { id: "arrow", markerWidth: 9, markerHeight: 9, refX: 7, refY: 4, orient: "auto" });
    marker.append(svgNode("path", { d: "M0 0 L8 4 L0 8 Z", fill: "#527b69" }));
    defs.append(marker);
    graph.append(defs);
    const layout = new Map(paths.map((path, i) => [path, [24 + (i % 3) * 234, 24 + Math.floor(i / 3) * 55]]));
    for (const edge of edges) {
      const a = layout.get(edge.source), b = layout.get(edge.target);
      if (!a || !b) continue;
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const inset = Math.min(98 / Math.max(1, Math.abs(dx)), 18 / Math.max(1, Math.abs(dy)));
      const line = svgNode("line", { x1: a[0] + 96 + dx * inset, y1: a[1] + 16 + dy * inset,
        x2: b[0] + 96 - dx * inset, y2: b[1] + 16 - dy * inset, "marker-end": "url(#arrow)" });
      const title = svgNode("title", {});
      title.textContent = edge.source + ":" + edge.line + " imports " + edge.target;
      line.append(title);
      graph.append(line);
    }
    const selection = node("div", "Select a module to inspect its imports.", "row fine");
    for (const [path, [x, y]] of layout) {
      const group = svgNode("g", { role: "button", tabindex: 0, "aria-label": path });
      group.append(svgNode("rect", { x, y, width: 192, height: 31 }));
      const title = svgNode("title", {});
      title.textContent = path;
      const label = svgNode("text", { x: x + 9, y: y + 20 });
      label.textContent = path.length > 27 ? "…" + path.slice(-26) : path;
      group.append(label, title);
      const select = () => {
        selection.replaceChildren(source(path));
        for (const edge of model.edges.filter((entry) => entry.source === path).slice(0, 25)) {
          const detail = append(node("div"), source(edge.source, edge.line), node("span", " imports "), source(edge.target));
          if (edge.configuration) detail.append(node("span", " via "), source(edge.configuration));
          selection.append(detail);
        }
      };
      group.addEventListener("click", select);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
      });
      graph.append(group);
    }
    let zoom = 1, x = 0, y = 0, drag;
    const update = () => graph.setAttribute("viewBox", [x, y, width / zoom, height / zoom].join(" "));
    const scale = (factor) => { zoom = Math.max(.55, Math.min(3, zoom * factor)); update(); };
    graph.addEventListener("pointerdown", (event) => {
      if (event.target.closest("[role=button]")) return;
      drag = [event.clientX, event.clientY, x, y];
      graph.setPointerCapture(event.pointerId);
    });
    graph.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const ratio = width / (Math.max(1, graph.clientWidth) * zoom);
      x = drag[2] - (event.clientX - drag[0]) * ratio;
      y = drag[3] - (event.clientY - drag[1]) * ratio;
      update();
    });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"]) graph.addEventListener(event, () => { drag = null; });
    return append(node("div"), graph,
      append(node("div", undefined, "graph-tools"), button("Zoom in", () => scale(1.2)),
        button("Zoom out", () => scale(1 / 1.2)),
        button("Reset view", () => { x = 0; y = 0; zoom = 1; update(); }),
        node("span", paths.length + " displayed modules · arrow points toward imported module", "fine")),
      selection);
  };
  function overview(s) {
    header(s.project, "Repository structure, implementation evidence, and what to verify next.",
      s.git.branch ? "Workspace / " + s.git.branch : "Workspace overview");
    const metrics = [
      ["Files inspected", model.counts.files], ["Evidence records", model.counts.evidence],
      ["Implementation records", Object.values(model.counts.status).reduce((a, b) => a + b, 0)],
      ["Discovered test files", s.files.filter((f) => f.kind === "test_discovery").length],
    ];
    main.append(append(node("div", undefined, "metrics"), ...metrics.map(([label, value]) =>
      append(node("div", undefined, "metric"), node("strong", number(value)), node("small", label)))));
    const status = Object.entries(statuses).map(([key, name]) => [name, model.counts.status[key] || 0]);
    const actions = s.findings.filter((item) => item.kind === "action").slice(0, 4);
    main.append(append(node("div", undefined, "grid"),
      append(node("div", undefined, "stack"),
        panel("Architecture map", graph(false), button("Explore map ↗", () => navTo("architecture"))),
        panel("Technology stack", bars(Object.entries(model.languages), "No supported languages were identified."))),
      append(node("div", undefined, "stack"),
        panel("Implementation status", bars(status, "No implementation findings.")),
        panel("Next actions", rows(actions, recordRow, "No evidence-backed recommendations."),
          button("View risks ↗", () => navTo("risks"))))));
    const entry = s.evidence.filter((e) => e.metadata.role === "entry");
    const summary = append(node("div", undefined, "panel-body"),
      node("p", "Project purpose is unverified. The scan observed " + number(model.counts.files) +
        " files across " + Object.keys(model.languages).length + " detected languages. Git metadata is " +
        s.git.state + "; " + Object.keys(s.git.changes).length + " visible working-tree changes were recorded."),
      node("p", "Scanned " + number(model.counts.bytes) + " bytes · " + new Date(s.observed_at).toLocaleString(), "fine"));
    for (const item of entry.slice(0, 10)) summary.append(source(item.source_path, item.line_start));
    main.append(panel("Repository summary", summary));
  }
  function filterList(items, label, make, initialProperty = "summary") {
    const input = node("input");
    input.type = "search";
    input.placeholder = "Search " + label.toLowerCase();
    input.setAttribute("aria-label", input.placeholder);
    const result = node("div");
    function apply() {
      const term = input.value.toLowerCase().trim();
      result.replaceChildren(rows(items.filter((item) => String(item[initialProperty]).toLowerCase().includes(term)),
        make, "No records match this view."));
    }
    input.addEventListener("input", apply);
    apply();
    main.append(append(node("div", undefined, "controls"), input), panel(label, result));
  }
  function folderTree(files) {
    const items = new Map();
    for (const entry of files.slice(0, 350)) {
      const parts = entry.path.split("/");
      let folder = items;
      for (const part of parts.slice(0, -1)) {
        if (!folder.has(part)) folder.set(part, new Map());
        folder = folder.get(part);
      }
      folder.set(parts.at(-1), entry.path);
    }
    const branch = (entries) => append(node("ul", undefined, "tree"), ...Array.from(entries, ([name, entry]) => {
      if (typeof entry === "string") return append(node("li"), source(entry));
      const detail = append(node("details"), node("summary", name), branch(entry));
      return append(node("li"), detail);
    }));
    return files.length ? append(node("div", undefined, "panel-body"), branch(items),
      ...(files.length > 350 ? [node("p", "Showing the first 350 files. Use file search for the full inventory.", "fine")] : []))
      : empty("No files were inventoried.");
  }
  function features(s) {
    header("Implementation tracker", "Review scoped observations and their verification requirements.");
    const input = node("input"); input.type = "search"; input.placeholder = "Search findings or source paths";
    input.setAttribute("aria-label", input.placeholder);
    const select = node("select"); select.setAttribute("aria-label", "Filter by status");
    select.append(node("option", "All statuses"));
    for (const [value, label] of Object.entries(statuses)) { const option = node("option", label); option.value = value; select.append(option); }
    const sort = node("select"); sort.setAttribute("aria-label", "Sort implementation findings");
    sort.append(node("option", "Evidence order"), node("option", "Status"), node("option", "Source"));
    const result = node("div");
    const update = () => {
      const relevant = s.findings.filter((item) => {
        const paths = item.evidence_ids.map((id) => evidence.get(id)?.source_path || "").join(" ");
        return item.status && (!select.selectedIndex || select.value === item.status) &&
          (item.summary + " " + paths).toLowerCase().includes(input.value.toLowerCase().trim());
      });
      if (sort.selectedIndex) relevant.sort((a, b) =>
        (sort.selectedIndex === 1 ? a.status : evidence.get(a.evidence_ids[0])?.source_path || "")
          .localeCompare(sort.selectedIndex === 1 ? b.status : evidence.get(b.evidence_ids[0])?.source_path || ""));
      const table = node("table");
      table.append(append(node("thead"), append(node("tr"), ...["Observation", "Status", "Evidence", "Source", "Verification"].map((v) => node("th", v)))));
      const body = node("tbody");
      for (const item of relevant.slice(0, 250)) {
        const refs = item.evidence_ids.map((id) => evidence.get(id)).filter(Boolean);
        const details = append(node("details"), node("summary", refs.length + " records"));
        for (const ref of refs) details.append(node("p", ref.description));
        body.append(append(node("tr"), node("td", item.summary),
          append(node("td"), badge(statuses[item.status], ["blocked", "partially_implemented"].includes(item.status))),
          append(node("td"), details),
          append(node("td"), ...refs.filter((r) => r.source_path).map((r) => source(r.source_path, r.line_start))),
          node("td", item.validation || item.confidence + " observation; behavior not established")));
      }
      table.append(body);
      result.replaceChildren(relevant.length ? append(node("div", undefined, "table-scroll"), table) : empty("No implementation records match."));
      if (relevant.length > 250) result.append(empty("Showing 250 of " + number(relevant.length) + " records. Refine the search."));
    };
    input.addEventListener("input", update); select.addEventListener("change", update); sort.addEventListener("change", update);
    update();
    main.append(append(node("div", undefined, "controls"), input, select, sort), panel("Implementation evidence", result));
  }
  function render() {
    evidence = new Map(model?.snapshot.evidence.map((item) => [item.id, item]) || []);
    byId("navigation").replaceChildren(...views.map(([id, label, icon]) => {
      const control = button("", () => navTo(id), "");
      const symbol = node("span", icon, "symbol"); symbol.setAttribute("aria-hidden", "true");
      control.append(symbol, node("span", label));
      if (view === id) control.setAttribute("aria-current", "page");
      return control;
    }));
    byId("breadcrumb").replaceChildren(node("strong", model?.snapshot.project || "Workspace"), node("span", "/"),
      document.createTextNode(views.find(([id]) => id === view)[1]));
    const actions = byId("actions");
    actions.replaceChildren();
    if (host) {
      const analyze = button(model ? "Refresh analysis" : "Analyze repository", () => send("analyze"), "action primary");
      analyze.disabled = busy;
      actions.append(analyze);
      if (!busy && model) actions.append(button("Export package", () => send("export")));
    } else {
      const download = node("a", "Download package", "action primary");
      download.href = "handover.zip"; download.download = "";
      actions.append(download);
    }
    main.replaceChildren();
    main.setAttribute("aria-busy", String(busy));
    if (!model) {
      header("Get oriented in this repository", "Analyze the current workspace to see its architecture, implementation evidence, and next actions.", "HandOff");
      main.append(panel("Workspace analysis", empty(busy ? "Inspecting repository files and Git metadata…" : "No analysis is loaded.")));
      return;
    }
    const s = model.snapshot;
    if (view === "overview") overview(s);
    else if (view === "architecture") {
      header("Architecture", "Explore resolved static import relationships and the scanned file tree.");
      main.append(panel("Static import map", graph(true)));
      main.append(panel("Folder tree", folderTree(s.files)));
      filterList(s.files, "Scanned files", (item) => append(node("div", undefined, "row"), source(item.path)), "path");
    } else if (view === "features") features(s);
    else if (view === "debt") {
      header("Technical debt", "Review markers, placeholder bodies, and parser limitations in context.");
      const items = s.evidence.filter((item) => item.source_type === "todo_marker" || ["stub", "parse-error"].includes(item.metadata.role));
      const groups = new Map();
      for (const item of items) groups.set(item.description, (groups.get(item.description) || 0) + 1);
      main.append(panel("Debt distribution", bars([...groups], "No supported debt signals observed.")));
      filterList(items, "Debt evidence", (item) => append(node("article", undefined, "row"),
        badge(item.metadata.role === "stub" ? "Needs interpretation" : "Observed"),
        node("h3", item.description), source(item.source_path, item.line_start)), "source_path");
    } else if (view === "dependencies") {
      header("Dependencies", "Package declarations from supported manifests and statically resolved internal imports.");
      const scopes = new Map();
      for (const item of model.packages) scopes.set(item.scope, (scopes.get(item.scope) || 0) + 1);
      main.append(panel("Package declarations by scope", bars([...scopes], "No package declarations found in supported manifests.")), panel("Internal dependencies", graph(true)));
      filterList(model.packages, "Declared packages", (item) => append(node("div", undefined, "row"),
        badge(item.scope), node("h3", item.name + (item.version ? " " + item.version : "")), source(item.source)), "name");
    } else if (view === "quality") {
      header("Testing & quality", "Discovered tests and saved artifacts provide different kinds of evidence.");
      const results = s.evidence.filter((item) => item.source_type === "test_result");
      const counts = ["passed", "failed", "skipped", "errors"].map((state) =>
        [state, results.reduce((count, item) => count + Number(item.metadata[state] || 0), 0)]);
      main.append(panel("External test outcomes", bars(results.length ? counts : [], "No external test result was supplied. HandOff did not execute tests.")));
      filterList(s.evidence.filter((e) => e.source_type === "test_discovery" ||
        e.source_type === "test_result" || (e.source_type === "configuration" && /workflows|ruff|mypy/.test(e.source_path || ""))),
        "Test and quality evidence", (item) => append(node("div", undefined, "row"),
          node("h3", item.description), source(item.source_path, item.line_start)), "source_path");
    } else if (view === "risks") {
      header("Risks & next steps", "Use evidence and scoped validation criteria to plan the next handover.");
      const actions = s.findings.filter((f) => f.kind === "action");
      const priorities = ["high", "medium", "low"].map((label) =>
        [label + " priority", actions.filter((item) => item.priority === label).length]);
      main.append(panel("Remaining work by priority", bars(actions.length ? priorities : [], "No action findings.")));
      main.append(panel("Recommended actions", rows(actions, recordRow, "No action findings.")));
      main.append(panel("Risks", rows(s.findings.filter((f) => f.kind === "risk"), recordRow, "No risk findings in this scan.")));
    } else {
      header("Developer handover", "Review the repository context and export the reports, diagrams, and structured evidence.");
      const setup = s.evidence.filter((e) => ["doc-setup", "doc-environment", "doc-architecture", "doc-tests", "decision", "entry"].includes(e.metadata.role));
      main.append(panel("Setup and architecture references", rows(setup, (item) =>
        append(node("div", undefined, "row"), node("h3", item.description), source(item.source_path, item.line_start)),
      "No setup or architecture instructions were identified. Consult the project documentation.")));
      const downloads = node("div", undefined, "panel-body button-row");
      if (host) {
        downloads.append(button("Generate reports", () => send("generate"), "action primary"),
          button("Export handover ZIP", () => send("export")), button("Validate package", () => send("validate")),
          button("Open generated artifacts", () => send("artifacts")));
        if (busy) for (const control of downloads.querySelectorAll("button")) control.disabled = true;
      }
      else for (const path of artifacts) {
        const link = node("a", path.split("/").at(-1), "action");
        link.href = encoded(path); link.download = ""; downloads.append(link);
      }
      main.append(panel("Handover artifacts", downloads));
    }
    if (model.analysis_notes.length) main.append(panel("Analysis limits", rows(model.analysis_notes, (item) => node("p", item, "row"), "")));
  }
  window.addEventListener("message", ({ data }) => {
    if (!host || data?.type !== "state") return;
    busy = Boolean(data.busy);
    if (data.model) model = data.model;
    if (data.view) view = data.view;
    byId("announcement").textContent = data.message || "";
    render();
  });
  render();
  send("ready");
})();
