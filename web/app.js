"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const stato = {
  utente: localStorage.getItem("sgs_utente") || "",
  sessione: localStorage.getItem("sgs_sessione") || (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
  configurazione: { sistemi: ["TGV", "MET", "FGC", "FPG", "FIL"] },
};
localStorage.setItem("sgs_sessione", stato.sessione);

async function api(percorso, opzioni = {}) {
  const risposta = await fetch(percorso, {
    headers: opzioni.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...opzioni,
  });
  if (!risposta.ok) {
    let dettaglio = risposta.statusText;
    try { dettaglio = (await risposta.json()).detail || dettaglio; } catch (_) {}
    throw new Error(dettaglio);
  }
  return risposta.status === 204 ? null : risposta.json();
}

const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------------------------------------------------------- markdown ---- */
function md(testo) {
  const righe = esc(testo).split("\n");
  let html = "", inLista = null, inTabella = false;
  const chiudi = () => { if (inLista) { html += `</${inLista}>`; inLista = null; }
                         if (inTabella) { html += "</tbody></table>"; inTabella = false; } };
  const inline = (t) => t
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  for (let i = 0; i < righe.length; i++) {
    const r = righe[i];
    if (/^\s*\|.*\|\s*$/.test(r)) {
      const celle = r.trim().slice(1, -1).split("|").map((c) => c.trim());
      if (/^\s*\|[\s:|-]+\|\s*$/.test(righe[i + 1] || "") && !inTabella) {
        chiudi(); inTabella = true;
        html += "<table><thead><tr>" + celle.map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>";
        i++; continue;
      }
      if (inTabella) { html += "<tr>" + celle.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>"; continue; }
    } else if (inTabella) { chiudi(); }

    const titolo = r.match(/^(#{1,4})\s+(.*)$/);
    const punto = r.match(/^\s*[-*•]\s+(.*)$/);
    const numero = r.match(/^\s*\d+[.)]\s+(.*)$/);
    const citazione = r.match(/^\s*>\s?(.*)$/);

    if (titolo) { chiudi(); html += `<h3>${inline(titolo[2])}</h3>`; }
    else if (punto) { if (inLista !== "ul") { chiudi(); html += "<ul>"; inLista = "ul"; } html += `<li>${inline(punto[1])}</li>`; }
    else if (numero) { if (inLista !== "ol") { chiudi(); html += "<ol>"; inLista = "ol"; } html += `<li>${inline(numero[1])}</li>`; }
    else if (citazione) { chiudi(); html += `<blockquote>${inline(citazione[1])}</blockquote>`; }
    else if (!r.trim()) { chiudi(); }
    else { chiudi(); html += `<p>${inline(r)}</p>`; }
  }
  chiudi();
  return html;
}

const fonteEtichetta = (c) => [c.codice, c.revisione ? `rev. ${c.revisione}` : null,
  c.pagina ? `pag. ${c.pagina}` : null, c.sezione ? `sez. ${c.sezione}` : null]
  .filter(Boolean).join(" · ");

/* -------------------------------------------------------------- schede -- */
$$("#schede button").forEach((b) => b.addEventListener("click", () => {
  $$("#schede button").forEach((x) => x.classList.remove("attivo"));
  $$(".pannello").forEach((p) => p.classList.remove("attivo"));
  b.classList.add("attivo");
  $(`#pannello-${b.dataset.scheda}`).classList.add("attivo");
  ({ proposte: caricaProposte, norme: caricaNorme, indicatori: caricaIndicatori,
     documenti: caricaDocumenti, audit: caricaAudit }[b.dataset.scheda] || (() => {}))();
}));

/* ----------------------------------------------------------------- KPI -- */
async function caricaStato() {
  const s = await api("/api/stato");
  const tessere = [
    ["Documenti indicizzati", s.documenti, ""],
    ["Passaggi ricercabili", s.passaggi_indicizzati, ""],
    ["Norme vigenti", s.norme_vigenti, ""],
    ["Norme in recepimento", s.norme_in_recepimento, s.norme_in_recepimento ? "attesa" : ""],
    ["Indicatori IPS", s.indicatori, ""],
    ["IPS fuori soglia", s.indicatori_fuori_soglia, s.indicatori_fuori_soglia ? "critica" : ""],
    ["Modifiche da confermare", s.proposte_in_attesa, s.proposte_in_attesa ? "attesa" : ""],
  ];
  $("#kpi").innerHTML = tessere.map(([e, v, c]) =>
    `<div class="tessera ${c}"><div class="valore">${v}</div><div class="etichetta">${e}</div></div>`).join("");
  const badge = $("#badge-proposte");
  badge.hidden = !s.proposte_in_attesa;
  badge.textContent = s.proposte_in_attesa;
}

/* ----------------------------------------------------------- assistente -- */
function aggiungiMessaggio(ruolo, testo, citazioni = []) {
  const vuoto = $("#messaggi .vuoto");
  if (vuoto) vuoto.remove();
  const div = document.createElement("div");
  div.className = `messaggio ${ruolo}`;
  div.innerHTML =
    `<div class="autore">${ruolo === "utente" ? esc(stato.utente || "Operatore") : "SGS Live"}</div>` +
    `<div class="bolla">${ruolo === "utente" ? `<p>${esc(testo)}</p>` : md(testo)}` +
    (citazioni.length
      ? `<div class="fonti">${citazioni.map((c) =>
          `<span class="fonte" title="${esc((c.evidenza || "").replace(/<<|>>/g, ""))}">${esc(fonteEtichetta(c))}</span>`).join("")}</div>`
      : "") + "</div>";
  $("#messaggi").appendChild(div);
  $("#messaggi").scrollTop = $("#messaggi").scrollHeight;
  return div;
}

async function invia() {
  const domanda = $("#domanda").value.trim();
  if (!domanda) return;
  if (!stato.utente) { alert("Indicare il nome dell'operatore: ogni interazione viene tracciata."); $("#utente").focus(); return; }
  $("#domanda").value = "";
  $("#btn-invia").disabled = true;
  aggiungiMessaggio("utente", domanda);
  const attesa = aggiungiMessaggio("assistente", "_Consultazione dei documenti in corso…_");
  try {
    const r = await api("/api/chat", { method: "POST", body: JSON.stringify(
      { domanda, sessione: stato.sessione, utente: stato.utente }) });
    attesa.remove();
    aggiungiMessaggio("assistente", r.testo, r.citazioni || []);
    if (r.proposte && r.proposte.length) {
      const nota = r.proposte.map((p) => `- **Proposta n. ${p.id}** — ${p.riepilogo}`).join("\n");
      aggiungiMessaggio("assistente",
        `⚠️ **Nessuna modifica è stata scritta.** In attesa di conferma nella scheda «Modifiche da confermare»:\n${nota}`);
      caricaStato(); caricaProposte();
    }
  } catch (e) {
    attesa.remove();
    aggiungiMessaggio("assistente", `**Errore:** ${esc(e.message)}`);
  } finally {
    $("#btn-invia").disabled = false;
  }
}

$("#btn-invia").addEventListener("click", invia);
$("#domanda").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); invia(); }
});
$$(".suggerimenti button").forEach((b) => b.addEventListener("click", () => {
  $("#domanda").value = b.textContent; $("#domanda").focus();
}));

/* ------------------------------------------------------------ proposte -- */
function renderDifferenze(anteprima) {
  const d = (anteprima && anteprima.differenze) || {};
  const chiavi = Object.keys(d);
  if (!chiavi.length) return '<div class="differenza">Nessuna variazione rispetto al dato attuale.</div>';
  return `<table><thead><tr><th>Campo</th><th>Valore attuale</th><th>Valore proposto</th></tr></thead><tbody>` +
    chiavi.map((k) => `<tr><td>${esc(k)}</td>` +
      `<td class="differenza"><span class="prima">${esc(d[k].prima ?? "—")}</span></td>` +
      `<td class="differenza"><span class="dopo">${esc(d[k].dopo ?? "—")}</span></td></tr>`).join("") +
    "</tbody></table>";
}

async function caricaProposte() {
  const elenco = await api(`/api/proposte?stato=${$("#filtro-proposte").value}`);
  const contenitore = $("#elenco-proposte");
  if (!elenco.length) { contenitore.innerHTML = '<div class="vuoto">Nessuna proposta.</div>'; return; }
  contenitore.innerHTML = elenco.map((p) => {
    const soglia = p.anteprima && p.anteprima.stato_soglia
      ? ` <span class="pillola ${p.anteprima.stato_soglia}">${p.anteprima.stato_soglia}</span>` : "";
    const azioni = p.stato === "in_attesa"
      ? `<div class="azioni">
           <button class="primario" data-conferma="${p.id}">Conferma e scrivi</button>
           <button class="pericolo" data-rifiuta="${p.id}">Rifiuta</button>
         </div>`
      : `<div class="meta">${esc(p.stato)} da ${esc(p.decisa_da || "—")} il ${esc(p.decisa_il || "—")}${p.esito ? " · " + esc(p.esito) : ""}</div>`;
    return `<div class="proposta">
      <h3>#${p.id} — ${esc(p.riepilogo)}${soglia}</h3>
      <div class="meta">Proposta il ${esc(p.creata_il)} su richiesta di ${esc(p.utente || "—")} · strumento <code>${esc(p.strumento)}</code></div>
      <div><strong>Motivazione dichiarata:</strong> ${esc(p.motivazione || "—")}</div>
      <div style="margin-top:8px">${renderDifferenze(p.anteprima)}</div>
      ${azioni}</div>`;
  }).join("");

  contenitore.querySelectorAll("[data-conferma]").forEach((b) => b.addEventListener("click", async () => {
    if (!richiediOperatore()) return;
    if (!confirm("Confermi la scrittura sul registro? L'operazione viene tracciata a tuo nome.")) return;
    try {
      await api(`/api/proposte/${b.dataset.conferma}/conferma`, { method: "POST", body: JSON.stringify({ utente: stato.utente }) });
      await Promise.all([caricaProposte(), caricaStato()]);
    } catch (e) { alert(e.message); }
  }));
  contenitore.querySelectorAll("[data-rifiuta]").forEach((b) => b.addEventListener("click", async () => {
    if (!richiediOperatore()) return;
    const motivo = prompt("Motivo del rifiuto (facoltativo):") ?? "";
    try {
      await api(`/api/proposte/${b.dataset.rifiuta}/rifiuta`, { method: "POST", body: JSON.stringify({ utente: stato.utente, motivo }) });
      await Promise.all([caricaProposte(), caricaStato()]);
    } catch (e) { alert(e.message); }
  }));
}
$("#filtro-proposte").addEventListener("change", caricaProposte);

function richiediOperatore() {
  if (stato.utente) return true;
  alert("Indicare il nome dell'operatore in alto a destra: le scritture devono essere attribuibili.");
  $("#utente").focus();
  return false;
}

/* --------------------------------------------------------------- norme -- */
async function caricaNorme() {
  const q = new URLSearchParams({ testo: $("#cerca-norme").value, stato: $("#filtro-stato-norme").value });
  const elenco = await api(`/api/norme?${q}`);
  $("#tabella-norme").innerHTML = elenco.length ? `<table><thead><tr>
      <th>Riferimento</th><th>Titolo</th><th>Ente</th><th>Sistemi</th><th>Stato</th>
      <th>Impatto / azioni</th><th>Resp.</th><th>Scadenza</th><th></th></tr></thead><tbody>` +
    elenco.map((n) => `<tr>
      <td><strong>${esc(n.riferimento)}</strong></td><td>${esc(n.titolo)}</td><td>${esc(n.ente || "—")}</td>
      <td>${esc(n.sistemi || "—")}</td><td><span class="pillola">${esc(n.stato)}</span></td>
      <td>${esc(n.valutazione_impatto || n.azioni_conseguenti || "—")}</td>
      <td>${esc(n.responsabile || "—")}</td><td>${esc(n.scadenza || "—")}</td>
      <td><button data-modifica-norma='${esc(JSON.stringify(n))}'>Modifica</button></td></tr>`).join("") +
    "</tbody></table>" : '<div class="vuoto">Registro normative vuoto.</div>';
  $$("#tabella-norme [data-modifica-norma]").forEach((b) =>
    b.addEventListener("click", () => formNorma(JSON.parse(b.dataset.modificaNorma))));
}
$("#cerca-norme").addEventListener("input", caricaNorme);
$("#filtro-stato-norme").addEventListener("change", caricaNorme);
$("#btn-nuova-norma").addEventListener("click", () => formNorma({}));

const CAMPI_NORMA = [
  ["riferimento", "Riferimento *", "testo"], ["titolo", "Titolo", "testo"],
  ["ente", "Ente emittente", "testo"], ["tipo_atto", "Tipo di atto", "testo"],
  ["data_pubblicazione", "Pubblicazione", "date"], ["data_entrata_vigore", "Entrata in vigore", "date"],
  ["sistemi", "Sistemi applicabili", "testo"], ["ambito", "Ambito", "testo"],
  ["stato", "Stato", "select", ["vigente", "in_recepimento", "monitoraggio", "abrogata"]],
  ["responsabile", "Responsabile", "testo"], ["scadenza", "Scadenza azione", "date"],
  ["documenti_sgs_impattati", "Documenti SGS impattati", "testo"],
  ["sintesi_applicabilita", "Sintesi applicabilità", "area"],
  ["valutazione_impatto", "Valutazione di impatto", "area"],
  ["azioni_conseguenti", "Azioni conseguenti", "area"], ["note", "Note", "area"],
];

function campoHtml([chiave, etichetta, tipo, opzioni], valori) {
  const v = valori[chiave] ?? "";
  const largo = tipo === "area" ? ' class="largo"' : "";
  let controllo;
  if (tipo === "select") controllo = `<select name="${chiave}">` +
    opzioni.map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("") + "</select>";
  else if (tipo === "area") controllo = `<textarea name="${chiave}" rows="2">${esc(v)}</textarea>`;
  else controllo = `<input name="${chiave}" type="${tipo === "date" ? "date" : tipo === "numero" ? "number" : "text"}" step="any" value="${esc(v)}">`;
  return `<label${largo}>${etichetta}${controllo}</label>`;
}

function apriDialogo(titolo, campi, valori, alSalvataggio) {
  $("#form-dialogo").innerHTML =
    `<h3 style="margin-top:0">${esc(titolo)}</h3><div class="griglia-campi">` +
    campi.map((c) => campoHtml(c, valori)).join("") +
    `</div><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px">
       <button value="annulla">Annulla</button>
       <button class="primario" value="salva">Salva</button></div>`;
  const dialogo = $("#dialogo");
  dialogo.showModal();
  $("#form-dialogo").onsubmit = async (e) => {
    if (e.submitter && e.submitter.value !== "salva") return;
    const dati = Object.fromEntries(new FormData(e.target).entries());
    try { await alSalvataggio(dati); } catch (err) { alert(err.message); }
  };
}

function formNorma(valori) {
  if (!richiediOperatore()) return;
  apriDialogo(valori.id ? `Modifica ${valori.riferimento}` : "Nuova voce del registro normative",
    CAMPI_NORMA, valori, async (dati) => {
      await api("/api/norme", { method: "POST", body: JSON.stringify({ ...dati, utente: stato.utente }) });
      await Promise.all([caricaNorme(), caricaStato()]);
    });
}

/* ---------------------------------------------------------- indicatori -- */
function sparkline(serie) {
  if (!serie || !serie.length) return "—";
  const valori = serie.map((m) => m.valore);
  const max = Math.max(...valori, 0.0001);
  return `<div class="sparkline" title="${serie.map((m) => `${m.periodo}: ${m.valore}`).join(" · ")}">` +
    serie.map((m) => `<i style="height:${Math.max(2, (m.valore / max) * 26)}px"></i>`).join("") + "</div>";
}

async function caricaIndicatori() {
  const elenco = await api(`/api/indicatori?sistema=${$("#filtro-sistema-ips").value}`);
  $("#tabella-indicatori").innerHTML = elenco.length ? `<table><thead><tr>
      <th>Codice</th><th>Sist.</th><th>Descrizione</th><th>U.M.</th><th>Tipo</th>
      <th>Allarme</th><th>Intervento</th><th>Ultima misura</th><th>Stato</th><th>Andamento</th><th></th>
    </tr></thead><tbody>` + elenco.map((i) => `<tr>
      <td><strong>${esc(i.codice)}</strong></td><td>${esc(i.sistema)}</td>
      <td>${esc(i.descrizione)}${i.id_ep ? `<br><small style="color:var(--testo-tenue)">EP: ${esc(i.id_ep)}</small>` : ""}</td>
      <td>${esc(i.unita_misura || "—")}</td><td>${esc(i.tipo)}</td>
      <td>${i.soglia_allarme ?? "—"}</td><td>${i.soglia_intervento ?? "—"}</td>
      <td>${i.ultima_misura ?? "—"}${i.ultimo_periodo ? `<br><small style="color:var(--testo-tenue)">${esc(i.ultimo_periodo)}</small>` : ""}</td>
      <td><span class="pillola ${i.stato_soglia}">${esc(i.stato_soglia.replace("_", " "))}</span></td>
      <td>${sparkline(i.serie)}</td>
      <td style="white-space:nowrap">
        <button data-misura="${i.id}" data-codice="${esc(i.codice)}">+ Misura</button>
        <button data-modifica-ips='${esc(JSON.stringify(i))}'>Modifica</button></td></tr>`).join("") +
    "</tbody></table>" : '<div class="vuoto">Nessun indicatore registrato.</div>';

  $$("#tabella-indicatori [data-misura]").forEach((b) => b.addEventListener("click", () => {
    if (!richiediOperatore()) return;
    apriDialogo(`Nuova misura — ${b.dataset.codice}`, [
      ["periodo", "Periodo * (es. 2026-Q1)", "testo"], ["valore", "Valore *", "numero"],
      ["fonte", "Fonte del dato", "testo"], ["note", "Note", "area"],
    ], { periodo: periodoCorrente() }, async (dati) => {
      await api(`/api/indicatori/${b.dataset.misura}/misure`,
        { method: "POST", body: JSON.stringify({ ...dati, utente: stato.utente }) });
      await Promise.all([caricaIndicatori(), caricaStato()]);
    });
  }));
  $$("#tabella-indicatori [data-modifica-ips]").forEach((b) =>
    b.addEventListener("click", () => formIndicatore(JSON.parse(b.dataset.modificaIps))));
}

function periodoCorrente() {
  const o = new Date();
  return `${o.getFullYear()}-Q${Math.floor(o.getMonth() / 3) + 1}`;
}

function formIndicatore(valori) {
  if (!richiediOperatore()) return;
  apriDialogo(valori.id ? `Modifica ${valori.codice}` : "Nuovo indicatore IPS", [
    ["codice", "Codice * (es. IPS01)", "testo"],
    ["sistema", "Sistema *", "select", stato.configurazione.sistemi],
    ["descrizione", "Descrizione *", "area"],
    ["unita_misura", "Unità di misura", "testo"],
    ["tipo", "Tipo", "select", ["reattivo", "proattivo"]],
    ["verso", "Direzione sfavorevole", "select", ["min", "max"]],
    ["soglia_allarme", "Soglia di Allarme", "numero"],
    ["soglia_intervento", "Soglia di Intervento", "numero"],
    ["soglia_accettabilita", "Soglia di accettabilità (testo)", "testo"],
    ["id_ep", "ID eventi pericolosi (Hazard Log)", "testo"],
    ["responsabile", "Responsabile", "testo"],
    ["periodicita", "Periodicità", "testo"],
    ["note", "Note", "area"],
  ], { periodicita: "trimestrale", verso: "min", tipo: "reattivo", ...valori }, async (dati) => {
    await api("/api/indicatori", { method: "POST", body: JSON.stringify({ ...dati, utente: stato.utente }) });
    await Promise.all([caricaIndicatori(), caricaStato()]);
  });
}
$("#btn-nuovo-ips").addEventListener("click", () => formIndicatore({}));
$("#filtro-sistema-ips").addEventListener("change", caricaIndicatori);

/* ---------------------------------------------------------- documenti -- */
async function caricaDocumenti() {
  const elenco = await api("/api/documenti");
  $("#tabella-documenti").innerHTML = elenco.length ? `<table><thead><tr>
      <th>Codice</th><th>Titolo</th><th>Tipo</th><th>Sist.</th><th>Rev.</th>
      <th>Passaggi</th><th>Indicizzato il</th><th></th></tr></thead><tbody>` +
    elenco.map((d) => `<tr><td><strong>${esc(d.codice)}</strong></td><td>${esc(d.titolo)}</td>
      <td>${esc(d.tipo)}</td><td>${esc(d.sistema)}</td><td>${esc(d.revisione || "—")}</td>
      <td>${d.n_chunk}</td><td>${esc((d.indicizzato_il || "").slice(0, 16).replace("T", " "))}</td>
      <td><a href="/api/documenti/${d.id}/file" download><button>Apri</button></a></td></tr>`).join("") +
    "</tbody></table>"
    : '<div class="vuoto">Nessun documento indicizzato. Carica un file o copia i documenti nella cartella e premi «Reindicizza».</div>';
}

$("#btn-carica").addEventListener("click", async () => {
  const file = $("#file-documento").files[0];
  if (!file) { alert("Selezionare un file."); return; }
  if (!richiediOperatore()) return;
  const dati = new FormData();
  dati.append("file", file);
  dati.append("utente", stato.utente);
  $("#btn-carica").disabled = true;
  try {
    const r = await api("/api/documenti/carica", { method: "POST", body: dati });
    alert(`${r.codice}: ${r.stato}${r.chunk ? ` (${r.chunk} passaggi)` : ""}${r.avviso ? "\n" + r.avviso : ""}`);
    await Promise.all([caricaDocumenti(), caricaStato()]);
  } catch (e) { alert(e.message); } finally { $("#btn-carica").disabled = false; }
});

$("#btn-reindicizza").addEventListener("click", async () => {
  $("#btn-reindicizza").disabled = true;
  $("#btn-reindicizza").textContent = "Indicizzazione…";
  try {
    const r = await api("/api/indicizza", { method: "POST", body: JSON.stringify({ utente: stato.utente || "operatore" }) });
    const riepilogo = r.esiti.reduce((acc, e) => { acc[e.stato] = (acc[e.stato] || 0) + 1; return acc; }, {});
    alert(`File esaminati: ${r.totale}\n` + Object.entries(riepilogo).map(([k, v]) => `${k}: ${v}`).join("\n"));
    await Promise.all([caricaDocumenti(), caricaStato()]);
  } catch (e) { alert(e.message); }
  finally { $("#btn-reindicizza").disabled = false; $("#btn-reindicizza").textContent = "Reindicizza cartella"; }
});

/* -------------------------------------------------------------- audit -- */
async function caricaAudit() {
  const elenco = await api("/api/audit?limite=200");
  const breve = (t) => { if (!t) return "—"; const s = JSON.parse(t);
    return esc(Object.entries(s).filter(([, v]) => v !== null && v !== "")
      .map(([k, v]) => `${k}=${String(v).slice(0, 40)}`).join("; ").slice(0, 220)); };
  $("#tabella-audit").innerHTML = elenco.length ? `<table><thead><tr>
      <th>Data e ora</th><th>Operatore</th><th>Azione</th><th>Entità</th><th>Origine</th>
      <th>Prima</th><th>Dopo</th></tr></thead><tbody>` +
    elenco.map((a) => `<tr><td style="white-space:nowrap">${esc(a.ts.slice(0, 19).replace("T", " "))}</td>
      <td>${esc(a.utente)}</td><td>${esc(a.azione)}</td><td>${esc(a.entita)} #${esc(a.entita_id || "")}</td>
      <td>${esc(a.origine)}</td><td>${breve(a.prima)}</td><td>${breve(a.dopo)}</td></tr>`).join("") +
    "</tbody></table>" : '<div class="vuoto">Nessuna operazione registrata.</div>';
}

/* ---------------------------------------------------------------- avvio -- */
$("#utente").value = stato.utente;
$("#utente").addEventListener("change", (e) => {
  stato.utente = e.target.value.trim();
  localStorage.setItem("sgs_utente", stato.utente);
});
$("#btn-aggiorna").addEventListener("click", () => {
  caricaStato();
  const attiva = $("#schede button.attivo").dataset.scheda;
  ({ proposte: caricaProposte, norme: caricaNorme, indicatori: caricaIndicatori,
     documenti: caricaDocumenti, audit: caricaAudit }[attiva] || (() => {}))();
});

(async function avvio() {
  try {
    stato.configurazione = await api("/api/configurazione");
    $("#info-cartella").textContent = `Cartella monitorata: ${stato.configurazione.cartella_documenti} · modello ${stato.configurazione.modello}`;
    $("#filtro-sistema-ips").innerHTML = '<option value="">Tutti i sistemi</option>' +
      stato.configurazione.sistemi.map((s) => `<option>${s}</option>`).join("");
  } catch (_) {}
  await caricaStato();
  for (const m of await api(`/api/conversazione/${stato.sessione}`)) {
    aggiungiMessaggio(m.ruolo === "utente" ? "utente" : "assistente", m.testo);
  }
})();
