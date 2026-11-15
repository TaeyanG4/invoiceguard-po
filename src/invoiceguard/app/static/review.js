// InvoiceGuard review screen: plain DOM, same-origin calls to the review API only (CSP self-only).
// Every rule lives in the API (versions, blockers, reasons, immutable snapshots); this file only shows and sends.
"use strict";

const DOC_FIELDS = [["invoice_number_raw", "인보이스 번호"], ["currency_raw", "통화"], ["subtotal_raw", "소계"],
  ["tax_raw", "세금"], ["discount_raw", "할인"], ["total_raw", "합계"]];
const ROW_FIELDS = [["sku_raw", "품번", "sku"], ["description_raw", "품명", "desc"], ["quantity_raw", "수량", "num"],
  ["unit_raw", "단위", ""], ["unit_price_raw", "단가", "num"], ["line_total_raw", "금액", "num"]];
const STATES = { uploaded: ["업로드됨", ""], extracting: ["추출 중", "warn"], needs_review: ["검토 필요", "warn"],
  matched_candidate: ["일치 후보", "ok"], approved: ["승인됨", "ok"], rejected: ["반려", "bad"], failed: ["실패", "bad"] };
const SEVERITY = { blocker: ["보완 필요", "bad"], warning: ["경고", "warn"], info: ["정보", ""] };

let current = null;   // last GET /api/cases/{id}
let selected = null;  // case id
let busy = false;

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

function toast(text, bad) {
  const t = document.getElementById("toast");
  t.textContent = text;
  t.className = "toast" + (bad ? " bad" : "");
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, bad ? 7000 : 3500);
}

async function api(method, path, body, isForm) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = data.error || {};
    throw new Error((e.code ? e.code + " — " : "") + (e.message || res.status));
  }
  return data;
}

async function guarded(label, fn) {
  if (busy) return;
  busy = true;
  document.body.setAttribute("aria-busy", "true");
  if (label) toast(label);
  try { await fn(); } catch (err) { toast(err.message, true); } finally {
    busy = false;
    document.body.removeAttribute("aria-busy");
  }
}

function statePill(state, reason) {
  const [name, cls] = STATES[state] || [state, ""];
  return h("span", { class: "pill " + cls }, name + (reason ? " · " + reason : ""));
}

async function loadHealth() {
  const el = document.getElementById("model");
  try {
    const hl = await api("GET", "/health");
    el.textContent = "모델 " + hl.model_mode + (hl.model_label ? " · " + hl.model_label : "") + (hl.model_ready ? "" : " · 사용 불가");
    el.className = "pill " + (hl.model_ready ? "ok" : "bad");
  } catch (err) { el.textContent = "API 연결 실패"; el.className = "pill bad"; }
}

async function loadSamples() {
  const { samples } = await api("GET", "/api/samples");
  const box = document.getElementById("sampleBox");
  const sel = document.getElementById("sample");
  sel.replaceChildren(...samples.map((s) => h("option", { value: s.doc_id }, s.label)));
  box.hidden = samples.length === 0;
}

async function loadCases() {
  const { cases } = await api("GET", "/api/cases");
  const ul = document.getElementById("cases");
  if (!cases.length) { ul.replaceChildren(h("li", { class: "sub" }, "아직 케이스가 없습니다.")); return; }
  ul.replaceChildren(...cases.map((c) => h("li", null, h("button", {
    type: "button", "aria-current": c.case_id === selected ? "true" : null, onclick: () => openCase(c.case_id),
  }, h("span", null, statePill(c.state), " v" + c.version), h("span", { class: "sub" }, c.po_id + " v" + c.po_version + " · " + c.case_id.slice(0, 8))))));
}

async function openCase(id) {
  selected = id;
  history.replaceState(null, "", "#case=" + id);
  current = await api("GET", "/api/cases/" + id);
  render();
  loadCases().catch(() => {});
}

function input(value, attrs) {
  const el = h("input", Object.assign({ type: "text" }, attrs));
  el.value = value === null || value === undefined ? "" : value;
  el.dataset.orig = el.value;
  el.addEventListener("input", () => el.classList.toggle("changed", el.value !== el.dataset.orig));
  return el;
}

function collectEdits() {
  const edits = [];
  const asValue = (v) => (v.trim() === "" ? null : v);
  document.querySelectorAll("[data-doc]").forEach((el) => {
    if (el.value !== el.dataset.orig) edits.push({ op: "set", field: el.dataset.doc, value: asValue(el.value) });
  });
  const deleted = [];
  document.querySelectorAll("tr[data-row]").forEach((tr) => {
    const row = Number(tr.dataset.row);
    if (tr.querySelector("[data-del]").checked) { deleted.push(row); return; }
    tr.querySelectorAll("[data-cell]").forEach((el) => {
      if (el.value !== el.dataset.orig) edits.push({ op: "set", field: el.dataset.cell, row_index: row, value: asValue(el.value) });
    });
  });
  deleted.sort((a, b) => b - a).forEach((row) => edits.push({ op: "delete_row", row_index: row }));
  let count = (current.current.items || []).length - deleted.length;
  document.querySelectorAll("tr[data-new]").forEach((tr) => {
    const values = {};
    tr.querySelectorAll("[data-cell]").forEach((el) => { values[el.dataset.cell] = asValue(el.value); });
    if (Object.values(values).some((v) => v !== null)) { edits.push({ op: "add_row", values, after_row_index: count }); count += 1; }
  });
  return edits;
}

function itemsTable(items, flags) {
  const head = h("tr", null, h("th", null, "행"), ROW_FIELDS.map(([, label]) => h("th", null, label)), h("th", null, "삭제"));
  const body = items.map((it) => h("tr", { "data-row": it.row_index, class: flags[it.row_index] ? "flag-" + flags[it.row_index] : null },
    h("td", null, String(it.row_index)),
    ROW_FIELDS.map(([f, label, cls]) => h("td", { class: cls }, input(it[f], { "data-cell": f, "aria-label": "행 " + it.row_index + " " + label }))),
    h("td", null, h("input", { type: "checkbox", "data-del": "", "aria-label": "행 " + it.row_index + " 삭제" }))));
  const tbody = h("tbody", null, body);
  const add = h("button", { type: "button", class: "ghost", onclick: () => {
    tbody.append(h("tr", { "data-new": "" }, h("td", null, "+"),
      ROW_FIELDS.map(([f, label, cls]) => h("td", { class: cls }, input("", { "data-cell": f, "aria-label": "새 행 " + label }))), h("td")));
  } }, "행 추가");
  return h("div", null, h("div", { class: "tablewrap" }, h("table", null, h("thead", null, head), tbody)), h("p", null, add));
}

function findingsList(findings) {
  if (!findings.length) return h("p", { class: "hint" }, "대사 결과 경고가 없습니다.");
  return h("ul", { class: "findings" }, findings.map((f) => {
    const [name, cls] = SEVERITY[f.severity] || [f.severity, ""];
    const where = f.row_index ? "행 " + f.row_index : "문서";
    const diff = (f.expected !== null && f.expected !== undefined) || (f.observed !== null && f.observed !== undefined)
      ? "기대값 " + (f.expected ?? "—") + " · 인보이스 " + (f.observed ?? "—") : null;
    return h("li", null,
      h("div", { class: "meta" }, h("span", { class: "pill " + cls }, name), h("code", null, f.code), h("span", null, where + (f.field ? " · " + f.field : "")), diff && h("span", { class: "hint" }, diff)),
      h("span", null, f.message || ""),
      f.severity === "blocker" ? h("span", { class: "hint" }, "값을 고쳐야 승인할 수 있습니다(사유로 넘길 수 없음).")
        : input("", { "data-key": f.key, placeholder: "확인 사유 (승인에 필요)", "aria-label": f.code + " 확인 사유" }));
  }));
}

function render() {
  const c = current;
  const main = document.getElementById("main");
  const findings = (c.findings && c.findings.findings) || [];
  const flags = {};
  for (const f of findings) if (f.row_index && (flags[f.row_index] !== "blocker")) flags[f.row_index] = f.severity === "blocker" ? "blocker" : f.severity === "warning" ? "warning" : flags[f.row_index];
  const approved = c.state === "approved";
  const canEdit = c.current && c.state !== "extracting";
  const canApprove = ["needs_review", "matched_candidate"].includes(c.state) && !findings.some((f) => f.severity === "blocker");

  const extractBtn = h("button", { type: "button", disabled: c.state === "extracting" || approved, onclick: () => guarded("추출 중… (모델 응답을 기다립니다)", async () => {
    await api("POST", "/api/cases/" + c.case_id + "/extract", { expected_version: c.version });
    await openCase(c.case_id); toast("추출 결과를 새 버전으로 저장했습니다.");
  }) }, c.current ? "다시 추출" : "추출 실행");

  const reason = input("", { placeholder: "수정 사유 (필수)", "aria-label": "수정 사유" });
  const saveBtn = h("button", { type: "button", disabled: !canEdit, onclick: () => guarded(null, async () => {
    const edits = collectEdits();
    if (!edits.length) { toast("바뀐 값이 없습니다."); return; }
    await api("PUT", "/api/cases/" + c.case_id + "/review", { expected_version: c.version, reason: reason.value, edits });
    await openCase(c.case_id); toast("수정을 새 버전으로 저장했습니다. 이전 승인은 취소됩니다.");
  }) }, "수정 저장");

  const reviewer = input("", { placeholder: "검수자 이름", "aria-label": "검수자" });
  const approveBtn = h("button", { type: "button", disabled: !canApprove, onclick: () => guarded(null, async () => {
    const dispositions = {};
    document.querySelectorAll("[data-key]").forEach((el) => { dispositions[el.dataset.key] = { decision: "accept", reason: el.value.trim() }; });
    await api("POST", "/api/cases/" + c.case_id + "/approve", { expected_version: c.version, reviewer: reviewer.value || "local_operator", dispositions });
    await openCase(c.case_id); toast("승인했습니다. 이 버전의 스냅샷만 내보낼 수 있습니다.");
  }) }, "승인");
  const rejectBtn = h("button", { type: "button", class: "danger", disabled: approved || c.state === "extracting", onclick: () => guarded(null, async () => {
    await api("POST", "/api/cases/" + c.case_id + "/reject", { expected_version: c.version, reason: reason.value });
    await openCase(c.case_id); toast("반려했습니다.");
  }) }, "반려");
  const exportLinks = approved ? h("span", { class: "actions" },
    h("a", { href: "/api/cases/" + c.case_id + "/export?format=json", download: "invoiceguard_" + c.case_id.slice(0, 8) + ".json" }, "JSON 내보내기"),
    h("a", { href: "/api/cases/" + c.case_id + "/export?format=csv", download: "invoiceguard_" + c.case_id.slice(0, 8) + ".csv" }, "CSV 내보내기")) : null;

  const data = c.current;
  main.replaceChildren(
    h("div", { class: "casehead" }, h("h2", null, "케이스"), statePill(c.state, c.state_reason), h("span", { class: "pill" }, "버전 " + c.version),
      h("span", { class: "pill" }, "발주서 " + c.po.po_id + " v" + c.po.po_version), c.approval ? h("span", { class: "pill ok" }, "승인 " + c.approval.reviewer) : null,
      h("span", { class: "id" }, c.case_id)),
    h("div", { class: "split" },
      h("div", { class: "imgbox" }, h("img", { src: "/api/cases/" + c.case_id + "/image", alt: "업로드한 인보이스 이미지" })),
      h("div", null,
        h("section", { class: "card" }, h("div", { class: "cardhead" }, h("h2", null, "추출 결과"), extractBtn),
          data ? h("div", null,
            h("div", { class: "docfields" }, DOC_FIELDS.map(([f, label]) => h("div", null, h("label", { for: "doc_" + f }, label), input(data[f], { id: "doc_" + f, "data-doc": f })))),
            itemsTable(data.items || [], flags))
            : h("p", { class: "hint" }, c.state === "failed" ? "추출이 실패했습니다. 다시 추출하세요(예시 결과로 대체하지 않습니다)." : "아직 추출 결과가 없습니다.")),
        data ? h("section", { class: "card" }, h("h2", null, "발주서 대사 결과"), findingsList(findings)) : null,
        h("section", { class: "card" }, h("h2", null, "검수"),
          h("div", { class: "actions" }, h("div", { class: "grow" }, h("label", null, "수정 사유 / 반려 사유"), reason), saveBtn),
          h("div", { class: "actions" }, h("div", { class: "grow" }, h("label", null, "검수자"), reviewer), approveBtn, rejectBtn),
          exportLinks,
          !canApprove && !approved && data ? h("p", { class: "hint" }, "승인 조건: 상태가 검토 필요/일치 후보이고, 보완 필요 항목이 없고, 모든 경고에 확인 사유가 있어야 합니다.") : null),
        h("section", { class: "card runs" }, h("h2", null, "추출 이력"),
          c.runs.length ? h("table", null, h("thead", null, h("tr", null, ["실행", "상태", "모드", "모델", "지연"].map((t) => h("th", null, t)))),
            h("tbody", null, c.runs.map((r) => h("tr", null, h("td", null, r.run_id.slice(0, 8)), h("td", null, r.status), h("td", null, r.extractor_mode),
              h("td", null, r.model_label || ""), h("td", null, r.latency_s ? r.latency_s.toFixed(1) + "s" : "—")))))
            : h("p", { class: "hint" }, "아직 추출하지 않았습니다.")))));
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("refresh").addEventListener("click", () => guarded(null, loadCases));
  document.getElementById("loadSample").addEventListener("click", () => guarded(null, async () => {
    const id = document.getElementById("sample").value;
    const r = await api("POST", "/api/samples/" + encodeURIComponent(id));
    await openCase(r.case_id); toast("예시 문서와 발주서를 등록했습니다. 추출을 실행하세요.");
  }));
  document.getElementById("upload").addEventListener("click", () => guarded(null, async () => {
    const poFile = document.getElementById("poFile").files[0];
    const img = document.getElementById("imgFile").files[0];
    if (!poFile || !img) { toast("발주서 JSON과 이미지를 모두 고르세요.", true); return; }
    const po = JSON.parse(await poFile.text());
    try { await api("POST", "/api/purchase-orders", po); } catch (err) { if (!String(err.message).startsWith("PO_VERSION_EXISTS")) throw err; }
    const form = new FormData();
    form.append("image", img); form.append("po_id", po.po_id); form.append("po_version", String(po.po_version));
    const r = await api("POST", "/api/cases", form, true);
    await openCase(r.case_id); toast("케이스를 만들었습니다. 추출을 실행하세요.");
  }));
  loadHealth(); loadSamples().catch(() => {}); loadCases().catch((err) => toast(err.message, true));
  const deep = /^#case=([0-9a-f-]{36})$/.exec(location.hash);  // shareable link to one case on this machine
  if (deep) openCase(deep[1]).catch((err) => toast(err.message, true));
});
