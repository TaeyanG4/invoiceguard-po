// InvoiceGuard-PO read-only admin dashboard (Korean UI).
// Every value from the API is inserted as text (textContent / text nodes) — never parsed as markup.
// The page only talks to its own origin (same-origin JSON/PNG endpoints); no CDN, no external fetch.
// Charts are plain elements positioned through the CSSOM (allowed by the CSP); no chart library.
"use strict";
(function () {
  const main = document.getElementById("main");
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("navtoggle");
  const backdrop = document.getElementById("backdrop");
  const crumbs = document.getElementById("crumbs");
  const tip = document.getElementById("tip");
  const PAGE_SIZE = 50;
  const PUBLIC_ID_RE = /^synth_\d{4}_[0-9a-f]{8}\.png$/;
  const TRADE_ID_RE = /^tr_[0-9a-f]{12}$/;
  const QUALITIES = ["clean", "faded", "bad_scan"];
  let LABELS = { status_ko: {}, status_class: {}, visibility_ko: {} };
  let lastPublicList = "#/public";
  let lastTradeList = "#/trade";
  let routeToken = 0;

  // ------------------------------------------------------------------ DOM helpers (text only)
  function safeHref(v) {
    const s = String(v);
    return s.startsWith("#/") || s.startsWith("/api/") ? s : "#/overview";
  }
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined || v === false) continue;
        if (k === "class") el.className = v;
        else if (k === "href") el.setAttribute("href", safeHref(v));
        else if (k === "src") el.setAttribute("src", safeHref(v));
        else if (k === "width") el.style.width = v; // CSSOM, allowed by the CSP
        else if (k === "css") for (const [p, val] of Object.entries(v)) el.style[p] = val;
        else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, String(v));
      }
    }
    add(el, children);
    return el;
  }
  function add(el, children) {
    for (const c of children.flat(Infinity)) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : String(c));
    }
    return el;
  }
  const txt = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));
  const mono = (v) => h("span", { class: "mono" }, txt(v));
  const short = (v, n) => (v ? String(v).slice(0, n || 12) + "…" : "—");
  const fmt = (v, d) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d === undefined ? 3 : d));
  const signed = (v, d) => (v === null || v === undefined ? "—" : (Number(v) >= 0 ? "+" : "−") + Math.abs(Number(v)).toFixed(d === undefined ? 3 : d));
  const clean = (v) => (v === null || v === undefined ? "" : String(v).replace(/\*\*/g, "").replace(/`/g, ""));
  // a SESSION_HANDOFF status line without its "해제: ..." (how to unblock) clause; the user decision is shown beside it
  const recordedStatus = (v) => clean(v).split(" 해제:")[0].trim();
  const pct = (v) => (Math.max(0, Math.min(1, Number(v) || 0)) * 100).toFixed(2) + "%";

  // statuses in the task board may carry a suffix: "passed_with_evidence (local) · RunPod blocked", "partial: ..."
  function statusKey(s) {
    return String(s || "").trim().split(/[\s(]/)[0].replace(/:$/, "") || "unknown";
  }
  function toneOf(key) {
    return LABELS.status_class[key] || (key === "partial" ? "warn" : "idle");
  }
  function pill(status, label) {
    const key = statusKey(status);
    return h("span", { class: "pill " + toneOf(key) }, label || LABELS.status_ko[key] || txt(key));
  }
  const pillCls = (cls, label) => h("span", { class: "pill " + cls }, label);
  const yesNo = (b, yes, no) => (b === true ? pillCls("ok", yes || "예") : b === false ? pillCls("bad", no || "아니오") : pillCls("warn", "미확인"));
  const FLAG_RE = /blocked|not_run|failed/i; // a passed step whose note still names something unfinished
  function statusExtra(status) {
    const s = String(status || "").trim();
    const key = statusKey(s);
    return s.slice(s.indexOf(key) + key.length).replace(/^[:\s·]+/, "").trim();
  }
  function card(title, ...children) {
    return h("section", { class: "card" }, title ? h("div", { class: "cardhead" }, h("h2", null, title)) : null, ...children);
  }
  function cardH(title, hint, ...children) {
    return h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, title), hint ? h("span", { class: "hint" }, hint) : null), ...children);
  }
  function kv(pairs) {
    return h("table", { class: "kv" }, h("tbody", null, pairs.filter(Boolean).map(([k, v]) => h("tr", null, h("th", null, k), h("td", null, v instanceof Node ? v : txt(v))))));
  }
  function table(headers, rows, cls, wrapCls) {
    return h("div", { class: "tablewrap " + (wrapCls || "") }, h("table", { class: "grid " + (cls || "") },
      h("thead", null, h("tr", null, headers.map((x) => (Array.isArray(x) ? h("th", { class: x[1] }, x[0]) : h("th", null, x))))),
      h("tbody", null, rows)));
  }
  function bars(counts, labeler) {
    const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
    const total = Math.max(1, entries.reduce((s, [, v]) => s + v, 0));
    return h("div", null, entries.map(([k, v]) => h("div", { class: "bar" },
      h("span", { class: "bl", title: k }, labeler ? labeler(k) : k),
      h("span", { class: "bt" }, h("i", { width: (100 * v / total).toFixed(1) + "%" })),
      h("span", { class: "bv" }, String(v)))));
  }
  const banner = (text, kind) => h("p", { class: "banner " + (kind || "") }, text);
  function pageHead(title, meta, source) {
    return h("div", { class: "pagehead" },
      h("div", null, h("h1", null, title), meta ? h("div", { class: "meta" }, meta) : null),
      source ? h("span", { class: "src", title: source }, source) : null);
  }
  function kpi(label, value, unit, sub, tone, meter) {
    return h("div", { class: "kpi" },
      h("div", { class: "kl" }, tone ? h("span", { class: "dot " + tone }) : null, label),
      h("div", { class: "kn" }, value, unit ? h("small", null, unit) : null),
      sub ? h("div", { class: "ks" }, sub) : null,
      meter !== undefined && meter !== null ? h("div", { class: "meter" }, h("i", { class: tone === "ok" ? "ok" : null, width: pct(meter) })) : null);
  }
  function details(title, ...children) {
    return h("details", { class: "card fold" }, h("summary", null, h("h2", null, title)), h("div", { class: "foldbody" }, ...children));
  }

  // ------------------------------------------------------------------ tooltip (hover + keyboard focus)
  function hideTip() { tip.hidden = true; }
  function placeTip(x, y) {
    const r = tip.getBoundingClientRect();
    let left = x + 14, top = y + 16;
    if (left + r.width > window.innerWidth - 8) left = x - r.width - 14;
    if (top + r.height > window.innerHeight - 8) top = y - r.height - 14;
    tip.style.left = Math.max(8, left) + "px";
    tip.style.top = Math.max(8, top) + "px";
  }
  function attachTip(el, build) {
    const show = (x, y) => { tip.replaceChildren(...build()); tip.hidden = false; placeTip(x, y); };
    el.addEventListener("pointerenter", (e) => show(e.clientX, e.clientY));
    el.addEventListener("pointermove", (e) => placeTip(e.clientX, e.clientY));
    el.addEventListener("pointerleave", hideTip);
    el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); show(r.left + Math.min(r.width, 240) / 2, r.bottom); });
    el.addEventListener("blur", hideTip);
  }
  const tipLine = (label, value) => h("div", null, h("span", { class: "tl" }, label + " "), value);

  // ------------------------------------------------------------------ API
  async function api(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" }, cache: "no-store", credentials: "same-origin" });
    let body = null;
    try { body = await res.json(); } catch (e) { body = null; }
    if (!res.ok) {
      const err = new Error((body && body.error) || "http_" + res.status);
      err.detail = body && body.detail;
      throw err;
    }
    return body;
  }
  async function status() {
    const s = await api("/api/status");
    if (s.labels) LABELS = s.labels;
    return s;
  }
  function errorBox(e) {
    return card("불러오지 못했습니다", h("p", { class: "err" }, mono(e.message), e.detail ? [" (", mono(e.detail), ")"] : null),
      h("p", { class: "sub" }, "서버가 실행 중인지, 주소의 ID·필터가 올바른지 확인하세요."));
  }
  function statusErrors(s) {
    const keys = Object.keys(s.errors || {});
    return keys.length ? banner("일부 기록을 읽지 못했습니다(동시 편집 중일 수 있음): " + keys.map((k) => k + " — " + s.errors[k]).join(" / "), "bad") : null;
  }

  // ------------------------------------------------------------------ evaluation helpers
  const ARMS = {
    b0: { name: "B0", desc: "OCR 규칙 기반 (Tesseract)", cls: "s-b0" },
    m0: { name: "M0", desc: "Qwen3-VL-2B 기본 · NF4", cls: "s-m0" },
    m1: { name: "M1", desc: "M0 + QLoRA 어댑터", cls: "s-m1" },
  };
  const ARM_ORDER = ["b0", "m0", "m1"];
  const IID_DESC = "IID 풀 · freelancer 외 5개 템플릿 (event_ticket은 학습에 없음)";
  const SET_INFO = {
    "trade:test": ["자체 test", "학습에 없던 레이아웃 T05·T06"],
    "public:iid_final|clean": ["공개 IID · clean", IID_DESC],
    "public:iid_final|faded": ["공개 IID · faded", IID_DESC],
    "public:iid_final|bad_scan": ["공개 IID · bad_scan", IID_DESC],
    "public:ood_final|clean": ["공개 OOD · clean", "freelancer · 학습 제외"],
    "public:ood_final|faded": ["공개 OOD · faded", "freelancer · 학습 제외"],
    "public:ood_final|bad_scan": ["공개 OOD · bad_scan", "freelancer · 학습 제외"],
    "trade:dev": ["자체 dev", ""],
    "public:dev|clean": ["공개 dev · clean", ""],
    "public:dev_stress|faded": ["공개 dev · faded", "열화 품질"],
    "public:dev_stress|bad_scan": ["공개 dev · bad_scan", "열화 품질"],
    "stress:blur_jpeg": ["stress · blur+JPEG", "dev 전용 합성 열화"],
    "stress:fade_noise": ["stress · fade+noise", "dev 전용 합성 열화"],
    "stress:skew_lowres": ["stress · skew+저해상도", "dev 전용 합성 열화"],
  };
  const SET_ORDER = Object.keys(SET_INFO);
  const setInfo = (k) => SET_INFO[k] || [k, ""];
  function orderSets(keys) {
    const rank = (k) => (SET_ORDER.indexOf(k) < 0 ? 999 : SET_ORDER.indexOf(k));
    return keys.slice().sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  }
  const runKey = (id) => String(id || "").split("_")[0].toLowerCase();
  const runName = (id) => (ARMS[runKey(id)] ? ARMS[runKey(id)].name : runKey(id).toUpperCase());
  function mainRuns(evals, stage) {
    const out = {};
    const runs = evals.filter((e) => e.stage === stage).sort((a, b) => String(a.run_id).localeCompare(String(b.run_id)));
    for (const e of runs) if (ARMS[runKey(e.run_id)]) out[runKey(e.run_id)] = e; // latest version per arm
    return out;
  }
  function armLegend(extra) {
    return h("div", { class: "legend" },
      ARM_ORDER.map((k) => h("span", { class: "key" }, h("span", { class: "sw " + ARMS[k].cls }), h("b", null, ARMS[k].name), " " + ARMS[k].desc)),
      h("span", { class: "key" }, h("span", { class: "cikey" }), "95% CI (base/family bootstrap)"),
      extra === false ? null : h("span", { class: "key" }, h("span", { class: "lenkey" }), "lenient (strict JSON 실패 시 코드펜스 제거 후 채점)"));
  }
  function armChart(byArm, sets) {
    const arms = ARM_ORDER.filter((k) => byArm[k]);
    const grid = h("div", { class: "armchart" },
      h("div", { class: "axis", "aria-hidden": "true" }, [0, 0.25, 0.5, 0.75, 1].map((t) => h("span", { css: { left: pct(t) } }, t === 0 ? "0" : t.toFixed(2)))));
    for (const k of sets) {
      const [label, desc] = setInfo(k);
      const first = arms.map((a) => byArm[a].headline[k]).find(Boolean);
      grid.append(h("div", { class: "setlabel" }, label, h("small", null, [desc, first ? "n " + first.n : null].filter(Boolean).join(" · "))));
      const rows = h("div", { class: "setbars" });
      for (const a of arms) {
        const v = byArm[a].headline[k];
        if (!v) { rows.append(h("div", { class: "armbar" }, h("span", { class: "val", css: { left: "0%" } }, ARMS[a].name + " 미측정"))); continue; }
        const acc = Number(v.fields_acc) || 0;
        const ci = Array.isArray(v.ci95) ? v.ci95.map(Number) : null;
        const lenient = Number(v.json_valid) < 1 && v.lenient_fields_acc !== null && v.lenient_fields_acc !== undefined ? Number(v.lenient_fields_acc) : null;
        const end = Math.max(acc, ci ? ci[1] : 0, lenient === null ? 0 : lenient);
        const summary = ARMS[a].name + " · " + label + " · strict " + fmt(acc) + (ci ? " [" + fmt(ci[0], 2) + "–" + fmt(ci[1], 2) + "]" : "");
        const bar = h("div", { class: "armbar", tabindex: "0", role: "img", "aria-label": summary },
          h("i", { class: "fill " + ARMS[a].cls + (acc === 0 ? " zero" : ""), css: { width: pct(acc) } }),
          ci ? h("b", { class: "ci", css: { left: pct(ci[0]), width: pct(Math.max(0, ci[1] - ci[0])) } }) : null,
          lenient !== null ? h("em", { class: "len", css: { left: pct(lenient) } }) : null,
          h("span", { class: "val", css: { left: pct(end) } }, fmt(acc), lenient !== null ? h("small", null, " · ◇ " + fmt(lenient)) : null));
        attachTip(bar, () => [h("b", null, ARMS[a].name + " · " + label),
          tipLine("strict 필드 정확도", fmt(acc) + (ci ? "  [" + fmt(ci[0], 2) + "–" + fmt(ci[1], 2) + "]" : "")),
          tipLine("문서 exact", fmt(v.doc_exact, 2)), tipLine("strict JSON 유효율", fmt(v.json_valid, 2)),
          lenient !== null ? tipLine("lenient 정확도", fmt(lenient)) : null,
          tipLine("문서 수", String(v.n)), h("div", { class: "tl" }, byArm[a].run_id)]);
        rows.append(bar);
      }
      grid.append(rows);
    }
    return grid;
  }
  function forestPlot(c) {
    const pos = (d) => (((Math.max(-1, Math.min(1, Number(d))) + 1) / 2) * 100).toFixed(2) + "%";
    const A = runName(c.a), B = runName(c.b);
    const grid = h("div", { class: "forest" },
      h("div", { class: "faxis", "aria-hidden": "true" }, [-1, -0.5, 0, 0.5, 1].map((t) => h("span", { css: { left: pos(t) } }, t > 0 ? "+" + t : t < 0 ? "−" + Math.abs(t) : "0"))));
    for (const k of orderSets(Object.keys(c.sets || {}))) {
      const v = c.sets[k];
      const d = Number(v.field_acc_diff);
      const ci = Array.isArray(v.field_acc_diff_ci95) ? v.field_acc_diff_ci95.map(Number) : null;
      const sig = ci ? ci[0] > 0 || ci[1] < 0 : null;
      const [label, desc] = setInfo(k);
      grid.append(h("div", { class: "fl" }, label, h("small", null, [desc, "n " + v.n_docs].filter(Boolean).join(" · "))));
      const track = h("div", { class: "ft", tabindex: "0", role: "img", "aria-label": A + " − " + B + " " + label + " " + signed(d) },
        h("i", { class: "zero" }),
        ci ? h("b", { class: "ci", css: { left: pos(ci[0]), width: (Math.max(0, ci[1] - ci[0]) * 50).toFixed(2) + "%" } }) : null,
        h("em", { class: "pt" + (sig ? "" : " ns"), css: { left: pos(d) } }));
      attachTip(track, () => [h("b", null, A + " − " + B + " · " + label), tipLine("필드 정확도 차이", signed(d) + (ci ? "  [" + signed(ci[0]) + ", " + signed(ci[1]) + "]" : "")),
        tipLine("문서 exact 차이", signed(v.doc_exact_diff, 2)), tipLine("같은 문서 / 클러스터", v.n_docs + " / " + v.n_clusters)]);
      grid.append(track,
        h("div", { class: "fv" }, signed(d) + (ci ? "  [" + signed(ci[0]) + ", " + signed(ci[1]) + "]" : "")),
        h("div", { class: "fs" }, sig === null ? pillCls("idle", "CI 없음") : sig ? pillCls(d > 0 ? "ok" : "warn", (d > 0 ? A : B) + " 우세") : pillCls("idle", "유의하지 않음")));
    }
    return grid;
  }
  function forestCard(comps, title) {
    if (!comps.length) return null;
    const body = h("div");
    const buttons = comps.map((c, i) => h("button", { type: "button", "aria-pressed": i === 0 ? "true" : "false", onclick: () => show(i) }, runName(c.a) + " − " + runName(c.b)));
    function show(i) {
      buttons.forEach((b, j) => b.setAttribute("aria-pressed", j === i ? "true" : "false"));
      body.replaceChildren(forestPlot(comps[i]));
    }
    show(0);
    return h("section", { class: "card" },
      h("div", { class: "cardhead" }, h("h2", null, title), h("div", { class: "segtabs", role: "group", "aria-label": "비교 선택" }, buttons)),
      h("div", { class: "legend" }, h("span", { class: "key" }, h("span", { class: "dot run" }), "CI가 0을 포함하지 않음 (유의)"),
        h("span", { class: "key" }, h("span", { class: "dot idle" }), "CI가 0을 포함 (유의하지 않음)"), h("span", { class: "key" }, "같은 문서 쌍, cluster bootstrap 95% CI")),
      body);
  }
  function stageComps(comps, evals, stage) {
    const ids = new Set(evals.filter((e) => e.stage === stage).map((e) => e.run_id));
    const order = (c) => ({ "m1-m0": 0, "m1-b0": 1, "m0-b0": 2 }[runKey(c.a) + "-" + runKey(c.b)] ?? 9);
    return comps.filter((c) => ids.has(c.a) && ids.has(c.b)).sort((x, y) => order(x) - order(y));
  }
  function evalTable(runs) {
    const sets = orderSets(Array.from(new Set(runs.flatMap((e) => Object.keys(e.headline)))));
    return table(["set"].concat(runs.map((e) => [h("span", null, runName(e.run_id), h("div", { class: "sub mono" }, e.run_id)), ""])),
      sets.map((k) => {
        const vals = runs.map((e) => e.headline[k]);
        const best = Math.max(...vals.filter(Boolean).map((v) => Number(v.fields_acc)));
        return h("tr", null, h("td", null, setInfo(k)[0], h("div", { class: "sub mono" }, k)),
          vals.map((v) => h("td", { class: v && Number(v.fields_acc) === best ? "best" : null }, v
            ? [fmt(v.fields_acc), h("div", { class: "sub" }, "exact " + fmt(v.doc_exact, 2) + " · JSON " + fmt(v.json_valid, 2) + " · n " + v.n),
              v.ci95 ? h("div", { class: "sub" }, "CI " + v.ci95.join("–")) : null,
              Number(v.json_valid) < 1 && v.lenient_fields_acc != null ? h("div", { class: "sub" }, "lenient " + fmt(v.lenient_fields_acc)) : null]
            : pill("not_run"))));
      }), "small");
  }

  // ------------------------------------------------------------------ pages
  const FLOW = [
    ["데이터·분할", ["T01", "T02"], "공개 합성 + 자체 Invoice–PO, 누수 없는 분할"],
    ["QLoRA 학습", ["T03", "T04"], "Qwen3-VL-2B NF4 + LoRA, 로컬 GPU"],
    ["dev 분석·개선", ["T05"], "실패 분류, 개선 시도 1회"],
    ["검수 API", ["T06"], "CAS·승인 스냅샷·export"],
    ["GPU 서빙", ["T07"], "HF+PEFT 서버, 취소·대기열"],
    ["final 평가", ["T08"], "동결 후 1회, B0·M0·M1"],
    ["백업·정리", ["T09"], "해시 검증 백업"],
  ];
  async function pageOverview(view) {
    const s = await status();
    const tasks = s.tasks || [], gates = s.gates || [], ho = s.handoff || {};
    const byId = Object.fromEntries(tasks.map((t) => [t.id, t]));
    const done = tasks.filter((t) => statusKey(t.status) === "passed_with_evidence").length;
    const gPass = gates.filter((g) => statusKey(g.status) === "pass").length;
    const gPartial = gates.filter((g) => statusKey(g.status) === "partial").length;
    const junit = s.junit;
    const evals = s.evaluations || [];
    const finals = mainRuns(evals, "final");
    const den = Object.values(finals).map((e) => e.denominator_check).filter(Boolean);
    const finalSets = orderSets(Array.from(new Set(Object.values(finals).flatMap((e) => Object.keys(e.headline)))));
    const passed = junit ? junit.tests - junit.failures - junit.errors - junit.skipped : null;
    const flow = h("ol", { class: "flow" }, FLOW.map(([name, ids, sub]) => {
      const keys = ids.map((i) => statusKey((byId[i] || {}).status));
      const notes = ids.map((i) => statusExtra((byId[i] || {}).status)).filter(Boolean);
      const ok = keys.every((k) => k === "passed_with_evidence");
      return h("li", { class: ok ? "is-ok" : "is-warn", title: ids.join(", ") },
        h("div", { class: "fh" }, name), h("div", { class: "fs" }, sub),
        notes.length ? h("div", { class: "fs" }, notes.some((x) => FLAG_RE.test(x)) ? [h("span", { class: "dot warn" }), " "] : null, notes.join(" / ")) : null);
    }));
    const blockers = [
      s.handoff_decision ? ["사용자 결정", clean(s.handoff_decision)] : null,
      ho["vLLM 서빙"] ? ["vLLM 서빙", recordedStatus(ho["vLLM 서빙"])] : null,
      ho.RunPod ? ["RunPod", clean(ho.RunPod)] : null,
      ...gates.filter((g) => statusKey(g.status) !== "pass").map((g) => [g.id + " " + g.name,
        (statusKey(g.status) === "partial" ? "부분 통과" : LABELS.status_ko[statusKey(g.status)] || statusKey(g.status)) + (g.detail ? " — " + g.detail : "")]),
    ].filter(Boolean);
    const complete = den.length && den.every((d) => d.predicted === d.expected && !d.missing);
    const ld = s.local_data || {};
    add(view, [
      h("section", { class: "card hero" },
        h("div", { class: "eyebrow" }, "INVOICEGUARD-PO"),
        h("h1", null, "영어 인보이스 이미지 → VLM 추출 → 발주서 대사 → 사람 검수"),
        h("p", null, "합성 영어 인보이스에서 SKU·수량·단가를 VLM(Qwen3-VL-2B + QLoRA)으로 추출하고, 독립 발주서와 규칙 기반으로 대사한 뒤 사람이 승인한 버전만 내보냅니다. 학습 효과는 사람이 라벨을 단 실사진 영수증(CORD v2)으로 따로 검증합니다. 이 화면은 저장소의 기록(reports/, manifests/, configs/)만 읽어서 보여주며 수치를 추정하지 않습니다."),
        flow),
      statusErrors(s),
      h("div", { class: "kpis" },
        kpi("진행 단계", String(done), "/ " + tasks.length, "증거로 통과한 T00–T09", done === tasks.length ? "ok" : "warn", tasks.length ? done / tasks.length : 0),
        kpi("인수 게이트", String(gPass), "/ " + gates.length, gPartial ? "부분 통과 " + gPartial + "개 (아래 차단 항목)" : "G0–G7", gPartial ? "warn" : "ok", gates.length ? gPass / gates.length : 0),
        kpi("FINAL 평가", den.length ? String(Math.min(...den.map((d) => d.predicted))) : "—", den.length ? "/ " + den[0].expected + " 문서" : "",
          den.length ? "동결 후 1회 · " + Object.keys(finals).map((k) => ARMS[k].name).join("·") + " 같은 문서" + (complete ? " · 누락 0" : " · 누락 있음") : "final 기록 없음", complete ? "ok" : den.length ? "warn" : "idle"),
        kpi("CPU 테스트", passed === null ? "—" : String(passed), junit ? "/ " + junit.tests : "", junit ? "건너뜀 " + junit.skipped + " · 실패 " + (junit.failures + junit.errors) + " · " + junit.mtime : "junit 기록 없음", junit && !junit.failures && !junit.errors ? "ok" : "warn", junit ? passed / Math.max(1, junit.tests) : null),
        kpi("클라우드 지출", ho.active_paid_resources_from_this_project && /^none/.test(ho.active_paid_resources_from_this_project) ? "$0" : "미확인", "", clean(ho.active_paid_resources_from_this_project) || "SESSION_HANDOFF 기록 없음", "idle")),
      finalSets.length
        ? h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "FINAL 결과 — strict 필드 정확도"), h("a", { href: "#/model" }, "모델·평가에서 자세히 →")),
          armLegend(), armChart(finals, finalSets),
          h("p", { class: "note" }, "합성 데이터·작은 표본(세트당 20~40문서)이므로 사례 증거로 읽어야 합니다. 막대에 마우스를 올리면 문서 exact·JSON 유효율·CI가 보입니다."))
        : card("FINAL 결과", h("p", null, pill("not_run"), " final 채점 파일이 없습니다.")),
      cordOverviewCard(s.cord),
      h("div", { class: "cols" },
        cardH("차단·미실행 항목", "기록 그대로", blockers.length ? h("ul", { class: "timeline" }, blockers.map(([k, v]) => h("li", { class: "is-warn" }, h("div", { class: "tt" }, k), h("div", { class: "td" }, v)))) : h("p", { class: "sub" }, "기록된 차단 항목 없음")),
        cardH("현재 상태", "reports/SESSION_HANDOFF.md", kv([
          ["프로필", clean(ho.profile)], ["모델", clean(ho.model)], ["final", clean(ho.final)], ["백업", clean(ho.backup)],
          ["실행 중 프로세스", clean(ho.running_processes)], ["유료 리소스", clean(ho.active_paid_resources_from_this_project)], ["push", clean(ho.push)],
        ]))),
      cardH("로컬 데이터", "Git에 넣지 않는 원본·캐시", kv([
        ["공개 parquet", ld.public_parquet ? pillCls("ok", "있음") : pillCls("warn", "없음 — 이미지·정답 표시 불가")],
        ["자체 Invoice–PO 파일", ld.trade_files ? pillCls("ok", "있음") : pillCls("warn", "없음 — 이미지·정답·PO 표시 불가")],
        ["캐시된 공개 이미지", String(ld.public_cached_images || 0) + "장 (data/processed/public/cache/)"],
        ["공개 manifest", s.public_manifest ? h("span", null, mono(short(s.public_manifest.sha256, 16)), " · ", s.public_manifest.frozen ? "동결됨" : "미동결") : "없음"],
        ["자체 manifest", s.trade_manifest ? h("span", null, mono(short(s.trade_manifest.sha256, 16)), " · ", s.trade_manifest.frozen ? "동결됨" : "미동결") : "없음"],
      ])),
    ]);
  }

  async function pageProgress(view) {
    const s = await status();
    const tasks = s.tasks || [], gates = s.gates || [];
    add(view, [
      pageHead("진행 단계·게이트", "T00–T09 작업과 G0–G7 인수 게이트 · 증거 문구는 기록 원문", "reports/TASK_BOARD.md"),
      statusErrors(s),
      cardH("진행 단계 T00–T09", tasks.filter((t) => statusKey(t.status) === "passed_with_evidence").length + "/" + tasks.length + " 증거 통과",
        h("ol", { class: "steps" }, tasks.map((t) => {
          const key = statusKey(t.status), extra = statusExtra(t.status);
          return h("li", { class: "is-" + (key === "passed_with_evidence" ? (FLAG_RE.test(extra) ? "warn" : "ok") : toneOf(key)) },
            h("span", { class: "sid" }, t.id),
            h("div", null, h("div", null, h("span", { class: "sname" }, t.name), h("span", { class: "swhere" }, t.where)), h("div", { class: "sub" }, t.evidence)),
            h("div", { class: "sstat" }, pill(key), extra ? h("small", null, extra) : null));
        }))),
      cardH("인수 게이트 G0–G7", "docs/16_RUNTIME_RELEASE_GATES.md",
        h("div", { class: "gategrid" }, gates.map((g) => h("div", { class: "gate" },
          h("div", { class: "gh" }, h("span", { class: "gid" }, g.id), pill(g.status, statusKey(g.status) === "partial" ? "부분 통과" : null)),
          h("div", { class: "gn" }, g.name), g.detail ? h("div", { class: "sub" }, g.detail) : null)))),
    ]);
  }

  // ---- shared list (filters + table + pager)
  function listQuery(query, allowed) {
    const p = new URLSearchParams();
    for (const k of allowed) { const v = query.get(k); if (v) p.set(k, v); }
    const page = Math.max(1, parseInt(query.get("page") || "1", 10) || 1);
    p.set("offset", String((page - 1) * PAGE_SIZE));
    p.set("limit", String(PAGE_SIZE));
    return { params: p, page };
  }
  function filterBar(base, query, facets, defs, searchLabel, total) {
    const form = h("form", { class: "toolbar", role: "search", onsubmit: (e) => { e.preventDefault(); go(); } });
    const controls = {};
    function go() {
      const p = new URLSearchParams();
      for (const [k, el] of Object.entries(controls)) if (el.value) p.set(k, el.value);
      location.hash = base + (p.toString() ? "?" + p.toString() : "");
    }
    for (const [key, label, labeler] of defs) {
      const sel = h("select", { name: key, onchange: go }, h("option", { value: "" }, "전체"),
        (facets[key] || []).map((f) => h("option", { value: f.value }, (labeler ? labeler(f.value) : f.value === "none" ? "(없음)" : f.value) + " · " + f.count)));
      sel.value = query.get(key) || "";
      controls[key] = sel;
      form.append(h("label", null, label, sel));
    }
    const q = h("input", { type: "search", name: "q", placeholder: "ID 일부", maxlength: "40", autocomplete: "off" });
    q.value = query.get("q") || "";
    q.addEventListener("change", go);
    controls.q = q;
    form.append(h("label", null, searchLabel, q), h("a", { class: "btn", href: base }, "초기화"), h("span", { class: "count" }, total.toLocaleString() + "건"));
    return form;
  }
  function pager(base, query, res, page) {
    const pages = Math.max(1, Math.ceil(res.total / PAGE_SIZE));
    const link = (n) => { const p = new URLSearchParams(query); p.set("page", String(n)); return base + "?" + p.toString(); };
    const start = res.total ? res.offset + 1 : 0, end = Math.min(res.total, res.offset + res.limit);
    return h("div", { class: "pager" },
      h("a", { class: "btn", href: page <= 1 ? null : link(page - 1), "aria-disabled": page <= 1 ? "true" : "false" }, "← 이전"),
      h("span", null, start + "–" + end + " / " + res.total + "건 · " + page + "/" + pages + "쪽"),
      h("a", { class: "btn", href: page >= pages ? null : link(page + 1), "aria-disabled": page >= pages ? "true" : "false" }, "다음 →"));
  }
  const rowLink = (href, cells) => h("tr", { class: "rowlink", onclick: () => { location.hash = href; } }, cells);

  // ---- public data
  const PUBLIC_FILTERS = ["pool", "standard_role", "mini_role", "template", "quality", "eligible", "q"];
  async function pagePublic(view, segs, query) {
    if (segs.length) return pagePublicDoc(view, segs);
    lastPublicList = location.hash || "#/public";
    const { params, page } = listQuery(query, PUBLIC_FILTERS);
    const [s, res] = await Promise.all([status(), api("/api/public/rows?" + params.toString())]);
    const pm = s.public_manifest;
    add(view, [
      pageHead("공개 데이터", "InvoiceOCR-Synth · PUBLIC_CANONICAL · 이미지 1장 = (base, 품질)", pm ? "manifest " + short(pm.sha256, 12) : "manifests/public_canonical_v1"),
      banner("공개 합성 영어 데이터입니다. SKU·단위·원문 인쇄 형식 정답은 없습니다. 정답(gold)은 평가·학습 라벨이며 모델 입력이 아닙니다.", "info"),
      h("section", { class: "card" }, filterBar("#/public", query, res.facets, [
        ["pool", "pool"], ["standard_role", "standard 역할"], ["mini_role", "mini 역할"], ["template", "템플릿"],
        ["quality", "품질"], ["eligible", "학습 가능", (v) => (v === "true" ? "가능" : "불가")],
      ], "base_id 검색", res.total),
      table(["base_id", "품질", "템플릿", "pool", "standard", "mini", "학습", ["품목", "num"], ["채점/마스크", "num"]],
        res.page.map((r) => rowLink("#/public/" + encodeURIComponent(r.base_id) + "/" + r.quality, [
          h("td", null, h("a", { class: "mono", href: "#/public/" + encodeURIComponent(r.base_id) + "/" + r.quality }, r.base_id)),
          h("td", null, r.quality), h("td", { class: "mono" }, r.template), h("td", null, r.pool),
          h("td", null, txt(r.standard_role)), h("td", null, txt(r.mini_role)),
          h("td", null, r.train_eligible ? pillCls("ok", "가능") : h("span", null, pillCls("idle", "불가"), h("div", { class: "sub mono" }, txt(r.train_ineligible_reason)))),
          h("td", { class: "num" }, String(r.n_items)), h("td", { class: "num" }, r.n_scored_fields + " / " + r.n_masked_fields),
        ])), "small", "tall"),
      pager("#/public", query, res, page),
      pm ? h("p", { class: "note" }, "seed ", String(pm.seed), " · 행을 누르면 이미지·정답·필드 가시성 상세") : null),
    ]);
  }
  function visCell(value, vis, fieldStatus, isText) {
    const masked = vis && vis !== "visible_exact";
    return h("td", { class: masked ? "masked" : null },
      h("span", { class: "val " + (isText ? "raw" : "mono") }, txt(value)),
      masked ? h("div", null, h("span", { class: "vis " + (vis === "not_printed" || vis === "source_empty" ? "idle" : "warn") }, LABELS.visibility_ko[vis] || vis), h("code", { class: "vcode" }, vis)) : null,
      fieldStatus && fieldStatus !== "ok" ? h("div", { class: "sub" }, "라벨 상태: ", mono(fieldStatus)) : null);
  }
  function imageFigure(url, alt, available, placeholder) {
    const figure = h("div", { class: "figure" }, h("div", { class: "ph" }, placeholder));
    if (available) {
      const img = h("img", { src: url, alt, decoding: "async" });
      img.addEventListener("load", () => figure.replaceChildren(img));
      img.addEventListener("error", () => figure.replaceChildren(h("div", { class: "ph" }, "이미지를 불러오지 못했습니다 (로컬 원본 또는 해시 불일치 확인).")));
      img.addEventListener("click", () => figure.classList.toggle("zoom"));
    }
    return figure;
  }
  async function pagePublicDoc(view, segs) {
    const baseId = segs[0], quality = segs[1] || "clean";
    if (!PUBLIC_ID_RE.test(baseId) || !QUALITIES.includes(quality)) {
      add(view, [pageHead("공개 데이터"), card("잘못된 주소", h("p", null, "ID 또는 품질 값이 형식에 맞지 않습니다."), h("a", { href: lastPublicList }, "목록으로"))]);
      return;
    }
    await status();
    const d = await api("/api/public/doc/" + encodeURIComponent(baseId) + "?quality=" + quality);
    const m = d.meta;
    const imgUrl = "/api/public/image/" + encodeURIComponent(baseId) + "/" + quality;
    const current = d.qualities.find((q) => q.quality === quality) || {};
    const available = d.public_parquet_available || current.image_cached;
    const figure = imageFigure(imgUrl, baseId + " (" + quality + ") 문서 이미지", available,
      !available ? "로컬 parquet 없음 — 이미지 표시 불가" : current.image_cached ? "이미지 불러오는 중…" : "이미지 추출 중… 처음 한 번은 parquet에서 꺼내 캐시하므로 몇 초 걸릴 수 있습니다.");
    const g = d.gold;
    const FIELDS = [["description", "설명 (description)", true], ["quantity", "수량", false], ["unit_price", "단가", false], ["amount", "금액", false]];
    const goldTable = g.available
      ? table(["#"].concat(FIELDS.map((f) => f[1])), g.items.map((it) => h("tr", null, h("td", { class: "mono" }, String(it.row_index)),
        FIELDS.map(([f, , isText]) => visCell(it[f], it.visibility && it.visibility[f], it.field_status && it.field_status[f], isText)))), "small")
      : h("p", { class: "err" }, "정답을 표시할 수 없습니다: ", mono(g.reason));
    add(view, [
      h("a", { class: "back", href: lastPublicList }, "← 공개 데이터 목록"),
      pageHead(baseId, m.template + " · " + m.pool + " · " + quality),
      h("div", { class: "tabs" }, d.qualities.map((q) => h("a", { href: "#/public/" + encodeURIComponent(baseId) + "/" + q.quality, class: q.quality === quality ? "active" : null },
        q.quality + (q.standard_role ? " · std:" + q.standard_role : "") + (q.mini_role ? " · mini:" + q.mini_role : "")))),
      h("div", { class: "cols detail" },
        h("section", { class: "card sticky" }, h("div", { class: "cardhead" }, h("h2", null, "문서 이미지"), h("span", { class: "hint" }, "모델 입력 후보")), figure,
          h("p", { class: "note" }, "클릭하면 원본 크기 토글 · ", h("a", { href: imgUrl, target: "_blank", rel: "noopener noreferrer" }, "새 탭에서 열기"),
            " · sha256 ", mono(short(current.image_sha256, 16)))),
        h("div", { class: "stackv" },
          h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "정답 (gold)"), h("span", { class: "tag gold" }, "평가·학습 라벨 · 모델 입력 아님")),
            h("p", { class: "sub" }, "PUBLIC_CANONICAL 4개 필드. 빗금 칸은 렌더러 기준으로 이미지에 그대로 보이지 않아 채점·학습에서 마스크되는 필드입니다. 값은 원문 그대로이며 PO에 맞추지 않습니다."),
            h("div", { class: "cap" }), goldTable,
            h("div", { class: "keyrow" }, Object.entries(LABELS.visibility_ko).map(([k, v]) => h("span", null, h("code", null, k), " ", v)))),
          cardH("manifest 메타데이터", null, kv([
            ["template / pool", m.template + " / " + m.pool], ["group_id", mono(m.group_id)],
            ["학습 가능", m.train_eligible ? pillCls("ok", "가능") : h("span", null, pillCls("idle", "불가"), " ", mono(m.train_ineligible_reason))],
            ["채점 / 마스크 필드", m.n_scored_fields + " / " + m.n_masked_fields], ["품목 수", m.n_items],
            ["label_status", m.label_status], ["content_hash", mono(short(m.content_hash, 24))], ["target_hash", mono(short(m.target_hash, 24))],
            ["origin / source", m.origin + " / " + m.source], ["revision", mono(short(m.revision, 12))], ["renderer_commit", mono(short(m.renderer_commit, 12))],
            ["정답 출처 품질", g.from_quality + " (세 품질의 주석은 동일 — 프로파일 검사)"],
          ])))),
    ]);
  }

  // ---- trade data
  const TRADE_FILTERS = ["split", "template", "scenario_type", "mini_role", "injection", "q"];
  async function pageTrade(view, segs, query) {
    if (segs.length) return pageTradeDoc(view, segs);
    lastTradeList = location.hash || "#/trade";
    const { params, page } = listQuery(query, TRADE_FILTERS);
    const [s, res] = await Promise.all([status(), api("/api/trade/rows?" + params.toString())]);
    const tm = s.trade_manifest;
    add(view, [
      pageHead("자체 Invoice–PO", "TRADE_RAW · 합성·가상 회사 · 렌더러 문자열 그대로", tm ? "manifest " + short(tm.sha256, 12) : "manifests/trade_raw_v1"),
      banner("자체 생성한 합성 문서입니다. 정답(gold)·발주서(PO)·시나리오 정보는 평가 데이터이며 모델 입력이 아닙니다.", "info"),
      h("section", { class: "card" }, filterBar("#/trade", query, res.facets, [
        ["split", "split"], ["template", "레이아웃"], ["scenario_type", "시나리오"], ["mini_role", "mini 역할"],
        ["injection", "주입 문구", (v) => (v === "true" ? "포함" : "없음")],
      ], "doc_id 검색", res.total),
      table(["doc_id", "split", "레이아웃", "시나리오", "기대 코드", ["행", "num"], "mini", "주입 문구"],
        res.page.map((r) => rowLink("#/trade/" + r.doc_id, [
          h("td", null, h("a", { class: "mono", href: "#/trade/" + r.doc_id }, r.doc_id)),
          h("td", null, r.split), h("td", { class: "mono" }, r.template), h("td", null, r.scenario_type),
          h("td", null, h("div", { class: "chips" }, (r.expected_codes || []).length ? r.expected_codes.map((c) => h("code", null, c)) : h("span", { class: "sub" }, "없음"))),
          h("td", { class: "num" }, String(r.n_rows)), h("td", null, txt(r.mini_role)),
          h("td", null, r.has_injection_text ? pillCls("warn", "포함") : ""),
        ])), "small", "tall"),
      pager("#/trade", query, res, page),
      tm ? h("p", { class: "note" }, tm.generator_version, " · 행을 누르면 이미지·정답·PO·대사 결과") : null),
    ]);
  }
  const GOLD_ITEM_COLS = ["row_index", "sku_raw", "description_raw", "quantity_raw", "unit_raw", "unit_price_raw", "line_total_raw"];
  const PO_ITEM_COLS = ["po_line_id", "sku", "description", "quantity", "unit", "unit_price"];
  function itemsTable(items, preferred) {
    const cols = preferred.slice();
    for (const it of items || []) for (const k of Object.keys(it)) if (!cols.includes(k)) cols.push(k);
    return table(cols, (items || []).map((it) => h("tr", null, cols.map((c) => h("td", { class: "raw" },
      it[c] === null || it[c] === undefined ? "—" : typeof it[c] === "object" ? JSON.stringify(it[c]) : String(it[c]))))), "small");
  }
  function scalarPairs(obj, skip) {
    return Object.entries(obj || {}).filter(([k]) => !skip.includes(k)).map(([k, v]) =>
      [k, h("span", { class: "raw" }, v === null || v === undefined ? "null" : typeof v === "object" ? JSON.stringify(v) : String(v))]);
  }
  async function pageTradeDoc(view, segs) {
    const docId = segs[0];
    if (!TRADE_ID_RE.test(docId)) {
      add(view, [pageHead("자체 Invoice–PO"), card("잘못된 주소", h("p", null, "doc_id 형식이 맞지 않습니다."), h("a", { href: lastTradeList }, "목록으로"))]);
      return;
    }
    await status();
    const d = await api("/api/trade/doc/" + docId);
    const m = d.meta, integ = d.integrity || {};
    const imgUrl = "/api/trade/image/" + docId;
    const figure = imageFigure(imgUrl, docId + " 문서 이미지", integ.image !== null, integ.image !== null ? "이미지 불러오는 중…" : "로컬 이미지 없음");
    const o = d.oracle;
    const findings = o && !o.findings.length ? h("p", { class: "sub" }, "발견 사항 없음 (findings 0건)") : o ? table(["코드", "심각도", "행", "필드", "기대(PO 등)", "관측(인보이스)", "메시지"],
      o.findings.map((f) => h("tr", null, h("td", null, h("code", null, f.code)),
        h("td", null, pillCls(f.severity === "blocker" ? "bad" : "warn", f.severity === "blocker" ? "차단" : "경고")),
        h("td", { class: "mono" }, txt(f.row_index)), h("td", { class: "mono" }, txt(f.field)),
        h("td", { class: "raw" }, txt(f.expected)), h("td", { class: "raw" }, txt(f.observed)), h("td", { class: "msg" }, f.message))), "small") : null;
    add(view, [
      h("a", { class: "back", href: lastTradeList }, "← 자체 Invoice–PO 목록"),
      pageHead(docId, m.split + " · " + m.template + " · " + m.scenario_type),
      m.has_injection_text ? banner("이 문서 이미지에는 프롬프트 주입 문구가 들어 있습니다(견고성 테스트용). 화면에는 일반 텍스트로만 표시하며 어떤 지시도 실행하지 않습니다.") : null,
      h("div", { class: "cols detail" },
        h("section", { class: "card sticky" }, h("div", { class: "cardhead" }, h("h2", null, "문서 이미지"), h("span", { class: "hint" }, "모델 입력 후보")), figure,
          h("p", { class: "note" }, "클릭하면 원본 크기 토글 · ", h("a", { href: imgUrl, target: "_blank", rel: "noopener noreferrer" }, "새 탭에서 열기"),
            " · ", m.width + "×" + m.height, " · sha256 ", mono(short(m.image_sha256, 16)))),
        h("div", { class: "stackv" },
          h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "대사 결과"), h("span", { class: "hint" }, "기대 코드 vs oracle")),
            kv([
              ["기대 코드 (manifest)", h("div", { class: "chips" }, d.expected_codes.length ? d.expected_codes.map((c) => h("code", null, c)) : "없음")],
              ["oracle 코드", d.oracle_codes ? h("div", { class: "chips" }, d.oracle_codes.length ? d.oracle_codes.map((c) => h("code", null, c)) : "없음") : "미실행 (정답 파일 없음)"],
              ["일치", d.codes_match === null ? pillCls("warn", "미확인") : yesNo(d.codes_match, "일치", "불일치")],
              ["case_status", o ? mono(o.case_status) : "—"], ["reference_total_difference", o ? mono(o.reference_total_difference) : "—"],
            ]), h("p", { class: "note" }, "oracle_fixture = 정답(gold)과 발주서로 규칙 엔진을 돌린 기준 결과입니다. 모델 예측 결과가 아닙니다."), findings),
          h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "정답 (gold, TRADE_RAW)"), h("span", { class: "tag gold" }, "평가 데이터 · 모델 입력 아님")),
            d.gold ? [kv(scalarPairs(d.gold, ["items"])), h("h3", null, "품목 (원문 문자열)"), itemsTable(d.gold.items, GOLD_ITEM_COLS)]
              : h("p", { class: "err" }, "로컬 정답 파일 없음")),
          h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "발주서 (PO)"), h("span", { class: "tag po" }, "대사 입력 · 모델 입력 아님")),
            d.po ? [kv(scalarPairs(d.po, ["items"])), h("h3", null, "발주 행"), itemsTable(d.po.items, PO_ITEM_COLS)]
              : h("p", { class: "err" }, "로컬 발주서 파일 없음")),
          cardH("manifest 메타데이터·무결성", null, kv([
            ["gold / PO / 이미지 sha256", h("span", null, yesNo(integ.gold, "gold 일치", "gold 불일치"), yesNo(integ.po, "PO 일치", "PO 불일치"), yesNo(integ.image, "이미지 일치", "이미지 불일치"))],
            ["split / standard / mini", m.split + " / " + txt(m.standard_role) + " / " + txt(m.mini_role)],
            ["family_id", mono(m.family_id)], ["scenario_type / transaction_diff", m.scenario_type + " / " + String(m.transaction_diff)],
            ["render_check / quality", m.render_check + " / " + m.quality], ["fonts", m.font_regular + " · " + m.font_bold],
            ["generator / seed", m.generator_version + " / " + m.seed], ["origin / task", m.origin + " / " + m.task],
          ])))),
    ]);
  }

  // ---- splits / manifests
  async function pageSplits(view) {
    const s = await status();
    const pm = s.public_manifest, tm = s.trade_manifest, pp = s.public_profile;
    const parts = [pageHead("분할·manifest", "누수 없는 분할과 동결된 manifest 요약", "manifests/*.summary.json"), statusErrors(s)];
    if (pm) {
      const roles = ["train", "dev", "dev_stress", "iid_final", "ood_final"];
      const prof = pm.profiles || {};
      const leakChecks = Object.entries(pm.checks || {}).filter(([k]) => k !== "pass");
      parts.push(h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "공개 InvoiceOCR-Synth"), h("span", { class: "tag" }, "PUBLIC_CANONICAL · 합성")),
        kv([["manifest", mono(pm.manifest)], ["sha256", mono(pm.sha256)], ["seed / revision", h("span", null, String(pm.seed), " / ", mono(short(pm.revision, 12)))],
          ["행 / base / group", pm.rows + " / " + pm.base_documents + " / " + pm.groups], ["누수 검사", yesNo(pm.checks && pm.checks.pass, "통과", "실패")],
          ["동결", pm.frozen ? pillCls("ok", "동결됨") : pillCls("warn", "미동결 — 프로필 선택 후 동결")]]),
        h("div", { class: "cols" },
          h("div", null, h("h3", null, "pool별 base 문서"), bars(pm.pool_base_docs)),
          h("div", null, h("h3", null, "마스크 사유 (학습 불가 base)"), bars(pm.ineligible_reasons))),
        h("h3", null, "standard / mini 역할 (이미지 행)"),
        table(["역할", ["standard 이미지", "num"], ["mini 이미지", "num"], ["standard 채점", "num"], ["standard 마스크", "num"], ["mini 채점", "num"], ["mini 마스크", "num"]],
          roles.map((r) => h("tr", null, h("td", null, r), ["standard", "mini"].map((p) => h("td", { class: "num" }, String(((prof[p] || {}).image_rows_by_role || {})[r] || 0))),
            ["standard", "mini"].map((p) => [h("td", { class: "num" }, String(((prof[p] || {}).scored_fields_by_role || {})[r] || 0)), h("td", { class: "num" }, String(((prof[p] || {}).masked_fields_by_role || {})[r] || 0))]))), "small"),
        h("div", { class: "cols" },
          h("div", null, h("h3", null, "템플릿별 학습 가능 base"), kv(Object.entries(pm.train_eligible_by_template || {}).map(([k, v]) => [k, v]))),
          h("div", null, h("h3", null, "필드 가시성 (전체 base)"), bars(pm.field_status_counts_all_bases))),
        leakChecks.length ? [h("h3", null, "검사 항목"), kv(leakChecks.map(([k, v]) => [k, h("span", { class: "raw" }, typeof v === "object" ? JSON.stringify(v) : String(v))]))] : null));
    } else parts.push(card("공개 manifest", h("p", null, "manifests/public_canonical_v1.summary.json 없음")));
    if (pp) {
      parts.push(cardH("공개 데이터 프로파일 (T01)", "reports/data/public_profile.json", kv([["dataset / revision", h("span", null, pp.dataset_id, " @ ", mono(short(pp.revision, 12)))],
        ["license / origin", pp.license_tag + " / " + pp.origin], ["SKU 정답", pp.sku_labels_available ? "있음" : "없음"],
        ["자동 검사", h("span", { class: "chips" }, Object.entries(pp.checks || {}).map(([k, v]) => h("span", null, yesNo(v.pass, k, k))))]]),
        h("div", { class: "cols" }, h("div", null, h("h3", null, "템플릿별 base 문서"), bars(pp.counts.templates_base_docs)),
          h("div", null, h("h3", null, "문서당 품목 수"), bars(pp.counts.items_per_doc)))));
    }
    if (tm) {
      const types = Object.keys(Object.values(tm.type_by_template || {})[0] || {});
      const rows = [];
      for (const [split, byType] of Object.entries(tm.type_by_template || {})) {
        const tpls = [...new Set(Object.values(byType).flatMap((v) => Object.keys(v)))].sort();
        for (const tpl of tpls) rows.push(h("tr", null, h("td", null, split), h("td", { class: "mono" }, tpl), types.map((t) => h("td", { class: "num" }, String((byType[t] || {})[tpl] || "·")))));
      }
      const leaks = (tm.checks && tm.checks.split_leaks) || {};
      parts.push(h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "자체 Invoice–PO"), h("span", { class: "tag" }, "TRADE_RAW · 합성·가상 회사")),
        kv([["manifest", mono(tm.manifest)], ["sha256", mono(tm.sha256)], ["문서", tm.documents + " (train/dev/test = " + ["train", "dev", "test"].map((k) => tm.by_split[k] || 0).join(" / ") + ")"],
          ["mini (train/dev/test)", ["train", "dev", "test"].map((k) => (tm.mini_by_split || {})[k] || 0).join(" / ")],
          ["렌더=정답 검사", yesNo(tm.checks && tm.checks.all_render_checks_pass, "통과", "실패")],
          ["레이아웃 holdout", yesNo(tm.checks && tm.checks.template_holdout_respected, "지켜짐", "위반")],
          ["split 누수", h("span", { class: "chips" }, Object.entries(leaks).map(([k, v]) => ((v || []).length ? pillCls("bad", k + " " + v.length) : pillCls("ok", k + " 0"))))],
          ["주입 문구 문서", String((tm.checks || {}).injection_text_docs)], ["동결", tm.frozen ? pillCls("ok", "동결됨") : pillCls("warn", "미동결")]]),
        h("h3", null, "split × 레이아웃 × 시나리오"), table(["split", "layout"].concat(types.map((t) => [t, "num"])), rows, "small"),
        h("div", { class: "cols" }, h("div", null, h("h3", null, "문서당 행 수"), bars(tm.rows_per_doc)),
          h("div", null, h("h3", null, "글꼴"), bars(tm.fonts_used))),
        tm.note ? h("p", { class: "note" }, tm.note) : null));
    } else parts.push(card("자체 manifest", h("p", null, "manifests/trade_raw_v1.summary.json 없음")));
    if (s.cord) parts.push(cordDataCard(s.cord));
    add(view, parts);
  }

  // ---- model / evaluation / training
  function sparkline(values) {
    const tpl = document.getElementById("tpl-spark");
    if (!tpl || values.length < 2) return null;
    const svg = tpl.content.firstElementChild.cloneNode(true);
    const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
    const pts = values.map((v, i) => (i / (values.length - 1) * 100).toFixed(2) + "," + (3 + (1 - (v - lo) / span) * 34).toFixed(2));
    svg.querySelector(".spark-line").setAttribute("points", pts.join(" "));
    svg.querySelector(".spark-area").setAttribute("points", "0,40 " + pts.join(" ") + " 100,40");
    return svg;
  }
  function trainingCard(reports, finalAdapter) {
    const runs = Object.entries(reports || {}).filter(([name, r]) => /^train_m1/.test(name) && r && r.run_id).map(([, r]) => r);
    if (!runs.length) return card("M1 학습 기록", h("p", null, pill("not_run"), " reports/model/train_m1*.json 없음"));
    const used = (r) => finalAdapter && ((r.adapter_files_sha256 || {})["adapter_model.safetensors"] || "") === finalAdapter;
    const primary = runs.find(used) || runs[0];
    const losses = (primary.loss_log || []).map((x) => Number(x.loss)).filter((x) => !Number.isNaN(x));
    const tr = primary.trainable || {}, cfg = primary.config || {}, env = primary.env || {};
    return h("section", { class: "card" },
      h("div", { class: "cardhead" }, h("h2", null, "M1 QLoRA 학습"), h("span", { class: "hint" }, "reports/model/" + "train_" + primary.run_id + ".json")),
      h("div", { class: "cols" },
        h("div", null,
          kv([
            ["run", h("span", null, mono(primary.run_id), " ", used(primary) ? pillCls("ok", "final에 사용한 어댑터") : null)],
            ["프레임워크", primary.framework],
            ["기본 모델", h("span", null, primary.base_model, " @ ", mono(short(primary.base_revision, 12)))],
            ["정밀도", env.precision],
            ["학습 기록", primary.records + "건 (" + Object.entries(primary.records_by_task || {}).map(([k, v]) => k + " " + v).join(" · ") + ")"],
            ["optimizer step", primary.optimizer_steps + " (micro batch " + cfg.micro_batch + " × grad accum " + cfg.grad_accum + ", ≈" + fmt(primary.epochs_equivalent, 2) + " epoch)"],
            ["학습률 / 스케줄", cfg.lr + " · " + cfg.scheduler + " · warmup " + cfg.warmup_ratio],
            ["학습 파라미터", (tr.trainable_params || 0).toLocaleString() + " / " + (tr.total_params || 0).toLocaleString() + " (vision 학습 " + (tr.visual_trainable ? "예" : "아니오") + ")"],
            ["시간 / 최대 VRAM", fmt(primary.train_seconds / 60, 1) + "분 · " + primary.peak_vram_gb + " GB"],
            ["GPU / 환경", env.gpu + " · torch " + env.torch + " · transformers " + env.transformers + " · peft " + env.peft + " · bnb " + env.bitsandbytes],
            ["어댑터 sha256", mono(short((primary.adapter_files_sha256 || {})["adapter_model.safetensors"], 20))],
          ])),
        h("div", null,
          h("div", { class: "cap" }, "학습 loss (step별 기록)"),
          losses.length > 1 ? h("div", { class: "sparkbox" }, sparkline(losses),
            h("div", { class: "sparkmeta" }, h("span", null, "step 1 · " + fmt(losses[0], 3)), h("span", null, "평균 train_loss " + fmt(primary.train_loss, 4)), h("span", null, "step " + losses.length + " · " + fmt(losses[losses.length - 1], 3))))
            : h("p", { class: "sub" }, "loss 기록 없음"),
          runs.length > 1 ? [h("h3", null, "다른 학습 실행"), table(["run", ["step", "num"], ["train_loss", "num"], ["기록", "num"], "어댑터"],
            runs.map((r) => h("tr", null, h("td", { class: "mono" }, r.run_id), h("td", { class: "num" }, String(r.optimizer_steps)), h("td", { class: "num" }, fmt(r.train_loss, 4)),
              h("td", { class: "num" }, String(r.records)), h("td", null, used(r) ? pillCls("ok", "final 사용") : finalAdapter ? pillCls("idle", "미채택") : "—"))), "small")] : null)));
  }
  async function pageModel(view) {
    const s = await status();
    const evals = s.evaluations || [], comps = s.comparisons || [];
    const finals = mainRuns(evals, "final"), devs = mainRuns(evals, "dev");
    const finalSets = orderSets(Array.from(new Set(Object.values(finals).flatMap((e) => Object.keys(e.headline)))));
    const devSets = orderSets(Array.from(new Set(Object.values(devs).flatMap((e) => Object.keys(e.headline))))).filter((k) => k !== "stress:all");
    const finalAdapter = (finals.m1 || {}).adapter_sha256;
    const byStage = (st) => evals.filter((e) => e.stage === st).sort((a, b) => ARM_ORDER.indexOf(runKey(a.run_id)) - ARM_ORDER.indexOf(runKey(b.run_id)) || String(a.run_id).localeCompare(String(b.run_id)));
    add(view, [
      pageHead("모델·평가", "B0 OCR vs M0 기본 VLM vs M1 QLoRA · 동일 frozen manifest·NF4·프롬프트·전처리·생성 설정", "reports/eval/*.json"),
      banner("모든 수치는 합성 데이터 기준입니다." + (finalSets.length ? " FINAL은 설정을 동결한 뒤 한 번만 실행했고, 실패·누락 문서도 분모에 남깁니다." : "") + " 결과 파일이 없는 칸은 미실행으로 표시합니다.", "info"),
      statusErrors(s),
      finalSets.length
        ? h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "FINAL — strict 필드 정확도"),
            h("span", { class: "hint" }, Object.values(finals).map((e) => runName(e.run_id) + " " + (e.denominator_check ? e.denominator_check.predicted + "/" + e.denominator_check.expected : "?")).join(" · ") + " 문서")),
          armLegend(), armChart(finals, finalSets),
          h("p", { class: "note" }, "M0은 공개 세트에서 출력을 ```json 코드펜스로 감싸 strict JSON이 0%라 strict 정확도가 0입니다. ◇ 표시는 코드펜스를 벗긴 lenient 점수로, 읽기 능력과 형식 준수를 분리해 보여줍니다."))
        : card("FINAL", h("p", null, pill("not_run"), " final 채점 파일 없음")),
      forestCard(stageComps(comps, evals, "final"), "FINAL paired 차이 (A − B)"),
      trainingCard(s.model_reports, finalAdapter),
      devSets.length ? details("DEV 결과 (개발 중 비교 · final 아님)", armLegend(), armChart(devs, devSets), forestCard(stageComps(comps, evals, "dev"), "DEV paired 차이")) : null,
      details("세부 표 — 실행별 원본 수치",
        ["final", "dev"].map((st) => byStage(st).length ? [h("h3", null, st === "final" ? "FINAL" : "DEV"), evalTable(byStage(st))] : null),
        h("p", { class: "note" }, "세트별로만 집계합니다(세트 합산 없음). 셀: strict 필드 정확도 · 문서 exact · strict JSON 유효율 · 문서 수 · base/family bootstrap 95% CI. 굵게 = 해당 세트 최고값.")),
      (s.local_smoke || []).length ? details("로컬 스모크 기록 (원문 키/값)",
        h("p", { class: "sub" }, "마스크 감사·파일럿·10-step 학습 스모크 파일을 해석하지 않고 그대로 보여줍니다. final 평가 결과가 아닙니다."),
        s.local_smoke.map((f) => [h("h3", { class: "mono" }, f.path), kv(f.pairs.map(([k, v]) => [h("span", { class: "mono" }, k), h("span", { class: "raw" }, v)]))])) : null,
    ]);
  }

  // ---- CORD v2 real receipt photos (docs/20_DECISIONS_V6.md) — data browser + pre-registered evaluation
  const CORD_ARMS = {
    "M0": { cls: "s-m0", desc: "기본 모델 · NF4" },
    "M1 v1": { cls: "s-m1", desc: "기존 M1 (CORD 없이 학습)" },
    "M1-cord": { cls: "s-m1c", desc: "CORD train 742건을 더해 학습" },
  };
  const CORD_ARM_ORDER = ["M0", "M1 v1", "M1-cord"];
  const CORD_STAGES = [["cord:dev", "dev", "공식 validation 100장 · 개발·비교용"], ["cord:test", "test", "공식 test 100장 · 동결 후 1회"]];
  const CORD_GROUPS = [["item.name", "품목 이름"], ["item.count", "품목 수량"], ["item.unit_price", "품목 단가"], ["item.price", "품목 금액"],
    ["sub.name", "하위 품목 이름"], ["sub.count", "하위 품목 수량"], ["sub.unit_price", "하위 품목 단가"], ["sub.price", "하위 품목 금액"],
    ["doc.subtotal", "소계 (subtotal)"], ["doc.tax", "세금 (tax)"], ["doc.total", "합계 (total)"]];
  const CORD_STATE = { ok: ["✓", "일치"], format: ["≈", "형식만 다름 (숫자·글자는 같음)"], wrong: ["✗", "틀림"], missing: ["∅", "빠뜨림"],
    filled: ["+", "정답에 없는 값을 채움"], empty: ["", "정답·예측 모두 없음"], masked: ["", "채점 제외 (원 라벨이 여러 상자)"] };
  const CORD_OVERLAP = { none: "겹침 없음", seen_in_train: "train과 같은 정답", dup_excluded: "dev/test와 같은 정답 → 학습 제외" };
  const CORD_FILTERS = ["split", "eligible", "overlap", "has_sub", "masked", "q"];
  const CORD_ID_RE = /^cord_(train|dev|test)_\d{4}$/;
  let lastCordList = "#/cord";
  const blankCell = (title) => h("td", { class: "blank", title: title || "아직 실행하지 않음" }, "—");

  function cordEvals(c) { // {set: {arm label: evaluation}} — latest file per arm wins (files are sorted by name)
    const out = {};
    for (const e of (c && c.evaluations) || []) (out[e.set] = out[e.set] || {})[e.label || e.run_id] = e;
    return out;
  }
  function cordComp(c, a, b) {
    return ((c && c.comparisons) || []).find((x) => x.a_label === a && x.b_label === b) || null;
  }
  function cordLegend() {
    return h("div", { class: "legend" },
      CORD_ARM_ORDER.map((k) => h("span", { class: "key" }, h("span", { class: "sw " + CORD_ARMS[k].cls }), h("b", null, k), " " + CORD_ARMS[k].desc)),
      h("span", { class: "key" }, h("span", { class: "lenkey" }), "형식 무시 정확도 (보조 A)"),
      h("span", { class: "key" }, h("span", { class: "blankkey" }), "미실행 (빈칸)"));
  }
  function cordBars(byStage, subset) {
    const grid = h("div", { class: "armchart" },
      h("div", { class: "axis", "aria-hidden": "true" }, [0, 0.25, 0.5, 0.75, 1].map((t) => h("span", { css: { left: pct(t) } }, t === 0 ? "0" : t.toFixed(2)))));
    for (const [set, name, desc] of CORD_STAGES) {
      const arms = byStage[set] || {};
      const first = CORD_ARM_ORDER.map((a) => arms[a]).find(Boolean);
      const n = first ? (first[subset] || {}).documents : null;
      grid.append(h("div", { class: "setlabel" }, "CORD " + name + (subset === "unseen" ? " · 내용 미중복" : ""),
        h("small", null, [desc, n ? "n " + n : null].filter(Boolean).join(" · "))));
      const rows = h("div", { class: "setbars" });
      for (const a of CORD_ARM_ORDER) {
        const e = arms[a], v = e ? e[subset] : null;
        if (!v) { rows.append(h("div", { class: "armbar blankbar" }, h("span", { class: "val", css: { left: "0%" } }, a + " — 미실행"))); continue; }
        const acc = Number(v.strict_field_accuracy.accuracy) || 0, loose = Number(v.format_insensitive_accuracy.accuracy);
        const label = a + " · CORD " + name + " · strict " + fmt(acc) + " · 형식 무시 " + fmt(loose);
        const bar = h("div", { class: "armbar", tabindex: "0", role: "img", "aria-label": label },
          h("i", { class: "fill " + CORD_ARMS[a].cls + (acc === 0 ? " zero" : ""), css: { width: pct(acc) } }),
          Number.isNaN(loose) ? null : h("em", { class: "len", css: { left: pct(loose) } }),
          h("span", { class: "val", css: { left: pct(Math.max(acc, Number.isNaN(loose) ? 0 : loose)) } }, fmt(acc), h("small", null, " · ◇ " + fmt(loose))));
        attachTip(bar, () => [h("b", null, a + " · CORD " + name),
          tipLine("strict 필드 정확도", fmt(acc) + " (" + v.strict_field_accuracy.correct + "/" + v.strict_field_accuracy.scored + ")"),
          tipLine("형식 무시 정확도", fmt(loose)), tipLine("순서 무관 F1", fmt(v.order_free_f1.f1)),
          tipLine("정답에 없는 값 채움", String(v.absent_fields_filled)), tipLine("문서 exact", fmt(v.doc_exact, 2)),
          h("div", { class: "tl" }, e.run_id)]);
        rows.append(bar);
      }
      grid.append(rows);
    }
    return grid;
  }
  const CORD_DIFFS = [["strict_field_accuracy", "strict 필드 정확도 (주 지표)"], ["format_insensitive_accuracy", "형식 무시 정확도 (보조 A)"],
    ["order_free_f1", "순서 무관 F1 (보조 B)"], ["doc_exact", "문서 전체 일치"]];
  function cordForest(cmp, set, subset) {
    const R = 0.6;
    const pos = (d) => (((Math.max(-R, Math.min(R, Number(d))) + R) / (2 * R)) * 100).toFixed(2) + "%";
    const v = cmp && cmp.sets[set] ? cmp.sets[set][subset] : null;
    if (!v) return h("p", { class: "blanknote" }, pill("not_run"), " ", set === "cord:test" ? "CORD test는 설정 동결 뒤 한 번만 실행합니다 — 아직 결과가 없습니다." : "이 비교의 결과 파일이 없습니다.");
    const grid = h("div", { class: "forest" },
      h("div", { class: "faxis", "aria-hidden": "true" }, [-R, -R / 2, 0, R / 2, R].map((t) => h("span", { css: { left: pos(t) } }, t > 0 ? "+" + t.toFixed(1) : t < 0 ? "−" + Math.abs(t).toFixed(1) : "0"))));
    for (const [key, label] of CORD_DIFFS) {
      const x = v[key];
      if (!x) continue;
      const d = Number(x.diff), ci = (x.ci95 || []).map(Number);
      const sig = ci.length === 2 ? ci[0] > 0 || ci[1] < 0 : null;
      grid.append(h("div", { class: "fl" }, label, h("small", null, "같은 문서 " + v.n_docs + "건 · 클러스터 " + v.n_clusters)));
      const track = h("div", { class: "ft", tabindex: "0", role: "img", "aria-label": cmp.a_label + " − " + cmp.b_label + " " + label + " " + signed(d) },
        h("i", { class: "zero" }),
        ci.length === 2 ? h("b", { class: "ci", css: { left: pos(ci[0]), width: (Math.max(0, Math.min(R, ci[1]) - Math.max(-R, ci[0])) / (2 * R) * 100).toFixed(2) + "%" } }) : null,
        h("em", { class: "pt" + (sig ? "" : " ns"), css: { left: pos(d) } }));
      attachTip(track, () => [h("b", null, cmp.a_label + " − " + cmp.b_label), tipLine(label, signed(d) + (ci.length === 2 ? "  [" + signed(ci[0]) + ", " + signed(ci[1]) + "]" : ""))]);
      grid.append(track, h("div", { class: "fv" }, signed(d) + (ci.length === 2 ? "  [" + signed(ci[0]) + ", " + signed(ci[1]) + "]" : "")),
        h("div", { class: "fs" }, sig === null ? pillCls("idle", "CI 없음") : sig ? pillCls(d > 0 ? "ok" : "warn", (d > 0 ? cmp.a_label : cmp.b_label) + " 우세") : pillCls("idle", "유의하지 않음")));
    }
    return grid;
  }
  function cordForestCard(c) {
    const pairs = [["M1-cord", "M0", "주 비교"], ["M1-cord", "M1 v1", "CORD를 더한 효과"], ["M1 v1", "M0", "기존 어댑터의 전이"]];
    const state = { pair: 0, set: "cord:dev", subset: "all" };
    const body = h("div");
    const seg = (items, key) => {
      const buttons = items.map(([value, label]) => h("button", { type: "button", "aria-pressed": state[key] === value ? "true" : "false",
        onclick: () => { state[key] = value; buttons.forEach((b, i) => b.setAttribute("aria-pressed", items[i][0] === value ? "true" : "false")); draw(); } }, label));
      return h("div", { class: "segtabs", role: "group" }, buttons);
    };
    function draw() {
      const [a, b] = pairs[state.pair];
      body.replaceChildren(cordForest(cordComp(c, a, b), state.set, state.subset));
    }
    draw();
    return h("section", { class: "card" },
      h("div", { class: "cardhead" }, h("h2", null, "paired 차이 (A − B) · 95% CI"),
        h("span", { class: "hint" }, "같은 문서 쌍 bootstrap 2,000회 · 정답이 같은 문서는 한 묶음으로 재표집")),
      h("div", { class: "toolrow" }, seg(pairs.map(([a, b, note], i) => [i, a + " − " + b + " (" + note + ")"]), "pair"),
        seg([["cord:dev", "dev"], ["cord:test", "test"]], "set"), seg([["all", "전체 100"], ["unseen", "내용 미중복"]], "subset")),
      h("div", { class: "legend" }, h("span", { class: "key" }, h("span", { class: "dot run" }), "CI가 0을 포함하지 않음 (유의)"),
        h("span", { class: "key" }, h("span", { class: "dot idle" }), "CI가 0을 포함 (유의하지 않음)")),
      body);
  }
  function verdictCell(ok, text) {
    return h("td", null, ok === null ? pillCls("idle", "미실행") : ok ? pillCls("ok", "충족") : pillCls("warn", "미충족"), text ? h("div", { class: "sub" }, text) : null);
  }
  // four decimals: the effect threshold is +0.05, and a three-decimal "+0.050" would hide a +0.0497 miss
  function ciText(x) { return x ? signed(x.diff, 4) + " [" + signed(x.ci95[0], 4) + ", " + signed(x.ci95[1], 4) + "]" : null; }
  function cordCriteriaCard(c) {
    const main = cordComp(c, "M1-cord", "M0");
    const at = (set) => (main && main.sets[set] ? main.sets[set].all : null);
    const dev = at("cord:dev"), test = at("cord:test");
    const effect = (v) => (v ? v.strict_field_accuracy.diff >= 0.05 && v.strict_field_accuracy.ci95[0] > 0 : null);
    const reading = (v) => (v ? effect(v) && v.format_insensitive_accuracy.ci95[0] > 0 : null);
    const reg = c.regression;
    const regRows = reg ? Object.entries(reg.sets || {}).filter(([k]) => k === "trade:dev" || k === "public:dev|clean") : [];
    const regOk = regRows.length ? regRows.every(([, v]) => Number(v.field_acc_diff) >= -0.03) : null;
    const regText = regRows.length ? regRows.map(([k, v]) => setInfo(k)[0] + " " + signed(v.field_acc_diff)).join(" · ") : null;
    return h("section", { class: "card" },
      h("div", { class: "cardhead" }, h("h2", null, "사전 고정 판정 기준"), h("span", { class: "hint" }, "docs/20_DECISIONS_V6.md · 학습 전에 고정")),
      table(["기준", "dev (참고 · 판정 아님)", "test (판정)"], [
        h("tr", null, h("td", null, h("b", null, "파인튜닝 효과"), h("div", { class: "sub" }, "M1-cord − M0 strict ≥ +0.05 이고 95% CI 하한 > 0")),
          verdictCell(effect(dev), dev ? ciText(dev.strict_field_accuracy) : null), verdictCell(effect(test), test ? ciText(test.strict_field_accuracy) : null)),
        h("tr", null, h("td", null, h("b", null, "읽기도 좋아짐"), h("div", { class: "sub" }, "위 기준 + 형식 무시 차이의 CI 하한 > 0. 아니면 \"주로 형식을 맞춘 효과\"")),
          verdictCell(reading(dev), dev ? ciText(dev.format_insensitive_accuracy) : null), verdictCell(reading(test), test ? ciText(test.format_insensitive_accuracy) : null)),
        h("tr", null, h("td", null, h("b", null, "기존 성능 유지"), h("div", { class: "sub" }, "기존 dev(trade dev · public dev clean)에서 M1-cord가 M1 v1보다 0.03 넘게 떨어지지 않음")),
          verdictCell(regOk, regText || (reg ? null : "회귀 비교 파일 없음 (진행 중이거나 미실행)")), h("td", { class: "sub" }, "test 기준 아님 — 기존 dev로 판정")),
      ], "small"),
      h("p", { class: "note" }, "test 칸은 configs/frozen_cord_v1.json으로 설정을 동결한 뒤 arm마다 한 번만 실행해 채웁니다. dev 값은 개발 중 비교용 참고값이며 판정에 쓰지 않습니다. 결과가 기준에 못 미쳐도 그대로 보고합니다."));
  }
  function cordMetricTable(byStage) {
    const cols = [];
    for (const [set, name] of CORD_STAGES) for (const a of CORD_ARM_ORDER) cols.push([set, name, a]);
    const get = (set, a) => (byStage[set] || {})[a];
    const row = (label, fn, hint) => h("tr", null, h("td", null, label, hint ? h("div", { class: "sub" }, hint) : null),
      cols.map(([set, , a]) => { const e = get(set, a); return e ? h("td", { class: "num" }, fn(e)) : blankCell(); }));
    const acc = (x) => [fmt(x.accuracy), h("div", { class: "sub" }, x.correct + "/" + x.scored)];
    return table(["지표"].concat(cols.map(([, name, a]) => [h("span", null, h("span", { class: "sw " + CORD_ARMS[a].cls }), " ", a, h("div", { class: "sub" }, "CORD " + name)), "num"])), [
      row("strict 필드 정확도", (e) => acc(e.all.strict_field_accuracy), "주 지표 · 펜스 하나만 벗긴 출력"),
      row("형식 무시 정확도", (e) => acc(e.all.format_insensitive_accuracy), "숫자는 숫자만, 이름은 대소문자·공백 무시"),
      row("순서 무관 F1", (e) => [fmt(e.all.order_free_f1.f1), h("div", { class: "sub" }, "P " + fmt(e.all.order_free_f1.precision, 2) + " · R " + fmt(e.all.order_free_f1.recall, 2))]),
      row("내용 미중복 strict", (e) => [fmt(e.unseen.strict_field_accuracy.accuracy), h("div", { class: "sub" }, "n " + e.unseen.documents)], "train과 정답이 겹치지 않는 문서"),
      row("펜스 없는 JSON 비율", (e) => fmt(e.strict_json.json_valid_rate, 2), "형식 지표 (출력을 그대로 파싱)"),
      row("정답에 없는 값 채움", (e) => String(e.all.absent_fields_filled), "인쇄되지 않은 값을 지어낸 필드 수"),
      row("행 수 일치", (e) => fmt(e.all.row_count_match_rate, 2)),
      row("문서 전체 일치", (e) => fmt(e.all.doc_exact, 2)),
      row("실행 시간", (e) => [fmt(e.wall_seconds / 60, 1) + "분", h("div", { class: "sub" }, fmt(e.wall_seconds / Math.max(1, e.all.documents), 1) + "초/문서")], "로컬 RTX 4070 Ti SUPER · 배치 1"),
      row("최대 VRAM", (e) => fmt(e.peak_vram_gb, 2) + " GB"),
    ], "small");
  }
  function cordFieldTable(byStage) {
    const cols = [];
    for (const [set, name] of CORD_STAGES) for (const a of CORD_ARM_ORDER) cols.push([set, name, a]);
    return table(["필드", ["채점 수", "num"]].concat(cols.map(([, name, a]) => [h("span", null, a, h("div", { class: "sub" }, name)), "num"])),
      CORD_GROUPS.map(([g, label]) => {
        const vals = cols.map(([set, , a]) => { const e = (byStage[set] || {})[a]; return e ? ((e.all.by_field_strict || {})[g] || null) : undefined; });
        const best = {};
        cols.forEach(([set], i) => { if (vals[i]) best[set] = Math.max(best[set] ?? -1, Number(vals[i].accuracy)); });
        return h("tr", null, h("td", null, label, h("div", { class: "sub mono" }, g)),
          h("td", { class: "num" }, [...new Set(cols.map(([set]) => set))].map((set) => {
            const e = Object.values(byStage[set] || {})[0];
            const x = e && (e.all.by_field_strict || {})[g];
            return x ? h("div", null, x.scored, h("small", { class: "sub" }, " " + set.split(":")[1])) : null;
          })),
          vals.map((x, i) => x === undefined ? blankCell() : x === null ? h("td", { class: "num" }, "—")
            : h("td", { class: "num" + (Number(x.accuracy) === best[cols[i][0]] ? " best" : "") }, fmt(x.accuracy, 2))));
      }), "small");
  }
  function cordTrainCard(reports) {
    const t = (reports || {})["train_m1_cord_v1.json"];
    if (!t) return card("M1-cord 학습", h("p", null, pill("not_run"), " reports/model/train_m1_cord_v1.json 없음"));
    const losses = (t.loss_log || []).map((x) => Number(x.loss)).filter((x) => !Number.isNaN(x));
    const cfg = t.config || {}, env = t.env || {}, tr = t.trainable || {};
    return h("section", { class: "card" },
      h("div", { class: "cardhead" }, h("h2", null, "M1-cord QLoRA 학습"), h("span", { class: "hint" }, "reports/model/train_m1_cord_v1.json")),
      h("div", { class: "cols" },
        kv([
          ["학습 기록", t.records + "건 (" + Object.entries(t.records_by_task || {}).map(([k, v]) => k + " " + v).join(" · ") + ")"],
          ["optimizer step", t.optimizer_steps + " (micro " + cfg.micro_batch + " × accum " + cfg.grad_accum + ", ≈" + fmt(t.epochs_equivalent, 2) + " epoch)"],
          ["학습률 / 스케줄", cfg.lr + " · " + cfg.scheduler + " · warmup " + cfg.warmup_ratio + " · seed " + cfg.seed],
          ["기본 모델 정밀도", txt(cfg.base_precision) + " (평가도 NF4에서 — 어댑터·정밀도 짝 검사)"],
          ["학습 파라미터", (tr.trainable_params || 0).toLocaleString() + " (LoRA q/v, vision 학습 " + (tr.visual_trainable ? "예" : "아니오") + ")"],
          ["시간 / 최대 VRAM", fmt(t.train_seconds / 60, 1) + "분 · " + t.peak_vram_gb + " GB"],
          ["GPU", env.gpu + " · torch " + env.torch + " · transformers " + env.transformers + " · peft " + env.peft],
          ["어댑터 sha256", mono(short((t.adapter_files_sha256 || {})["adapter_model.safetensors"], 20))],
        ]),
        h("div", null, h("div", { class: "cap" }, "학습 loss (step별)"),
          losses.length > 1 ? h("div", { class: "sparkbox" }, sparkline(losses),
            h("div", { class: "sparkmeta" }, h("span", null, "step 1 · " + fmt(losses[0], 3)), h("span", null, "평균 " + fmt(t.train_loss, 4)), h("span", null, "step " + losses.length + " · " + fmt(losses[losses.length - 1], 3))))
            : h("p", { class: "sub" }, "loss 기록 없음"))));
  }
  function cordTimeCard(c, reports) {
    const t = (reports || {})["train_m1_cord_v1.json"];
    const rows = (c.runs || []).map((r) => ({ when: r.started, what: r.label + " 추론 · " + r.sets.join(", "), id: r.run_id, start: r.started, end: r.finished, sec: r.wall_seconds }));
    if (t) rows.push({ when: null, what: "M1-cord 학습 (240 step)", id: t.run_id, start: null, end: null, sec: t.train_seconds });
    const pending = [["CORD test · M0", "동결 후"], ["CORD test · M1 v1", "동결 후"], ["CORD test · M1-cord", "동결 후"]]
      .filter(([what]) => !(c.runs || []).some((r) => r.sets.includes("cord:test") && what.endsWith(r.label)));
    const total = rows.reduce((s, r) => s + (Number(r.sec) || 0), 0);
    return cardH("걸린 시간", "로컬 RTX 4070 Ti SUPER · GPU 작업은 한 번에 하나",
      table(["단계", "run", "시작", "종료", ["소요", "num"]], rows.sort((a, b) => (a.when ? 0 : 1) - (b.when ? 0 : 1) || String(a.when).localeCompare(String(b.when)))
        .map((r) => h("tr", null, h("td", null, r.what), h("td", { class: "mono" }, r.id), h("td", { class: "mono" }, txt(r.start && r.start.replace("T", " "))),
          h("td", { class: "mono" }, txt(r.end && r.end.replace("T", " "))), h("td", { class: "num" }, fmt(Number(r.sec) / 60, 1) + "분")))
        .concat(pending.map(([what, note]) => h("tr", { class: "pending" }, h("td", null, what), blankCell(note), blankCell(), blankCell(), blankCell())))
        .concat([h("tr", { class: "total" }, h("td", null, h("b", null, "합계 (기록된 것)")), h("td"), h("td"), h("td"), h("td", { class: "num" }, h("b", null, fmt(total / 60, 1) + "분")))]), "small"),
      h("p", { class: "note" }, "추론 시각은 run_metadata.json(로컬 시각), 학습은 train 기록의 train_seconds입니다(학습 기록에는 시각이 없어 맨 아래에 둡니다). 학습의 시작·종료 시각(UTC)은 artifacts/logs/cord_local_chain.log에 있습니다."));
  }
  function cordDataCard(c) {
    const b = (c.build || {}).summary || {}, f = c.fetch || {};
    const splits = ["train", "dev", "test"];
    return cardH("데이터 — CORD v2", f.repo ? f.repo + " @ " + short(f.revision, 8) : "reports/realdocs/",
      kv([
        ["출처 · 라이선스", h("span", null, txt(f.source), " · ", txt(f.license))],
        ["내려받기", f.all_ok === undefined ? "기록 없음" : h("span", null, yesNo(f.all_ok, "해시 " + f.files + "/" + f.files + " 일치", "해시 불일치"), " · " + fmt((f.total_bytes || 0) / 1e9, 2) + " GB · " + fmt(f.total_seconds, 0) + "초 · 사용자 승인 " + txt(f.approved_by_user))],
        ["로컬 이미지·정답", c.local_data ? pillCls("ok", "있음 (data/processed/cord, Git 제외)") : pillCls("warn", "없음 — 이미지·정답 표시 불가")],
        ["manifest", h("span", { class: "mono" }, "manifests/cord_v2.jsonl · " + short((c.build || {}).manifest_sha256, 16))],
        ["동결", c.frozen ? h("span", null, pillCls("ok", "동결됨"), " " + txt(c.frozen.frozen_at)) : pillCls("idle", "아직 동결 전 — test 미실행")],
      ]),
      table(["split", ["문서", "num"], ["학습 사용", "num"], ["품목", "num"], ["하위 품목", "num"], ["채점 제외 필드 있는 문서", "num"], ["정답 내용이 겹치는 문서", "num"]],
        splits.map((k) => { const x = b[k] || {}; return h("tr", null, h("td", null, k), h("td", { class: "num" }, txt(x.docs)), h("td", { class: "num" }, txt(x.train_eligible)),
          h("td", { class: "num" }, txt(x.items)), h("td", { class: "num" }, txt(x.sub_items)), h("td", { class: "num" }, txt(x.with_masked)),
          h("td", { class: "num" }, k === "train" ? txt(x.content_dup_excluded) + " (학습 제외)" : txt(x.content_seen_in_train) + " (train과 같은 정답)")); }), "small"),
      h("p", { class: "note" }, "인도네시아 실사진 영수증입니다(영어 전용 아님). 품목 이름·수량·단가·금액, 하위 품목, 소계·세금·합계를 인쇄된 그대로 옮기는 별도 태스크 CORD_RAW로 다룹니다. 기존 합성 데이터 계약과 FINAL 결과는 바꾸지 않습니다."));
  }
  function cordOverviewCard(c) {
    if (!c) return null;
    return h("section", { class: "card" },
      h("div", { class: "cardhead" }, h("h2", null, "실사진 영수증 CORD v2 — strict 필드 정확도"), h("a", { href: "#/cordeval" }, "CORD 평가에서 자세히 →")),
      cordLegend(), cordBars(cordEvals(c), "all"),
      h("p", { class: "note" }, "합성 데이터만으로는 학습 효과를 가를 수 없어(M0도 거의 다 맞힘) 추가한 실문서 평가입니다. 사람 라벨·공식 분할·로컬 NF4. 빈칸은 아직 실행하지 않은 결과입니다."));
  }
  async function pageCordEval(view) {
    const s = await status();
    const c = s.cord || {};
    const byStage = cordEvals(c);
    const dev = byStage["cord:dev"] || {}, test = byStage["cord:test"] || {};
    const main = cordComp(c, "M1-cord", "M0");
    const devDiff = main && main.sets["cord:dev"] ? main.sets["cord:dev"].all.strict_field_accuracy : null;
    const testDiff = main && main.sets["cord:test"] ? main.sets["cord:test"].all.strict_field_accuracy : null;
    const subsetBox = h("div");
    let subset = "all";
    const drawBars = () => subsetBox.replaceChildren(cordBars(byStage, subset));
    drawBars();
    const subsetButtons = [["all", "전체 100장"], ["unseen", "train과 정답이 겹치지 않는 문서"]].map(([v, label]) => h("button", { type: "button", "aria-pressed": v === subset ? "true" : "false",
      onclick: (ev) => { subset = v; ev.currentTarget.parentNode.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b === ev.currentTarget ? "true" : "false")); drawBars(); } }, label));
    const kAcc = (e) => (e ? fmt(e.all.strict_field_accuracy.accuracy) : "—");
    add(view, [
      pageHead("CORD 평가", "실사진 영수증 CORD v2 · M0 vs M1-cord · 로컬 RTX 4070 Ti SUPER · 모두 NF4 · 같은 프롬프트·전처리·생성 설정", "reports/eval/cord_*.json"),
      banner("합성 데이터에서는 M0와 M1의 차이가 유의하지 않아(데이터가 너무 쉬움) 사람이 라벨을 단 실사진 영수증을 추가했습니다. 판정 기준은 학습 전에 docs/20에 고정했습니다. 빈칸(—)은 아직 실행하지 않은 결과입니다.", "info"),
      statusErrors(s),
      h("div", { class: "kpis" },
        kpi("dev · M0", kAcc(dev["M0"]), "", "strict 필드 정확도 (기준선)", dev["M0"] ? "idle" : "idle"),
        kpi("dev · M1-cord", kAcc(dev["M1-cord"]), "", devDiff ? "M0 대비 " + ciText(devDiff) : "미실행", dev["M1-cord"] ? "run" : "idle"),
        kpi("test · M0", kAcc(test["M0"]), "", test["M0"] ? "strict 필드 정확도" : "동결 후 1회 실행 예정", test["M0"] ? "ok" : "idle"),
        kpi("test · M1-cord", kAcc(test["M1-cord"]), "", testDiff ? "M0 대비 " + ciText(testDiff) : "동결 후 1회 실행 예정", test["M1-cord"] ? "ok" : "idle")),
      cordCriteriaCard(c),
      h("section", { class: "card" },
        h("div", { class: "cardhead" }, h("h2", null, "strict 필드 정확도 — arm별"), h("div", { class: "segtabs", role: "group", "aria-label": "문서 범위" }, subsetButtons)),
        cordLegend(), subsetBox,
        h("p", { class: "note" }, "막대 = strict 필드 정확도(정답에 값이 있는 필드만, 위치 기준, NFKC·공백 정리 후 완전 일치). ◇ = 형식 무시 정확도(\"@16.500\" = \"16500\"). 막대에 마우스를 올리면 F1·채움 수가 보입니다.")),
      cordForestCard(c),
      cardH("세부 지표", "arm × split · 빈칸은 미실행", cordMetricTable(byStage),
        h("p", { class: "note" }, "M0는 dev 100건 모두 답을 ```json 펜스로 감쌌습니다. 주 지표는 펜스 하나만 벗긴 출력으로 계산하고(docs/20 수정 1), 펜스 없는 JSON 비율은 형식 지표로 따로 둡니다.")),
      cardH("필드별 strict 정확도", "굵게 = 같은 split에서 가장 높음", cordFieldTable(byStage)),
      h("div", { class: "cols" }, cordTrainCard(s.model_reports), cordTimeCard(c, s.model_reports)),
      cordDataCard(c),
    ]);
  }
  async function pageCord(view, segs, query) {
    if (segs.length) return pageCordDoc(view, segs);
    lastCordList = location.hash || "#/cord";
    const { params, page } = listQuery(query, CORD_FILTERS);
    const [s, res] = await Promise.all([status(), api("/api/cord/rows?" + params.toString())]);
    const c = s.cord || {};
    add(view, [
      pageHead("CORD 영수증", "CORD v2 · 실사진 영수증 1,000장 · 사람이 단 라벨 · CC BY 4.0", "manifests/cord_v2.jsonl"),
      banner("정답(gold)은 평가·학습 라벨이며 모델 입력이 아닙니다. 모델 입력은 사진과 고정 프롬프트뿐입니다. dev·test 문서를 열면 기록된 실행(M0·M1 v1·M1-cord)의 예측을 정답과 칸마다 비교해 보여줍니다.", "info"),
      c.local_data === false ? banner("로컬 CORD 이미지·정답이 없습니다(scripts/realdocs/fetch_cord.py → invoiceguard.cord build).", "bad") : null,
      h("section", { class: "card" }, filterBar("#/cord", query, res.facets, [
        ["split", "split"], ["eligible", "학습 사용", (v) => (v === "true" ? "사용" : "미사용")],
        ["overlap", "정답 겹침", (v) => CORD_OVERLAP[v] || v], ["has_sub", "하위 품목", (v) => (v === "true" ? "있음" : "없음")],
        ["masked", "채점 제외 필드", (v) => (v === "true" ? "있음" : "없음")],
      ], "ID 검색", res.total),
      table(["id", "split", ["CORD image_id", "num"], ["품목", "num"], ["하위 품목", "num"], "정답 겹침", "채점 제외", "학습", ["크기", "num"]],
        res.page.map((r) => rowLink("#/cord/" + r.id, [
          h("td", null, h("a", { class: "mono", href: "#/cord/" + r.id }, r.id)), h("td", null, r.split), h("td", { class: "num" }, String(r.cord_image_id)),
          h("td", { class: "num" }, String(r.n_items)), h("td", { class: "num" }, String(r.n_sub_items)),
          h("td", null, r.content_overlap === "none" ? "" : pillCls(r.content_overlap === "dup_excluded" ? "warn" : "idle", CORD_OVERLAP[r.content_overlap])),
          h("td", { class: "num" }, r.n_masked ? String(r.n_masked) : ""), h("td", null, r.train_eligible ? pillCls("ok", "사용") : ""),
          h("td", { class: "num" }, r.width + "×" + r.height),
        ])), "small", "tall"),
      pager("#/cord", query, res, page),
      h("p", { class: "note" }, "행을 누르면 사진·정답·모델별 예측 비교. 평가 결과 요약은 ", h("a", { href: "#/cordeval" }, "CORD 평가"), " 페이지에 있습니다.")),
    ]);
  }
  function cordCell(cell) {
    const [icon, meaning] = CORD_STATE[cell.state] || ["", cell.state];
    const v = cell.value;
    return h("td", { class: "cc st-" + cell.state, title: meaning },
      icon ? h("span", { class: "si", "aria-label": meaning }, icon) : null,
      h("span", { class: "raw" }, v === null || v === undefined ? (cell.state === "missing" ? "(없음)" : "") : v === "" ? '""' : typeof v === "string" ? v : JSON.stringify(v)));
  }
  async function pageCordDoc(view, segs) {
    const rid = segs[0];
    if (!CORD_ID_RE.test(rid)) {
      add(view, [pageHead("CORD 영수증"), card("잘못된 주소", h("p", null, "ID 형식이 맞지 않습니다."), h("a", { href: lastCordList }, "목록으로"))]);
      return;
    }
    await status();
    const d = await api("/api/cord/doc/" + rid);
    const m = d.meta, integ = d.integrity || {};
    const imgUrl = "/api/cord/image/" + rid;
    const figure = imageFigure(imgUrl, rid + " 영수증 사진", integ.image !== null, integ.image !== null ? "이미지 불러오는 중…" : "로컬 이미지 없음");
    const runs = d.runs || [];
    const overlap = m.content_dup_of_heldout ? "dup_excluded" : m.content_seen_in_train ? "seen_in_train" : "none";
    const summaryRows = runs.map((r) => {
      const sc = r.score;
      return h("tr", null, h("td", null, h("span", { class: "sw " + ((CORD_ARMS[r.label] || {}).cls || "") }), " ", h("b", null, r.label), h("div", { class: "sub mono" }, r.run_id)),
        h("td", null, r.status === "ok" ? (r.strict_json ? pillCls("ok", "JSON") : pillCls("idle", "펜스 제거 후")) : pillCls("bad", r.status)),
        h("td", { class: "num" }, sc ? sc.strict[0] + "/" + sc.strict[1] : "—"), h("td", { class: "num" }, sc ? sc.loose[0] + "/" + sc.loose[1] : "—"),
        h("td", { class: "num" }, sc ? String(sc.absent_filled) : "—"), h("td", { class: "num" }, sc ? sc.pred_items + " / " + sc.gold_items : "—"),
        h("td", { class: "num" }, txt(r.generated_tokens)), h("td", { class: "num" }, r.latency_s ? fmt(r.latency_s, 1) + "s" : "—"));
    });
    const slotTable = d.slots.length ? table(["#", "필드", "정답"].concat(runs.map((r) => h("span", null, h("span", { class: "sw " + ((CORD_ARMS[r.label] || {}).cls || "") }), " ", r.label))),
      d.slots.map((row) => h("tr", { class: row.in_gold ? (row.kind === "doc" ? "docrow" : null) : "extra" },
        h("td", { class: "mono" }, row.kind === "doc" ? "문서" : row.index), h("td", { class: "mono" }, (row.kind === "sub" ? "└ " : "") + row.field),
        h("td", { class: "raw" + (row.masked ? " masked" : "") }, row.masked ? "채점 제외" : row.gold === null ? h("span", { class: "sub" }, row.in_gold ? "(미인쇄)" : "(정답에 없는 행)") : row.gold),
        row.cells.map(cordCell))), "small cordslots") : h("p", { class: "err" }, "정답을 표시할 수 없습니다.");
    add(view, [
      h("a", { class: "back", href: lastCordList }, "← CORD 영수증 목록"),
      pageHead(rid, m.split + " · CORD " + m.cord_split + " #" + m.cord_image_id + " · 품목 " + m.n_items + " · 하위 품목 " + m.n_sub_items),
      h("div", { class: "cols detail" },
        h("section", { class: "card sticky" }, h("div", { class: "cardhead" }, h("h2", null, "영수증 사진"), h("span", { class: "hint" }, "모델 입력")), figure,
          h("p", { class: "note" }, "클릭하면 원본 크기 토글 · ", h("a", { href: imgUrl, target: "_blank", rel: "noopener noreferrer" }, "새 탭에서 열기"),
            " · ", m.width + "×" + m.height, " · sha256 ", mono(short(m.image_sha256, 16)), " · CC BY 4.0")),
        h("div", { class: "stackv" },
          runs.length ? cardH("모델별 결과 (이 문서)", "펜스 하나만 벗긴 출력 · 사전 고정 채점기",
            table(["arm", "출력", ["strict", "num"], ["형식 무시", "num"], ["채움", "num"], ["행 (예측/정답)", "num"], ["토큰", "num"], ["지연", "num"]], summaryRows, "small"))
            : card("모델별 결과", h("p", null, pill("not_run"), m.split === "test" ? " CORD test는 설정 동결 뒤 한 번만 실행합니다 — 아직 예측이 없습니다." : m.split === "train" ? " train 문서는 평가하지 않습니다." : " 이 split의 실행 기록이 없습니다.")),
          h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "정답 대 예측 — 칸별"), h("span", { class: "tag gold" }, "정답은 평가 데이터 · 모델 입력 아님")),
            h("div", { class: "keyrow" }, Object.entries(CORD_STATE).filter(([k]) => CORD_STATE[k][0]).map(([k, [icon, meaning]]) => h("span", { class: "cc st-" + k }, h("span", { class: "si" }, icon), " " + meaning))),
            slotTable,
            h("p", { class: "note" }, "위치 기준 채점입니다: 행 하나를 빠뜨리거나 더하면 그 뒤 행이 모두 밀립니다(순서 무관 F1이 이를 보완). 회색 행은 정답에 없는 행을 모델이 만든 경우입니다.")),
          runs.length ? details("모델 원문 출력", runs.map((r) => [h("h3", null, r.label + " · " + r.run_id + (r.finish_reason ? " · " + r.finish_reason : "")), h("pre", { class: "rawout" }, txt(r.raw_response))])) : null,
          cardH("manifest 메타데이터·무결성", null, kv([
            ["정답 / 이미지 sha256", h("span", null, yesNo(integ.gold, "정답 일치", "정답 불일치"), " ", yesNo(integ.image, "이미지 일치", "이미지 불일치"))],
            ["split (CORD split)", m.split + " (" + m.cord_split + ")"],
            ["학습 사용", m.train_eligible ? pillCls("ok", "사용") : "아니오"],
            ["정답 겹침", CORD_OVERLAP[overlap]],
            ["채점 제외 필드", (m.masked || []).length ? h("span", { class: "mono" }, m.masked.join(", ")) : "없음"],
            ["gold_sha256", mono(short(m.gold_sha256, 24))],
          ])))),
    ]);
  }

  // ---- serving
  async function pageServing(view) {
    const s = await status();
    const sv = s.serving || {}, ho = s.handoff || {};
    const bench = sv.hf_peft_nf4_local, probe = sv.hf_cancel_probe;
    const t07 = (s.tasks || []).find((t) => t.id === "T07");
    const arms = bench ? Object.keys(bench.arms || {}) : [];
    const m1c1 = bench && bench.arms.m1 && bench.arms.m1.bench ? bench.arms.m1.bench["1"] : null;
    const allSame = arms.length > 0 && arms.every((a) => bench.arms[a].identical_raw_rate === 1);
    const rows = [];
    for (const a of arms) for (const [c, b] of Object.entries(bench.arms[a].bench || {})) {
      rows.push(h("tr", null, h("td", null, h("span", { class: "sw " + (ARMS[a] || {}).cls }), " ", runName(a)), h("td", { class: "num" }, c),
        h("td", { class: "num" }, String(b.requests)), h("td", { class: "num" }, b.failures ? h("b", null, String(b.failures)) : "0"),
        h("td", { class: "num" }, fmt(b.docs_per_min, 2)), h("td", { class: "num" }, fmt(b.p50_s, 1) + "s"), h("td", { class: "num" }, fmt(b.p95_s, 1) + "s"),
        h("td", { class: "num" }, String(b.gpu_mem_mb_max) + " MB")));
    }
    // re-measurements that score every answer and record HTTP codes (own dev with M1 v1, CORD dev with M1-cord)
    const SCORED = [["hf_peft_nf4_local_v2", "자체 dev · M1 v1"], ["hf_peft_nf4_local_sustained", "자체 dev · M1 v1 · 5분"],
      ["hf_peft_nf4_local_cord", "CORD dev · M1-cord"], ["hf_peft_nf4_local_cord_sustained", "CORD dev · M1-cord · 5분"],
      ["hf_multi_lora_trade", "어댑터 2개 서버 · 자체 dev 24장 · M1 v1"], ["hf_multi_lora_cord", "어댑터 2개 서버 · CORD dev 100장 · M1-cord"],
      ["hf_multi_lora_cord_sustained", "어댑터 2개 서버 · CORD dev · M1-cord · 5분"]];
    const scoredRows = [], parity = [];
    for (const [key, name] of SCORED) {
      const r = sv[key], m = r && r.arms && r.arms.m1;
      if (!m) continue;
      if (m.identical_raw_rate !== undefined && !key.endsWith("_sustained")) parity.push(name + ": 서버 원문이 오프라인 평가(" + ((r.offline_runs || {}).m1 || "m1_dev_v1") + ")와 " +
        fmt(m.identical_raw_rate * 100, 0) + "% 동일 (정확도 서버 " + fmt(m.server_field_accuracy) + " · 오프라인 " + fmt(m.offline_hf_field_accuracy_same_docs) + ")");
      for (const [c, b] of Object.entries(m.bench || {})) {
        const codes = Object.entries(b.status_codes || {}).map(([k, v]) => k + "×" + v).join(" ");
        scoredRows.push(h("tr", null, h("td", null, name), h("td", { class: "num" }, c), h("td", { class: "num" }, String(b.requests)), h("td", null, codes),
          h("td", { class: "num" }, fmt(b.field_accuracy)), h("td", { class: "num" }, fmt((b.identical_to_concurrency1_rate || 0) * 100, 0) + "%"),
          h("td", { class: "num" }, fmt(b.docs_per_min, 2)), h("td", { class: "num" }, fmt(b.p50_s, 1) + "s / " + fmt(b.p95_s, 1) + "s")));
      }
    }
    add(view, [
      pageHead("서빙", "Transformers + PEFT 서버(로컬 RTX 4070 Ti SUPER, 127.0.0.1) 실측", "reports/serving/*.json"),
      ho["vLLM 서빙"] ? banner("vLLM: " + recordedStatus(ho["vLLM 서빙"]) + (s.handoff_decision ? " — 사용자 결정: " + clean(s.handoff_decision) : "")) : t07 ? banner(t07.evidence) : null,
      statusErrors(s),
      bench ? h("div", { class: "kpis" },
        kpi("서버 = 오프라인 출력", allSame ? "100" : arms.map((a) => fmt(bench.arms[a].identical_raw_rate * 100, 0)).join("/"), "%", "같은 " + (bench.docs || []).length + "문서 원문 출력 일치 (" + arms.map(runName).join("·") + ")", allSame ? "ok" : "warn"),
        m1c1 ? kpi("M1 지연 p50 · 동시 1", fmt(m1c1.p50_s, 1), "s", "p95 " + fmt(m1c1.p95_s, 1) + "s · 요청 " + m1c1.requests + "건", "run") : null,
        m1c1 ? kpi("M1 처리량 · 동시 1", fmt(m1c1.docs_per_min, 2), "문서/분", "GPU 1개, 배치 1 (동시 생성 없음)", "run") : null,
        probe ? kpi("타임아웃 취소", String(probe.timeout_cancel_test.http_status), "", "제한 " + probe.timeout_cancel_test.request_timeout_s + "s · GPU " + fmt(probe.timeout_cancel_test.gpu_seconds, 2) + "s 후 중단", "ok") : null)
        : card("벤치마크", h("p", null, pill("not_run"), " reports/serving/hf_peft_nf4_local.json 없음")),
      bench ? h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "동시성별 지연·처리량"), h("span", { class: "hint" }, "최대 토큰 " + bench.max_tokens + " · warmup " + bench.warmups)),
        table(["arm", ["동시 요청", "num"], ["요청", "num"], ["실패", "num"], ["문서/분", "num"], ["p50", "num"], ["p95", "num"], ["GPU 메모리 최대", "num"]], rows, "small"),
        h("p", { class: "note" }, "서버는 GPU 작업을 한 번에 하나만 실행하고 대기열을 2개로 제한해 넘치는 요청을 429로 거절하도록 만들어져 있습니다. 이 벤치는 상태 코드를 기록하지 않았고, 상태 코드를 기록한 재측정(reports/serving/hf_peft_nf4_local_v2.json)에서 동시 4의 실패 7건은 모두 429로 확인됐습니다. 같은 재측정의 5분 지속 부하(동시 2)는 25건 모두 200, 정확도 0.943입니다. 문서/분·p50·p95는 성공한 요청만으로 계산했으므로 동시 4 행은 성공 3건 기준입니다. ", clean(bench.note))) : null,
      scoredRows.length ? h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "모든 답 채점 재측정"),
        h("span", { class: "hint" }, "답마다 채점 · HTTP 상태 코드 · 동시 1과 원문 비교 · 잘림 기록")),
        table(["측정", ["동시", "num"], ["요청", "num"], "HTTP", ["정확도", "num"], ["동시 1과 동일", "num"], ["문서/분", "num"], ["p50 / p95", "num"]], scoredRows, "small"),
        h("p", { class: "note" }, parity.join(" · "), parity.length ? ". " : "", "429는 대기열(2개)이 찬 요청을 설계대로 거절한 것입니다. CORD 영수증은 출력이 짧아 자체 인보이스보다 처리량이 높습니다.")) : null,
      h("div", { class: "cols" },
        probe ? cardH("취소·대기열 프로브", probe.measured_at, kv([
          ["요청 타임아웃", probe.timeout_cancel_test.request_timeout_s + "s → HTTP " + probe.timeout_cancel_test.http_status + " (경과 " + probe.timeout_cancel_test.wall_s + "s)"],
          ["GPU 사용 시간", fmt(probe.timeout_cancel_test.gpu_seconds, 3) + "s — 마감 시각에 생성 중단"],
          ["직후 상태", "busy " + probe.timeout_cancel_test.health_immediately_after.busy + " · 대기 " + probe.timeout_cancel_test.health_immediately_after.queued],
          ["정상 M1 요청", "HTTP " + probe.normal_m1_request.http_status + " · " + probe.normal_m1_request.finish_reason + " · " + fmt(probe.normal_m1_request.gpu_seconds, 2) + "s"],
          ["동시 " + probe.bounded_queue_test.concurrent_requests + "건", h("span", { class: "chips" }, probe.bounded_queue_test.status_codes.map((c) => pillCls(c === 200 ? "ok" : "warn", String(c))))],
          ["결론", probe.bounded_queue_test.conclusion],
        ])) : null,
        bench ? cardH("출력 동일성 (서버 vs 오프라인 HF)", "같은 문서·같은 설정", kv(arms.map((a) => [runName(a),
          "원문 일치 " + fmt(bench.arms[a].identical_raw_rate * 100, 0) + "% · 필드 정확도 서버 " + fmt(bench.arms[a].server_field_accuracy) + " / 오프라인 " + fmt(bench.arms[a].offline_hf_field_accuracy_same_docs)])),
          h("p", { class: "note" }, "서빙 경로가 평가 경로와 같은 출력을 내는지 확인한 값입니다(문서 " + (bench.docs || []).length + "건).")) : null),
    ]);
  }

  // ---- runpod / cloud cost
  async function pageRunpod(view) {
    const s = await status();
    const hw = s.hardware || {}, ap = s.approval || {}, ho = s.handoff || {};
    const total = hw.prepaid_balance_usd_user_reported || 0;
    const seg = (cls, v, label) => h("i", { class: cls, width: total ? (100 * v / total).toFixed(0) + "%" : "0%" }, label + " $" + v);
    const apPairs = Object.entries(ap).map(([k, v]) => [h("span", { class: "mono" }, k),
      v === "null" ? pillCls("idle", "미확인 (null)") : v === "false" ? h("span", { class: "mono" }, "false") : v === "true" ? pillCls("ok", "true") : h("span", { class: "raw" }, v)]);
    const unused = /^none/.test(ho.active_paid_resources_from_this_project || "");
    add(view, [
      pageHead("클라우드·비용", "RunPod 1-GPU 계획 · 승인 양식 · 실제 사용 기록", "reports/RUNPOD_APPROVAL.md · configs/project.yaml"),
      ho.RunPod ? banner("RunPod: " + clean(ho.RunPod), "info") : null,
      s.handoff_decision ? banner("사용자 결정: " + clean(s.handoff_decision), "info") : null,
      banner("유료 리소스 생성·재시작·변경은 실제 콘솔 견적을 사용자가 승인한 뒤에만 합니다. 예산 계산기는 과금 차단 장치가 아니며, Python을 멈춰도 Pod 과금은 멈추지 않습니다."),
      statusErrors(s),
      h("div", { class: "kpis" },
        kpi("이 프로젝트의 유료 리소스", unused ? "없음" : "확인 필요", "", clean(ho.active_paid_resources_from_this_project) || "기록 없음", unused ? "ok" : "warn"),
        kpi("승인 상태", ap.approved === "true" ? "승인됨" : "승인 없음", "", "실제 견적 승인 양식 기준", ap.approved === "true" ? "ok" : "idle"),
        kpi("계획 예산", "$" + txt(hw.gpu_compute_budget_usd), "+ $" + txt(hw.storage_and_shutdown_budget_usd), "GPU + 저장·정리, 여유 $" + txt(hw.reserve_usd) + " (미사용)", "idle")),
      h("div", { class: "cols" },
        cardH("계획 예산 배분", "사용자 보고 잔액 약 $" + txt(total) + " · 계정 잔액 미검증",
          total ? h("div", { class: "stack" }, seg("gpu", hw.gpu_compute_budget_usd, "GPU"), seg("oth", hw.storage_and_shutdown_budget_usd, "기타"), seg("res", hw.reserve_usd, "여유")) : null,
          kv([["동시 유료 Pod 상한", hw.max_simultaneous_paid_pods],
            ["soft stop", hw.spend_soft_stop_usd !== undefined ? "$" + hw.spend_soft_stop_usd : null], ["자동 충전 허용", String(hw.auto_top_up_authorized)],
            ["Full SSH 필요", String(hw.full_ssh_required)], ["콘솔 GPU 단가 (config)", hw.actual_console_gpu_rate_usd_per_hour === null ? "미확인" : hw.actual_console_gpu_rate_usd_per_hour],
            ["선호 GPU", hw.preferred_gpu], ["제안 디스크", "container " + txt(hw.container_disk_gb_proposed) + "GB · volume " + txt(hw.volume_disk_gb_proposed) + "GB"]])),
        cardH("이번 실행 승인 양식", "원문 값", apPairs.length ? kv(apPairs) : h("p", null, "RUNPOD_APPROVAL.md를 읽지 못했습니다."))),
    ]);
  }

  // ---- tests
  async function pageTests(view) {
    const s = await status();
    const j = s.junit;
    const passed = j ? j.tests - j.failures - j.errors - j.skipped : 0;
    add(view, [
      pageHead("테스트", "CPU 기능 테스트(application_cpu_test) — 모델·GPU 결과가 아닙니다", "artifacts/dashboard/pytest_junit.xml"),
      j ? h("div", { class: "kpis" },
        kpi("통과", String(passed), "/ " + j.tests, "기록 " + j.mtime, j.failures || j.errors ? "warn" : "ok", passed / Math.max(1, j.tests)),
        kpi("실패 · 오류", String(j.failures + j.errors), "", j.failures + j.errors ? "아래 실패 파일 참고" : "없음", j.failures + j.errors ? "bad" : "ok"),
        kpi("건너뜀", String(j.skipped), "", "로컬 데이터가 없을 때 건너뛰는 테스트", "idle"),
        kpi("소요 시간", fmt(j.time, 1), "s", "pytest 전체", "idle"))
        : card("pytest 요약", h("p", null, pill("not_run"), " junit 기록이 없습니다.")),
      j ? h("div", { class: "cols wide-left" },
        cardH("파일별 테스트 수", Object.keys(j.by_file || {}).length + "개 파일", bars(j.by_file),
          Object.keys(j.failed_by_file || {}).length ? [h("h3", null, "실패한 파일"), bars(j.failed_by_file)] : null),
        cardH("다시 실행하는 방법", null, h("p", null, h("code", null, ".venv/Scripts/python.exe -m invoiceguard.dashboard --run-tests")),
          h("p", null, "또는 서버 시작 시 ", h("code", null, "-m invoiceguard.dashboard_server --run-tests")),
          h("p", { class: "sub" }, "대시보드는 읽기 전용이라 화면에서 테스트를 실행하지 않습니다."))) : null,
    ]);
  }

  // ---- review API (T06)
  const STEP_KO = { create_po: "발주서 등록", upload: "인보이스 이미지 업로드", export_before_approval: "승인 전 export 시도",
    extract_live: "실시간 VLM 추출 + 대사", approve: "사람 승인", export_json: "승인본 export (JSON)" };
  const ENDPOINTS = [["get", "/health"], ["post", "/api/purchase-orders"], ["post", "/api/cases"], ["post", "/api/cases/{case_id}/extract"],
    ["get", "/api/cases/{case_id}"], ["get", "/api/cases/{case_id}/image"], ["put", "/api/cases/{case_id}/review"],
    ["post", "/api/cases/{case_id}/approve"], ["post", "/api/cases/{case_id}/reject"], ["get", "/api/cases/{case_id}/export"]];
  async function pageReview(view) {
    const s = await status();
    const t06 = (s.tasks || []).find((t) => t.id === "T06");
    const demo = (s.serving || {}).live_e2e_demo;
    add(view, [
      pageHead("검수 API", "업로드 → 추출 → 수정·승인 → 승인본 export (FastAPI + SQLite)", "src/invoiceguard/app/"),
      banner("검수용 화면(UI)은 아직 없습니다. 이 대시보드는 읽기 전용이며 검수 API를 호출하지 않습니다.", "info"),
      t06 ? cardH("T06 상태", t06.where, h("div", null, pill(t06.status), statusExtra(t06.status) ? h("span", { class: "sub" }, " " + statusExtra(t06.status)) : null), h("p", { class: "note" }, t06.evidence)) : null,
      h("div", { class: "cols" },
        demo ? cardH("라이브 E2E 시연 기록", demo.doc_id + " · " + demo.scenario,
          h("ol", { class: "timeline" }, (demo.steps || []).map((st) => {
            const [name, code, ...rest] = st;
            return h("li", { class: Number(code) >= 400 ? "is-warn" : null },
              h("div", { class: "tt" }, (STEP_KO[name] || name) + " · HTTP " + code),
              h("div", { class: "td" }, [name === "export_before_approval" && Number(code) === 409 ? "승인 전이라 거절 (의도된 동작)" : null, rest.map((x) => (Array.isArray(x) ? x.join(", ") : String(x))).join(" · ")].filter(Boolean).join(" — ")));
          })),
          demo.run ? h("p", { class: "note" }, "extractor ", mono(demo.run.extractor_mode), " · model ", mono(demo.run.model_label), " · ", fmt(demo.run.latency_s, 1), "s · 추출 = 정답 행 ", demo.extraction_equals_gold_rows ? "일치" : "불일치") : null)
          : card("라이브 E2E 시연", h("p", null, pill("not_run"), " reports/serving/live_e2e_demo.json 없음")),
        cardH("구현된 엔드포인트", "src/invoiceguard/app/api.py",
          h("ul", { class: "endpoints" }, ENDPOINTS.map(([m, p]) => h("li", null, h("span", { class: "m " + m }, m.toUpperCase()), h("code", null, p)))),
          h("p", { class: "note" }, "늦게 도착한 추론은 최신 수정·승인을 덮어쓰지 않습니다(버전 CAS). 승인 시 불변 스냅샷을 만들고 export는 승인본만 내보냅니다."))),
    ]);
  }

  // ------------------------------------------------------------------ router
  const PAGES = { overview: pageOverview, progress: pageProgress, public: pagePublic, trade: pageTrade, splits: pageSplits,
    model: pageModel, serving: pageServing, runpod: pageRunpod, tests: pageTests, review: pageReview, cord: pageCord, cordeval: pageCordEval };
  const PAGE_META = { overview: ["요약", "개요"], progress: ["요약", "진행 단계·게이트"], public: ["데이터", "공개 데이터"], trade: ["데이터", "자체 Invoice–PO"],
    splits: ["데이터", "분할·manifest"], cord: ["데이터", "CORD 영수증"], cordeval: ["모델·서빙", "CORD 평가"], model: ["모델·서빙", "모델·평가"], serving: ["모델·서빙", "서빙"], review: ["운영", "검수 API"],
    tests: ["운영", "테스트"], runpod: ["운영", "클라우드·비용"] };
  function parseHash() {
    const raw = (location.hash || "").replace(/^#/, "") || "/overview";
    const qi = raw.indexOf("?");
    const path = qi >= 0 ? raw.slice(0, qi) : raw;
    const segs = path.split("/").filter(Boolean).map((x) => { try { return decodeURIComponent(x); } catch (e) { return ""; } });
    return { segs, query: new URLSearchParams(qi >= 0 ? raw.slice(qi + 1) : "") };
  }
  function setNavOpen(open) {
    sidebar.classList.toggle("open", open);
    backdrop.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
  }
  function setNav(page, segs) {
    for (const a of document.querySelectorAll("nav a")) {
      const on = a.dataset.page === page;
      a.classList.toggle("active", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    }
    const [group, title] = PAGE_META[page];
    crumbs.replaceChildren();
    add(crumbs, [h("span", null, group), h("span", { class: "sep" }, "/"), h("b", null, title),
      segs.length ? [h("span", { class: "sep" }, "/"), h("span", { class: "mono" }, segs[0])] : null]);
    document.title = title + " · InvoiceGuard 관리자";
    setNavOpen(false);
  }
  async function route() {
    const token = ++routeToken;
    hideTip();
    const { segs, query } = parseHash();
    const name = PAGES[segs[0]] ? segs[0] : "overview";
    setNav(name, segs.slice(1));
    const timer = setTimeout(() => {
      if (token === routeToken) main.replaceChildren(h("div", { class: "skeleton", "aria-hidden": "true" }, h("div", { class: "sk tall" }), h("div", { class: "sk" }), h("div", { class: "sk" })));
    }, 150);
    const view = h("div", { class: "view" });
    try {
      await PAGES[name](view, segs.slice(1), query);
    } catch (e) {
      view.replaceChildren(errorBox(e));
    }
    clearTimeout(timer);
    if (token !== routeToken) return;
    main.replaceChildren(view);
    window.scrollTo(0, 0);
  }
  document.querySelector(".skip").addEventListener("click", (e) => { e.preventDefault(); main.focus(); });
  toggle.addEventListener("click", () => setNavOpen(!sidebar.classList.contains("open")));
  backdrop.addEventListener("click", () => setNavOpen(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { setNavOpen(false); hideTip(); } });
  document.getElementById("refresh").addEventListener("click", route);
  window.addEventListener("scroll", hideTip, { passive: true });

  // ---- theme: dark by default; the light choice is remembered per browser
  const themeBtn = document.getElementById("themetoggle");
  const themeLabel = document.getElementById("themelabel");
  const currentTheme = () => (document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark");
  function paintThemeButton() {
    const dark = currentTheme() === "dark";
    themeLabel.textContent = dark ? "라이트 모드" : "다크 모드";
    themeBtn.setAttribute("aria-label", dark ? "라이트 모드로 전환" : "다크 모드로 전환");
  }
  themeBtn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      if (next === "light") window.localStorage.setItem("ig-theme", "light");
      else window.localStorage.removeItem("ig-theme");
    } catch (e) { /* not remembered, still applied */ }
    paintThemeButton();
  });
  paintThemeButton();
  window.addEventListener("hashchange", route);
  route();
})();
