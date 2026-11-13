// InvoiceGuard-PO read-only admin dashboard (Korean UI).
// Every value from the API is inserted as text (textContent / text nodes) — never parsed as markup.
// The page only talks to its own origin (same-origin JSON/PNG endpoints); no CDN, no external fetch.
"use strict";
(function () {
  const main = document.getElementById("main");
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("navtoggle");
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
  function pill(status, label) {
    const cls = LABELS.status_class[status] || "idle";
    return h("span", { class: "pill " + cls }, label || LABELS.status_ko[status] || txt(status));
  }
  const pillCls = (cls, label) => h("span", { class: "pill " + cls }, label);
  const yesNo = (b, yes, no) => (b === true ? pillCls("ok", yes || "예") : b === false ? pillCls("bad", no || "아니오") : pillCls("warn", "미확인"));
  function card(title, ...children) {
    return h("section", { class: "card" }, title ? h("h2", null, title) : null, ...children);
  }
  function kv(pairs) {
    return h("table", { class: "kv" }, pairs.filter(Boolean).map(([k, v]) => h("tr", null, h("th", null, k), h("td", null, v instanceof Node ? v : txt(v)))));
  }
  function table(headers, rows, cls) {
    return h("div", { class: "tablewrap" }, h("table", { class: "grid " + (cls || "") },
      h("thead", null, h("tr", null, headers.map((x) => h("th", null, x)))),
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
  function pageHead(title, meta) {
    return h("div", { class: "pagehead" }, h("h1", null, title), meta ? h("span", { class: "meta" }, meta) : null);
  }

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
    return card("오류", h("p", { class: "err" }, "불러오지 못했습니다: ", mono(e.message), e.detail ? [" (", mono(e.detail), ")"] : null),
      h("p", { class: "sub" }, "서버가 실행 중인지, 주소의 ID·필터가 올바른지 확인하세요."));
  }
  function statusErrors(s) {
    const keys = Object.keys(s.errors || {});
    return keys.length ? banner("일부 기록을 읽지 못했습니다(동시 편집 중일 수 있음): " + keys.map((k) => k + " — " + s.errors[k]).join(" / "), "bad") : null;
  }

  // ------------------------------------------------------------------ pages
  async function pageOverview(view) {
    const s = await status();
    const tasks = s.tasks || [], gates = s.gates || [], ho = s.handoff || {}, ap = s.approval || {};
    const done = tasks.filter((t) => t.status === "passed_with_evidence").length;
    const junit = s.junit;
    const pm = s.public_manifest, tm = s.trade_manifest, pp = s.public_profile;
    const resultsStatus = (s.results && s.results.status) || "not_run";
    const kpis = [
      ["진행 단계", done + "/" + tasks.length, "증거로 통과한 T단계"],
      ["인수 게이트", gates.filter((g) => g.status === "pass").length + "/" + gates.length, "G0–G7 중 통과"],
      ["CPU 테스트", junit ? (junit.tests - junit.failures - junit.errors) + "/" + junit.tests : "—", junit ? "pytest 통과 · " + junit.mtime : "junit 기록 없음 (테스트 페이지 참고)"],
      ["클라우드 지출 기록", ho.actual_spend_from_this_package ? ho.actual_spend_from_this_package.split(" ")[0] : "미확인", "SESSION_HANDOFF 기록값 · 계정 잔액 미검증"],
      ["공개 데이터", pp ? pp.counts.rows_actual.toLocaleString() + "장" : "—", pp ? "base " + pp.counts.base_documents_actual + " · 합성 영어 · SKU 정답 없음" : "프로파일 없음"],
      ["자체 Invoice–PO", tm ? tm.documents + "건" : "—", tm ? "train/dev/test " + ["train", "dev", "test"].map((k) => tm.by_split[k] || 0).join("/") + " · 합성·가상 회사" : "manifest 없음"],
      ["모델 M0 / M1", resultsStatus === "not_run" ? "미실행" : resultsStatus, "결과 파일 상태 (수치 없음)"],
      ["RunPod 승인", ap.approved === "true" ? "승인됨" : "승인 없음", "활성 Pod: " + txt(ho.active_pods_from_this_package)],
    ];
    const ld = s.local_data || {};
    add(view, [
      pageHead("개요", "읽기 전용 · reports/, manifests/, configs/ 기록 기준"),
      banner("이 화면은 저장소에 기록된 증거만 보여줍니다. 기록에 없는 GPU·과금·모델 결과는 미실행/미확인으로 표시하며 추정치를 만들지 않습니다. 공개 데이터와 자체 Invoice–PO는 모두 합성 자료입니다."),
      statusErrors(s),
      h("div", { class: "kpis" }, kpis.map(([a, b, c]) => h("div", { class: "kpi" }, h("div", { class: "kl" }, a), h("div", { class: "kn" }, b), h("div", { class: "ks" }, c)))),
      h("div", { class: "cols" },
        card("현재 작업 (SESSION_HANDOFF)", kv([
          ["현재 단계", ho.current_task], ["마지막 완료", ho.last_completed_implementation_task],
          ["프로필", ho.current_profile], ["과금 승인", ho.billing_approval],
          ["이 프로젝트의 활성 Pod", ho.active_pods_from_this_package], ["계정 전체 과금 리소스", ho.actual_account_active_resources],
          ["로컬 프로세스", ho.running_local_processes],
        ])),
        card("로컬 데이터 상태", kv([
          ["공개 parquet", ld.public_parquet ? pillCls("ok", "있음") : pillCls("warn", "없음 — 이미지·정답 표시 불가")],
          ["자체 Invoice–PO 파일", ld.trade_files ? pillCls("ok", "있음") : pillCls("warn", "없음 — 이미지·정답·PO 표시 불가")],
          ["캐시된 공개 이미지", String(ld.public_cached_images || 0) + "장 (data/processed/public/cache/)"],
          ["공개 manifest", pm ? h("span", null, mono(short(pm.sha256, 16)), " · ", pm.frozen ? "동결됨" : "미동결") : "없음"],
          ["자체 manifest", tm ? h("span", null, mono(short(tm.sha256, 16)), " · ", tm.frozen ? "동결됨" : "미동결") : "없음"],
        ]))),
    ]);
  }

  async function pageProgress(view) {
    const s = await status();
    add(view, [
      pageHead("진행 단계·게이트", "reports/TASK_BOARD.md"),
      statusErrors(s),
      card("진행 단계 T00–T09", table(["ID", "작업 · 증거/차단 사유", "실행 위치", "상태"],
        (s.tasks || []).map((t) => h("tr", null, h("td", { class: "mono" }, t.id),
          h("td", null, t.name, h("div", { class: "sub" }, t.evidence)), h("td", null, t.where), h("td", null, pill(t.status)))))),
      card("인수 게이트 G0–G7 (docs/16)", h("ul", { class: "gates" }, (s.gates || []).map((g) => h("li", null,
        pill(g.status), h("b", { class: "mono" }, g.id), " ", g.name, g.detail ? h("div", { class: "sub" }, g.detail) : null)))),
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
  function filterBar(base, query, facets, defs, searchLabel) {
    const form = h("form", { class: "filters", onsubmit: (e) => { e.preventDefault(); go(); } });
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
    form.append(h("label", null, searchLabel, q), h("a", { class: "btn", href: base }, "초기화"));
    return form;
  }
  function pager(base, query, res, page) {
    const pages = Math.max(1, Math.ceil(res.total / PAGE_SIZE));
    const link = (n) => { const p = new URLSearchParams(query); p.set("page", String(n)); return base + "?" + p.toString(); };
    const start = res.total ? res.offset + 1 : 0, end = Math.min(res.total, res.offset + res.limit);
    return h("div", { class: "pager" },
      h("a", { class: "btn", href: link(page - 1), "aria-disabled": page <= 1 ? "true" : "false" }, "이전"),
      h("span", null, start + "–" + end + " / " + res.total + "건 · " + page + "/" + pages + "쪽"),
      h("a", { class: "btn", href: link(page + 1), "aria-disabled": page >= pages ? "true" : "false" }, "다음"));
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
      pageHead("공개 데이터", "InvoiceOCR-Synth · PUBLIC_CANONICAL · 이미지 1장 = (base, 품질)"),
      banner("공개 합성 영어 데이터입니다. SKU·단위·원문 인쇄 형식 정답은 없습니다. 정답(gold)은 평가·학습 라벨이며 모델 입력이 아닙니다.", "info"),
      card(null, filterBar("#/public", query, res.facets, [
        ["pool", "pool"], ["standard_role", "standard 역할"], ["mini_role", "mini 역할"], ["template", "템플릿"],
        ["quality", "품질"], ["eligible", "학습 가능", (v) => (v === "true" ? "가능" : "불가")],
      ], "base_id 검색"),
      table(["base_id", "품질", "템플릿", "pool", "standard", "mini", "학습", "품목", "채점/마스크 필드"],
        res.page.map((r) => rowLink("#/public/" + encodeURIComponent(r.base_id) + "/" + r.quality, [
          h("td", null, h("a", { class: "mono", href: "#/public/" + encodeURIComponent(r.base_id) + "/" + r.quality }, r.base_id)),
          h("td", null, r.quality), h("td", { class: "mono" }, r.template), h("td", null, r.pool),
          h("td", null, txt(r.standard_role)), h("td", null, txt(r.mini_role)),
          h("td", null, r.train_eligible ? pillCls("ok", "가능") : h("span", null, pillCls("idle", "불가"), h("div", { class: "sub mono" }, txt(r.train_ineligible_reason)))),
          h("td", { class: "num" }, String(r.n_items)), h("td", { class: "num" }, r.n_scored_fields + " / " + r.n_masked_fields),
        ])), "small"),
      pager("#/public", query, res, page)),
      pm ? h("p", { class: "sub" }, "manifest ", mono(short(pm.sha256, 16)), " · seed ", String(pm.seed), " · 행 클릭 시 이미지·정답·가시성 상세") : null,
    ]);
  }
  function visCell(value, vis, fieldStatus, isText) {
    const masked = vis && vis !== "visible_exact";
    return h("td", { class: masked ? "masked" : null },
      h("span", { class: "val " + (isText ? "raw" : "mono") }, txt(value)),
      masked ? h("div", null, h("span", { class: "vis " + (vis === "not_printed" || vis === "source_empty" ? "idle" : "warn") }, LABELS.visibility_ko[vis] || vis), h("code", { class: "vcode" }, vis)) : null,
      fieldStatus && fieldStatus !== "ok" ? h("div", { class: "sub" }, "라벨 상태: ", mono(fieldStatus)) : null);
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
    const figure = h("div", { class: "figure" }, h("div", { class: "ph" },
      current.image_cached ? "이미지 불러오는 중…" : "이미지 추출 중… 처음 한 번은 parquet에서 꺼내 캐시하므로 몇 초 걸릴 수 있습니다."));
    if (d.public_parquet_available || current.image_cached) {
      const img = h("img", { src: imgUrl, alt: baseId + " (" + quality + ") 문서 이미지", decoding: "async" });
      img.addEventListener("load", () => figure.replaceChildren(img));
      img.addEventListener("error", () => figure.replaceChildren(h("div", { class: "ph" }, "이미지를 불러오지 못했습니다 (로컬 원본 또는 해시 불일치 확인).")));
      img.addEventListener("click", () => figure.classList.toggle("zoom"));
    } else {
      figure.replaceChildren(h("div", { class: "ph" }, "로컬 parquet 없음 — 이미지 표시 불가"));
    }
    const g = d.gold;
    const FIELDS = [["description", "설명 (description)", true], ["quantity", "수량", false], ["unit_price", "단가", false], ["amount", "금액", false]];
    const goldTable = g.available
      ? table(["#"].concat(FIELDS.map((f) => f[1])), g.items.map((it) => h("tr", null, h("td", { class: "mono" }, String(it.row_index)),
        FIELDS.map(([f, , isText]) => visCell(it[f], it.visibility && it.visibility[f], it.field_status && it.field_status[f], isText)))))
      : h("p", { class: "err" }, "정답을 표시할 수 없습니다: ", mono(g.reason));
    add(view, [
      h("a", { href: lastPublicList }, "← 공개 데이터 목록"),
      pageHead(baseId, m.template + " · " + m.pool),
      h("div", { class: "tabs" }, d.qualities.map((q) => h("a", { href: "#/public/" + encodeURIComponent(baseId) + "/" + q.quality, class: q.quality === quality ? "active" : null },
        q.quality + (q.standard_role ? " · std:" + q.standard_role : "") + (q.mini_role ? " · mini:" + q.mini_role : "")))),
      h("div", { class: "cols detail" },
        card("문서 이미지 (모델 입력 후보)", figure, h("p", { class: "sub" }, "클릭하면 원본 크기 토글 · ", h("a", { href: imgUrl, target: "_blank", rel: "noopener noreferrer" }, "새 탭에서 열기"),
          " · sha256 ", mono(short(current.image_sha256, 16)))),
        h("div", { class: "view" },
          card(h("span", null, "정답 (gold) ", h("span", { class: "tag gold" }, "평가·학습 라벨 · 모델 입력 아님")),
            h("p", { class: "sub" }, "PUBLIC_CANONICAL 4개 필드. 빗금 칸은 렌더러 기준으로 이미지에 그대로 보이지 않아 채점·학습에서 마스크되는 필드입니다. 값은 원문 그대로이며 PO에 맞추지 않습니다."),
            goldTable,
            h("div", { class: "legend" }, Object.entries(LABELS.visibility_ko).map(([k, v]) => h("span", null, h("code", null, k), " ", v)))),
          card("manifest 메타데이터", kv([
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
      pageHead("자체 Invoice–PO", "TRADE_RAW · 합성·가상 회사 · 렌더러 문자열 그대로"),
      banner("자체 생성한 합성 문서입니다. 정답(gold)·발주서(PO)·시나리오 정보는 평가 데이터이며 모델 입력이 아닙니다.", "info"),
      card(null, filterBar("#/trade", query, res.facets, [
        ["split", "split"], ["template", "레이아웃"], ["scenario_type", "시나리오"], ["mini_role", "mini 역할"],
        ["injection", "주입 문구", (v) => (v === "true" ? "포함" : "없음")],
      ], "doc_id 검색"),
      table(["doc_id", "split", "레이아웃", "시나리오", "기대 코드", "행", "mini", "주입 문구"],
        res.page.map((r) => rowLink("#/trade/" + r.doc_id, [
          h("td", null, h("a", { class: "mono", href: "#/trade/" + r.doc_id }, r.doc_id)),
          h("td", null, r.split), h("td", { class: "mono" }, r.template), h("td", null, r.scenario_type),
          h("td", null, h("div", { class: "chips" }, (r.expected_codes || []).length ? r.expected_codes.map((c) => h("code", null, c)) : h("span", { class: "sub" }, "없음"))),
          h("td", { class: "num" }, String(r.n_rows)), h("td", null, txt(r.mini_role)),
          h("td", null, r.has_injection_text ? pillCls("warn", "포함") : ""),
        ])), "small"),
      pager("#/trade", query, res, page)),
      tm ? h("p", { class: "sub" }, "manifest ", mono(short(tm.sha256, 16)), " · ", tm.generator_version, " · 행 클릭 시 이미지·정답·PO·대사 결과") : null,
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
    const figure = h("div", { class: "figure" }, h("div", { class: "ph" }, "이미지 불러오는 중…"));
    if (integ.image !== null) {
      const img = h("img", { src: imgUrl, alt: docId + " 문서 이미지", decoding: "async" });
      img.addEventListener("load", () => figure.replaceChildren(img));
      img.addEventListener("error", () => figure.replaceChildren(h("div", { class: "ph" }, "이미지를 불러오지 못했습니다.")));
      img.addEventListener("click", () => figure.classList.toggle("zoom"));
    } else {
      figure.replaceChildren(h("div", { class: "ph" }, "로컬 이미지 없음"));
    }
    const o = d.oracle;
    const findings = o && !o.findings.length ? h("p", { class: "sub" }, "발견 사항 없음 (findings 0건)") : o ? table(["코드", "심각도", "행", "필드", "기대(PO 등)", "관측(인보이스)", "메시지"],
      o.findings.map((f) => h("tr", null, h("td", null, h("code", null, f.code)),
        h("td", null, pillCls(f.severity === "blocker" ? "bad" : "warn", f.severity === "blocker" ? "차단" : "경고")),
        h("td", { class: "mono" }, txt(f.row_index)), h("td", { class: "mono" }, txt(f.field)),
        h("td", { class: "raw" }, txt(f.expected)), h("td", { class: "raw" }, txt(f.observed)), h("td", null, f.message))), "small") : null;
    add(view, [
      h("a", { href: lastTradeList }, "← 자체 Invoice–PO 목록"),
      pageHead(docId, m.split + " · " + m.template + " · " + m.scenario_type),
      m.has_injection_text ? banner("이 문서 이미지에는 프롬프트 주입 문구가 들어 있습니다(견고성 테스트용). 화면에는 일반 텍스트로만 표시하며 어떤 지시도 실행하지 않습니다.") : null,
      h("div", { class: "cols detail" },
        card("문서 이미지 (모델 입력 후보)", figure, h("p", { class: "sub" }, "클릭하면 원본 크기 토글 · ", h("a", { href: imgUrl, target: "_blank", rel: "noopener noreferrer" }, "새 탭에서 열기"),
          " · ", m.width + "×" + m.height, " · sha256 ", mono(short(m.image_sha256, 16)))),
        h("div", { class: "view" },
          card(h("span", null, "정답 (gold, TRADE_RAW) ", h("span", { class: "tag gold" }, "평가 데이터 · 모델 입력 아님")),
            d.gold ? [kv(scalarPairs(d.gold, ["items"])), h("h3", null, "품목 (원문 문자열)"), itemsTable(d.gold.items, GOLD_ITEM_COLS)]
              : h("p", { class: "err" }, "로컬 정답 파일 없음")),
          card(h("span", null, "발주서 (PO) ", h("span", { class: "tag po" }, "대사 입력 · 모델 입력 아님")),
            d.po ? [kv(scalarPairs(d.po, ["items"])), h("h3", null, "발주 행"), itemsTable(d.po.items, PO_ITEM_COLS)]
              : h("p", { class: "err" }, "로컬 발주서 파일 없음")))),
      card("대사 결과 — 기대 코드 vs oracle", kv([
        ["기대 코드 (manifest)", h("div", { class: "chips" }, d.expected_codes.length ? d.expected_codes.map((c) => h("code", null, c)) : "없음")],
        ["oracle 코드", d.oracle_codes ? h("div", { class: "chips" }, d.oracle_codes.length ? d.oracle_codes.map((c) => h("code", null, c)) : "없음") : "미실행 (정답 파일 없음)"],
        ["일치", d.codes_match === null ? pillCls("warn", "미확인") : yesNo(d.codes_match, "일치", "불일치")],
        ["case_status", o ? mono(o.case_status) : "—"], ["reference_total_difference", o ? mono(o.reference_total_difference) : "—"],
      ]), h("p", { class: "sub" }, "oracle_fixture = 정답(gold)과 발주서로 규칙 엔진을 돌린 기준 결과입니다. 모델 예측 결과가 아닙니다."), findings),
      card("manifest 메타데이터·무결성", kv([
        ["gold / PO / 이미지 sha256", h("span", null, yesNo(integ.gold, "gold 일치", "gold 불일치"), yesNo(integ.po, "PO 일치", "PO 불일치"), yesNo(integ.image, "이미지 일치", "이미지 불일치"))],
        ["split / standard / mini", m.split + " / " + txt(m.standard_role) + " / " + txt(m.mini_role)],
        ["family_id", mono(m.family_id)], ["scenario_type / transaction_diff", m.scenario_type + " / " + String(m.transaction_diff)],
        ["render_check / quality", m.render_check + " / " + m.quality], ["fonts", m.font_regular + " · " + m.font_bold],
        ["generator / seed", m.generator_version + " / " + m.seed], ["origin / task", m.origin + " / " + m.task],
      ])),
    ]);
  }

  // ---- splits / manifests
  async function pageSplits(view) {
    const s = await status();
    const pm = s.public_manifest, tm = s.trade_manifest, pp = s.public_profile;
    const parts = [pageHead("분할·manifest", "manifests/*.summary.json · reports/data/public_profile.json"), statusErrors(s)];
    if (pm) {
      const roles = ["train", "dev", "dev_stress", "iid_final", "ood_final"];
      const prof = pm.profiles || {};
      const leakChecks = Object.entries(pm.checks || {}).filter(([k]) => k !== "pass");
      parts.push(card(h("span", null, "공개 InvoiceOCR-Synth ", h("span", { class: "tag" }, "PUBLIC_CANONICAL · 합성")),
        kv([["manifest", mono(pm.manifest)], ["sha256", mono(pm.sha256)], ["seed / revision", h("span", null, String(pm.seed), " / ", mono(short(pm.revision, 12)))],
          ["행 / base / group", pm.rows + " / " + pm.base_documents + " / " + pm.groups], ["누수 검사", yesNo(pm.checks && pm.checks.pass, "통과", "실패")],
          ["동결", pm.frozen ? pillCls("ok", "동결됨") : pillCls("warn", "미동결 — 프로필 선택 후 동결")]]),
        h("div", { class: "cols" },
          h("div", null, h("div", { class: "cap" }, "pool별 base 문서"), bars(pm.pool_base_docs)),
          h("div", null, h("div", { class: "cap" }, "마스크 사유 (학습 불가 base)"), bars(pm.ineligible_reasons))),
        h("h3", null, "standard / mini 역할 (이미지 행)"),
        table(["역할", "standard 이미지", "mini 이미지", "standard 채점 필드", "standard 마스크 필드", "mini 채점 필드", "mini 마스크 필드"],
          roles.map((r) => h("tr", null, h("td", null, r), ["standard", "mini"].map((p) => h("td", { class: "num" }, String(((prof[p] || {}).image_rows_by_role || {})[r] || 0))),
            ["standard", "mini"].map((p) => [h("td", { class: "num" }, String(((prof[p] || {}).scored_fields_by_role || {})[r] || 0)), h("td", { class: "num" }, String(((prof[p] || {}).masked_fields_by_role || {})[r] || 0))]))), "small"),
        h("h3", null, "템플릿별 학습 가능 base"), kv(Object.entries(pm.train_eligible_by_template || {}).map(([k, v]) => [k, v])),
        h("h3", null, "필드 가시성 (전체 base)"), bars(pm.field_status_counts_all_bases),
        leakChecks.length ? [h("h3", null, "검사 항목"), kv(leakChecks.map(([k, v]) => [k, h("span", { class: "raw" }, typeof v === "object" ? JSON.stringify(v) : String(v))]))] : null));
    } else parts.push(card("공개 manifest", h("p", null, "manifests/public_canonical_v1.summary.json 없음")));
    if (pp) {
      parts.push(card("공개 데이터 프로파일 (T01)", kv([["dataset / revision", h("span", null, pp.dataset_id, " @ ", mono(short(pp.revision, 12)))],
        ["license / origin", pp.license_tag + " / " + pp.origin], ["SKU 정답", pp.sku_labels_available ? "있음" : "없음"],
        ["자동 검사", h("span", null, Object.entries(pp.checks || {}).map(([k, v]) => h("span", null, yesNo(v.pass, "통과", "실패"), h("small", null, k), " ")))]]),
        h("div", { class: "cols" }, h("div", null, h("div", { class: "cap" }, "템플릿별 base 문서"), bars(pp.counts.templates_base_docs)),
          h("div", null, h("div", { class: "cap" }, "문서당 품목 수"), bars(pp.counts.items_per_doc)))));
    }
    if (tm) {
      const types = Object.keys(Object.values(tm.type_by_template || {})[0] || {});
      const rows = [];
      for (const [split, byType] of Object.entries(tm.type_by_template || {})) {
        const tpls = [...new Set(Object.values(byType).flatMap((v) => Object.keys(v)))].sort();
        for (const tpl of tpls) rows.push(h("tr", null, h("td", null, split), h("td", { class: "mono" }, tpl), types.map((t) => h("td", { class: "num" }, String((byType[t] || {})[tpl] || "·")))));
      }
      const leaks = (tm.checks && tm.checks.split_leaks) || {};
      parts.push(card(h("span", null, "자체 Invoice–PO ", h("span", { class: "tag" }, "TRADE_RAW · 합성·가상 회사")),
        kv([["manifest", mono(tm.manifest)], ["sha256", mono(tm.sha256)], ["문서", tm.documents + " (train/dev/test = " + ["train", "dev", "test"].map((k) => tm.by_split[k] || 0).join(" / ") + ")"],
          ["mini (train/dev/test)", ["train", "dev", "test"].map((k) => (tm.mini_by_split || {})[k] || 0).join(" / ")],
          ["렌더=정답 검사", yesNo(tm.checks && tm.checks.all_render_checks_pass, "통과", "실패")],
          ["레이아웃 holdout", yesNo(tm.checks && tm.checks.template_holdout_respected, "지켜짐", "위반")],
          ["split 누수", h("span", null, Object.entries(leaks).map(([k, v]) => h("span", null, (v || []).length ? pillCls("bad", k + " " + v.length) : pillCls("ok", k + " 0"))))],
          ["주입 문구 문서", String((tm.checks || {}).injection_text_docs)], ["동결", tm.frozen ? pillCls("ok", "동결됨") : pillCls("warn", "미동결")]]),
        h("h3", null, "split × 레이아웃 × 시나리오"), table(["split", "layout"].concat(types), rows, "small"),
        h("div", { class: "cols" }, h("div", null, h("div", { class: "cap" }, "문서당 행 수"), bars(tm.rows_per_doc)),
          h("div", null, h("div", { class: "cap" }, "글꼴"), bars(tm.fonts_used))),
        tm.note ? h("p", { class: "sub" }, tm.note) : null));
    } else parts.push(card("자체 manifest", h("p", null, "manifests/trade_raw_v1.summary.json 없음")));
    add(view, parts);
  }

  // ---- model / training
  async function pageModel(view) {
    const s = await status();
    const r = s.results || {}, ho = s.handoff || {};
    const cols = ["public IID final", "public OOD final", "trade final"];
    add(view, [
      pageHead("모델·학습", "M0 base vs M1 adapter · 동일 frozen manifest·NF4·프롬프트·생성 설정"),
      banner("측정된 결과 파일이 없으면 모든 칸은 미실행입니다. 이 페이지는 수치를 추정하거나 채우지 않습니다."),
      statusErrors(s),
      card("평가 매트릭스", table(["모델"].concat(cols), ["M0 base (NF4)", "M1 adapter (NF4)"].map((name) => h("tr", null, h("td", { class: "mono" }, name), cols.map(() => h("td", null, pill("not_run")))))),
        h("p", { class: "sub" }, "결과 파일 reports/RESULTS_TEMPLATE.json 상태: ", mono(r.status || "not_run"), " — 템플릿이며 측정값이 아닙니다.")),
      h("div", { class: "cols" },
        card("기록된 모델 상태", kv([
          ["model_revision / adapter_hash", ho["model_revision / adapter_hash"]], ["current_profile", ho.current_profile],
          ["base 로딩 정밀도", r.base_loading_precision], ["adapter 로딩 정밀도", r.adapter_loading_precision],
          ["model_revision", r.model_revision], ["adapter_sha256", r.adapter_sha256], ["gpu", r.gpu],
          ["경고", (r.warnings || []).join(" / ")],
        ])),
        card("로컬 스모크 기록 (reports/model/local_smoke*.json)", (s.local_smoke || []).length
          ? [h("p", { class: "sub" }, "파일 내용을 키/값 원문 그대로 보여줍니다. 대시보드는 해석·검증하지 않으며, 이는 frozen final 평가나 M0/M1 비교 결과가 아닙니다."),
            s.local_smoke.map((f) => [h("h3", { class: "mono" }, f.path),
              h("div", { class: "tablewrap" }, kv(f.pairs.map(([k, v]) => [h("span", { class: "mono" }, k), h("span", { class: "raw" }, v)])))])]
          : h("p", null, pill("not_run"), "파일 없음 — 로컬 스모크 기록이 아직 없습니다."))),
    ]);
  }

  // ---- runpod
  async function pageRunpod(view) {
    const s = await status();
    const hw = s.hardware || {}, ap = s.approval || {}, ho = s.handoff || {};
    const total = hw.prepaid_balance_usd_user_reported || 0;
    const seg = (cls, v, label) => h("i", { class: cls, width: total ? (100 * v / total).toFixed(0) + "%" : "0%" }, label + " $" + v);
    const apPairs = Object.entries(ap).map(([k, v]) => [h("span", { class: "mono" }, k),
      v === "null" ? pillCls("idle", "미확인 (null)") : v === "false" ? h("span", { class: "mono" }, "false") : v === "true" ? pillCls("ok", "true") : h("span", { class: "raw" }, v)]);
    add(view, [
      pageHead("RunPod 비용·승인", "reports/RUNPOD_APPROVAL.md · configs/project.yaml"),
      banner("유료 리소스 생성·재시작·변경은 실제 콘솔 견적을 사용자가 승인한 뒤에만 합니다. 예산 계산기는 과금 차단 장치가 아니며, Python을 멈춰도 Pod 과금은 멈추지 않습니다."),
      statusErrors(s),
      h("div", { class: "cols" },
        card("계획 예산 배분", total ? h("div", { class: "stack" }, seg("gpu", hw.gpu_compute_budget_usd, "GPU"), seg("oth", hw.storage_and_shutdown_budget_usd, "기타"), seg("res", hw.reserve_usd, "여유")) : null,
          h("p", { class: "sub" }, "사용자 보고 잔액 약 $" + txt(total) + " (계정 잔액 미검증)."),
          kv([["승인 상태", ap.approved === "true" ? pillCls("ok", "승인됨") : pillCls("warn", "승인 없음")],
            ["이 프로젝트의 활성 Pod", ho.active_pods_from_this_package], ["계정 전체 과금 리소스", ho.actual_account_active_resources],
            ["실제 지출 기록", ho.actual_spend_from_this_package], ["동시 유료 Pod 상한", hw.max_simultaneous_paid_pods],
            ["soft stop", hw.spend_soft_stop_usd !== undefined ? "$" + hw.spend_soft_stop_usd : null], ["자동 충전 허용", String(hw.auto_top_up_authorized)],
            ["Full SSH 필요", String(hw.full_ssh_required)], ["콘솔 GPU 단가 (config)", hw.actual_console_gpu_rate_usd_per_hour === null ? "미확인" : hw.actual_console_gpu_rate_usd_per_hour],
            ["선호 GPU", hw.preferred_gpu], ["제안 디스크", "container " + txt(hw.container_disk_gb_proposed) + "GB · volume " + txt(hw.volume_disk_gb_proposed) + "GB"]])),
        card("이번 실행 승인 양식 (원문 값)", apPairs.length ? kv(apPairs) : h("p", null, "RUNPOD_APPROVAL.md를 읽지 못했습니다."))),
    ]);
  }

  // ---- tests
  async function pageTests(view) {
    const s = await status();
    const j = s.junit;
    add(view, [
      pageHead("테스트", "artifacts/dashboard/pytest_junit.xml"),
      banner("CPU 기능 테스트(application_cpu_test) 결과입니다. 모델·GPU 결과가 아닙니다.", "info"),
      j ? card("pytest 요약", kv([["통과", (j.tests - j.failures - j.errors) + " / " + j.tests], ["실패 / 오류 / 건너뜀", j.failures + " / " + j.errors + " / " + j.skipped],
        ["소요", txt(j.time) + "s"], ["기록 시각", j.mtime]]),
        h("h3", null, "파일별 테스트 수"), bars(j.by_file),
        Object.keys(j.failed_by_file || {}).length ? [h("h3", null, "실패한 파일"), bars(j.failed_by_file)] : null)
        : card("pytest 요약", h("p", null, pill("not_run"), "junit 기록이 없습니다.")),
      card("다시 실행하는 방법", h("p", null, h("code", null, ".venv/Scripts/python.exe -m invoiceguard.dashboard --run-tests"), " 또는 서버 시작 시 ",
        h("code", null, "-m invoiceguard.dashboard_server --run-tests")), h("p", { class: "sub" }, "대시보드는 읽기 전용이라 화면에서 테스트를 실행하지 않습니다.")),
    ]);
  }

  // ---- review app placeholder
  async function pageReview(view) {
    const s = await status();
    const t06 = (s.tasks || []).find((t) => t.id === "T06");
    add(view, [
      pageHead("검수 앱", "업로드 → 추출 → 수정·승인 → export (T06)"),
      card("상태", kv([
        ["T06 단계", t06 ? pill(t06.status) : pill("unknown")], ["앱", pill("not_implemented")],
        ["검수 건 / 승인 / export", "— (앱 DB 없음)"], ["추론 큐·취소·격리", pill("not_run")],
        ["버전 CAS · 승인 스냅샷", pill("not_run")], ["모델 서버", pillCls("warn", "연결 없음 — fixture로 대체하지 않음")],
      ])),
      card("계획된 흐름 (구현 전)", h("ul", { class: "plain" },
        h("li", null, "영어 인보이스 이미지 업로드 → 실제 VLM 추출 (늦게 도착한 추론은 최신 수정·승인을 덮어쓰지 않음)"),
        h("li", null, "독립 발주서와 대사 → 사유 코드(QTY_DIFF, UNIT_PRICE_DIFF, PO_LINE_NOT_FOUND …) 표시"),
        h("li", null, "사람 검수·수정 → 승인 → 불변 승인 스냅샷 기반 버전 export"))),
    ]);
  }

  // ------------------------------------------------------------------ router
  const PAGES = { overview: pageOverview, progress: pageProgress, public: pagePublic, trade: pageTrade, splits: pageSplits,
    model: pageModel, runpod: pageRunpod, tests: pageTests, review: pageReview };
  function parseHash() {
    const raw = (location.hash || "").replace(/^#/, "") || "/overview";
    const qi = raw.indexOf("?");
    const path = qi >= 0 ? raw.slice(0, qi) : raw;
    const segs = path.split("/").filter(Boolean).map((x) => { try { return decodeURIComponent(x); } catch (e) { return ""; } });
    return { segs, query: new URLSearchParams(qi >= 0 ? raw.slice(qi + 1) : "") };
  }
  function setNav(page) {
    for (const a of document.querySelectorAll("nav a")) a.classList.toggle("active", a.dataset.page === page);
    sidebar.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  }
  async function route() {
    const token = ++routeToken;
    const { segs, query } = parseHash();
    const name = PAGES[segs[0]] ? segs[0] : "overview";
    setNav(name);
    const timer = setTimeout(() => { if (token === routeToken) main.replaceChildren(h("p", { class: "loading" }, "불러오는 중…")); }, 150);
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
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  window.addEventListener("hashchange", route);
  route();
})();
