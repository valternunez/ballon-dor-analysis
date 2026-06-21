/* Goals or Stories? — interactive charts for the editorial redesign (D3 v7, vanilla).
   Every chart is real + data-driven (from data.js) + interactive (hover on desktop, tap on touch).
   The look matches the design (warm palette, Bodoni/Newsreader/Mono); curated copy — leaderboard
   descriptors, de-faming notes, per-year verdicts — lives here as editorial overlays on the data. */
(function () {
  "use strict";
  const D = window.BDOR;
  if (!D) { console.error("data.js missing"); return; }

  // On phones/touch, drop chart tooltips entirely (they fight with scrolling); desktop keeps hover.
  const MOBILE = window.matchMedia("(max-width: 760px), (pointer: coarse)").matches;

  const GOLD = "#c9a44c", HOT = "#d8693c", COOL = "#5f93c9", INK = "#ece6da",
        MUTED = "#a79d8b", FAINT = "#6f6757", NEUTRAL = "#6f6757", BG = "#0c0b09";
  const fmtN = n => Math.round(n).toLocaleString("en-US");
  const sgn = v => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2);
  const POSX = 95.2;  // x-position scale: value * 95.2% (matches the design's axis: +1.0 → 95.2%)

  // diverging colour by Hype Score: neutral→hot for +, neutral→cool for − (design's mix)
  const hx = h => { h = h.replace("#", ""); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
  const mix = (a, b, t) => { const A = hx(a), B = hx(b); return "rgb(" + A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(",") + ")"; };
  const hcol = v => { const t = 0.28 + Math.min(1, Math.abs(v) / 2.4) * 0.72; return v >= 0 ? mix(NEUTRAL, HOT, t) : mix(NEUTRAL, COOL, t); };

  // ---- shared tooltip (hover + tap) ----
  const tip = document.createElement("div");
  tip.className = "tooltip";
  document.body.appendChild(tip);
  const showTip = (html, x, y) => {
    tip.innerHTML = html; tip.style.opacity = 1;
    tip.style.left = Math.min(x + 14, window.innerWidth - 250) + "px";
    tip.style.top = (y + 14) + "px";
  };
  const hideTip = () => { tip.style.opacity = 0; };
  if (!MOBILE) document.addEventListener("touchstart", hideTip, { passive: true });
  // attach hover (always) + tap (desktop/non-touch only) tooltip to a DOM node
  function bindTip(node, html) {
    node.addEventListener("mousemove", e => showTip(html, e.clientX, e.clientY));
    node.addEventListener("mouseleave", hideTip);
    if (!MOBILE) node.addEventListener("touchstart",
      e => { e.stopPropagation(); showTip(html, e.touches[0].clientX, e.touches[0].clientY); }, { passive: true });
  }

  // ---- curated editorial copy (matches the design) ----
  const DESC = {
    "Lamine Yamal|2024": "16-yo phenomenon", "Khvicha Kvaratskhelia|2023": "Napoli breakout",
    "Randal Kolo Muani|2023": "World Cup final goal", "Nico Williams|2024": "Euro star turn",
    "Pedri|2021": "teenage prodigy", "Cole Palmer|2024": "breakout season",
    "Désiré Doué|2025": "treble teenager", "Gianluigi Donnarumma|2021": "Euro-winning keeper",
    "Kevin De Bruyne|2019": "elite, overlooked", "Lautaro Martínez|2021": "quietly elite",
    "Harry Kane|2025": "goals, no buzz", "Serhou Guirassy|2025": "overlooked scorer",
    "Alisson|2019": "best keeper, ignored", "Roberto Firmino|2019": "selfless, unsung",
    "Robert Lewandowski|2019": "robbed of his due", "Jorginho|2021": "trophy-laden, quiet",
  };
  const DEFAME_NOTE = {
    "Modrić": "A World Cup run, not a club season — the attention ran far ahead of the year itself.",
    "Bruyne": "One of the best midfield seasons going — and the conversation barely registered it.",
    "Yamal": "A 16-year-old phenomenon: the single largest unexplained gap anywhere in the data.",
  };
  const YEARS = [
    { year: "2018", best: "Lionel Messi", hype: "Luka Modrić", winner: "Luka Modrić", verdict: "The highest-narrative winner in the data — far more attention than his merit (20th in the field) explained — while Messi quietly had the best season. The complaint, confirmed." },
    { year: "2019", best: "Robert Lewandowski", hype: "Virgil van Dijk", winner: "Lionel Messi", verdict: "No real inflation this year: even the loudest extra buzz — Van Dijk's, at a modest +0.92 — sat well behind the field's best seasons. Messi won among the very best by production. A clean one." },
    { year: "2021", best: "Robert Lewandowski", hype: "Lionel Messi", winner: "Lionel Messi", verdict: "The textbook case. Lewandowski had the best season in the field — a record-breaking scorer — with almost no buzz, and finished second. The story edged the goals." },
    { year: "2022", best: "Kylian Mbappé", hype: "Karim Benzema", winner: "Karim Benzema", verdict: "Benzema took the vote on a Champions League run, while Mbappé out-produced everyone again. Earned, with a tailwind." },
    { year: "2023", best: "Lionel Messi", hype: "Lionel Messi", winner: "Lionel Messi", verdict: "Best season, most votes, and plenty of buzz on the back of a World Cup. Hard to call this one a robbery." },
    { year: "2024", best: "Mohamed Salah", hype: "Lamine Yamal", winner: "Rodri", verdict: "Rodri won ranked 14th on raw production — the holding midfielder whose value the box score can barely see, lifted by a treble narrative." },
    { year: "2025", best: "Mohamed Salah", hype: "Ousmane Dembélé", winner: "Ousmane Dembélé", verdict: "Dembélé won with little extra buzz; Salah had the best season of anyone and finished fourth." },
  ];

  const el = id => document.getElementById(id);
  const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // ---- "In plain numbers" (data-true) ----
  function fillHuman() {
    const e = D.effects; if (!e) return;
    const orA = e.gate_a_or.or, orB = e.gate_b_or.or, a = e.gate_a_ame;
    const base = Math.round(a.base_pct), lift = Math.round(a.mean);
    if (el("hm-or-a")) el("hm-or-a").textContent = orA.toFixed(1) + "×";
    if (el("hm-ame")) el("hm-ame").innerHTML = "+" + lift + '<span class="pts"> pts</span>';
    if (el("hm-range")) el("hm-range").textContent = "~" + base + "% to ~" + (base + lift) + "%";
    if (el("hm-or-b")) el("hm-or-b").textContent = orB.toFixed(2) + "×";
  }

  // ---- de-faming card (tabs + bars + readout) ----
  function renderDefame() {
    const host = el("defame-card"); if (!host) return;
    const ex = (D.defame || []).map(d => {
      const last = /Bruyne/.test(d.player) ? "De Bruyne" : d.player.split(" ").slice(-1)[0];
      const noteKey = Object.keys(DEFAME_NOTE).find(k => d.player.includes(k));
      return { ...d, last, pos: d.h_perp >= 0, note: noteKey ? DEFAME_NOTE[noteKey] : "" };
    });
    if (!ex.length) return;
    let cur = 0;
    host.innerHTML =
      '<div class="df-tabs" role="tablist">' +
      ex.map((d, i) => `<button class="df-tab" role="tab" data-i="${i}">${esc(d.last)} '${String(d.year).slice(2)}</button>`).join("") +
      '</div>' +
      '<div class="df-body">' +
      '  <div class="df-plot">' +
      '    <div class="df-bars">' +
      '      <div class="df-col"><div class="df-cap gold" id="df-acap"></div><div class="df-bar actual" id="df-abar" style="height:0"></div></div>' +
      '      <div class="df-col"><div class="df-cap muted" id="df-ecap"></div><div class="df-bar expected" id="df-ebar" style="height:0"></div></div>' +
      '    </div>' +
      '    <div class="df-xlab"><div>Actual attention</div><div>Merit + fame predict</div></div>' +
      '  </div>' +
      '  <div class="df-read">' +
      '    <div class="df-name" id="df-name"></div>' +
      '    <div class="df-year" id="df-year"></div>' +
      '    <div class="df-h"><span class="big" id="df-h"></span><span class="u">Hype Score H⊥</span></div>' +
      '    <div class="df-gap" id="df-gap"></div>' +
      '    <p class="df-note" id="df-note"></p>' +
      '  </div>' +
      '</div>';
    const tabs = [...host.querySelectorAll(".df-tab")];
    function sel(i) {
      cur = i;
      tabs.forEach((t, j) => t.setAttribute("aria-selected", j === i ? "true" : "false"));
      const d = ex[i], mx = Math.max(d.actual, d.expected) * 1.2, diff = Math.abs(d.actual - d.expected);
      el("df-acap").textContent = "≈ " + fmtN(d.actual) + " / day";
      el("df-ecap").textContent = "≈ " + fmtN(d.expected) + " / day";
      el("df-abar").style.height = (d.actual / mx * 100).toFixed(1) + "%";
      el("df-ebar").style.height = (d.expected / mx * 100).toFixed(1) + "%";
      el("df-name").textContent = d.player;
      el("df-year").textContent = d.year + " BALLON D'OR";
      el("df-h").textContent = sgn(d.h_perp); el("df-h").style.color = d.pos ? GOLD : COOL;
      el("df-gap").style.color = d.pos ? GOLD : COOL;
      el("df-gap").textContent = d.pos
        ? fmtN(diff) + " more views a day than merit and fame predict"
        : fmtN(diff) + " fewer views than predicted — buzz the season never drew";
      el("df-note").textContent = d.note;
    }
    tabs.forEach(t => t.addEventListener("click", () => sel(+t.dataset.i)));
    sel(0);
  }

  // ---- two-gate card ----
  function renderGates() {
    const host = el("gates-card"); if (!host) return;
    const A = D.headline.gateA, B = D.headline.gateB;
    const tick = p => `<div class="gate-tick" style="left:${p}%"></div>`;
    const row = (g, name, q, num, od, dotCol, rangeStyle, dotStyle) => {
      const dl = g.mean * POSX, rl = g.lo * POSX, rw = (g.hi - g.lo) * POSX;
      return (
        `<div class="gate-row" data-tip="${name}: ${sgn(g.mean)} · 94% CI [${sgn(g.lo)}, ${sgn(g.hi)}]">
          <div class="gate-top">
            <div><div class="gate-name">${name}</div><div class="gate-q">${q}</div></div>
            <div style="text-align:right;flex:none">
              <div class="gate-num" style="color:${num.c}">${num.t}</div>
              <div class="gate-od" style="color:${od.c}">${od.t}</div>
            </div>
          </div>
          <div class="gate-track">${tick(47.6)}${tick(95.2)}
            <div class="gate-range" style="left:${rl}%;width:${rw}%;${rangeStyle}"></div>
            <div class="gate-dot" style="left:${dl}%;${dotStyle}"></div>
          </div>
        </div>`);
    };
    host.innerHTML =
      `<div class="gates-head"><div class="l">Effect of +1 SD Hype Score · per-gate</div><div class="r">bars = 94% uncertainty range</div></div>` +
      row(A, "Gate A — getting noticed", "Do you make the 30-man shortlist?",
        { t: sgn(A.mean), c: GOLD }, { t: "≈ doubles the odds", c: GOLD },
        GOLD, "background:linear-gradient(90deg,rgba(201,164,76,0.18),rgba(201,164,76,0.4))",
        "width:17px;height:17px;background:var(--gold);box-shadow:0 0 16px rgba(201,164,76,0.55)") +
      row(B, "Gate B — finishing higher", "Given you're in, do you place above the rest?",
        { t: sgn(B.mean), c: INK }, { t: "a modest nudge", c: MUTED },
        INK, "background:rgba(232,222,202,0.16)", "width:15px;height:15px;background:var(--ink)") +
      `<div class="gate-axis"><span style="left:0">0</span><span style="left:47.6%;transform:translateX(-50%)">+0.5</span>` +
      `<span style="left:95.2%;transform:translateX(-50%)">+1.0</span><span style="right:0;color:var(--faint)">log-odds, per SD</span></div>`;
    host.querySelectorAll(".gate-row").forEach(r => bindTip(r, r.getAttribute("data-tip")));
  }

  // ---- leaderboard rows ----
  function renderLeaderboard() {
    const host = el("leaderboard-rows"); if (!host) return;
    const rows = (D.leaderboard || []).slice().sort((a, b) => b.h_perp - a.h_perp);
    const max = d3.max(rows, d => Math.abs(d.h_perp)) * 1.05 || 4;
    const F = 50 / max;
    host.className = "lb-rows";
    host.innerHTML = rows.map(r => {
      const pos = r.h_perp >= 0, w = Math.abs(r.h_perp) * F;
      const tag = DESC[`${r.player}|${r.year}`] || (pos ? "narrative excess" : "under the radar");
      const fill = `left:${pos ? 50 : 50 - w}%;width:${w}%;background:${pos ? HOT : COOL}`;
      const lab = pos ? `left:${50 + w}%;text-align:left` : `right:${50 + w}%;text-align:right`;
      return (
        `<div class="lb-row" data-tip="<b>${esc(r.player)}</b> · ${r.year}<br>Hype Score ${sgn(r.h_perp)} · finished #${r.rank}">
          <div class="lb-name"><div class="nm">${esc(r.player)}</div><div class="tag">${r.year} · ${esc(tag)}</div></div>
          <div class="lb-bar"><div class="lb-zero"></div>
            <div class="lb-fill" style="${fill}"></div>
            <div class="lb-val" style="${lab}">${sgn(r.h_perp)}</div></div>
        </div>`);
    }).join("");
    host.querySelectorAll(".lb-row").forEach(r => bindTip(r, r.getAttribute("data-tip")));
  }

  // ---- per-year rows (curated editorial) ----
  function renderPerYear() {
    const host = el("peryear-rows"); if (!host) return;
    host.innerHTML = YEARS.map(y => {
      const hypeCol = y.hype.startsWith("—") ? "var(--faint)" : "var(--hot)";
      return (
        `<div class="py-row">
          <div class="py-year">${y.year}</div>
          <div class="py-body">
            <div class="py-faces">
              <div><div class="py-flab">Best season</div><div class="py-fname">${esc(y.best)}</div></div>
              <div><div class="py-flab">Biggest story</div><div class="py-fname" style="color:${hypeCol}">${esc(y.hype)}</div></div>
              <div><div class="py-flab">Winner ●</div><div class="py-fname gold">${esc(y.winner)}</div></div>
            </div>
            <p class="py-verdict">${esc(y.verdict)}</p>
          </div>
        </div>`);
    }).join("");
  }

  // ---- robustness strips ----
  function renderRobust() {
    const host = el("robust-card"); if (!host) return;
    const SPECS = ["baseline", "no_duopoly", "drop_low_baseline", "window_leaky", "window_strict", "jackknife_year"];
    const LAB = { baseline: "main model", no_duopoly: "drop Messi & Ronaldo", drop_low_baseline: "drop low-fame",
      window_leaky: "window past ceremony", window_strict: "window before ceremony", jackknife_year: "leave a year out" };
    const byGate = g => (D.robustness || []).filter(r => r.gate === g && SPECS.includes(r.spec));
    const strip = (g, col, slab) => {
      const dots = byGate(g).map(r =>
        `<div class="rb-dot" style="left:${(r.estimate * POSX).toFixed(1)}%;background:${col};opacity:.8"
           data-tip="${LAB[r.spec] || r.spec}: ${sgn(r.estimate)}"></div>`).join("");
      return (
        `<div class="rb-strip">
          <div class="rb-slab" style="color:${col === GOLD ? "var(--gold)" : "var(--muted)"}"><span>${slab[0]}</span><span>${slab[1]}</span></div>
          <div class="rb-track"${col === GOLD ? ' style="background:linear-gradient(90deg,rgba(201,164,76,0) 60%,rgba(201,164,76,0.06))"' : ""}>${dots}</div>
        </div>`);
    };
    host.innerHTML =
      `<div class="rb-head">Re-estimated across specifications</div>` +
      strip("A_nomination", GOLD, ["GATE A — noticed", "clusters tight, far from 0"]) +
      strip("B_placement", INK, ["GATE B — placed", "small, grazes 0"]) +
      `<div class="rb-axis"><span style="left:0">0</span><span style="left:47.6%;transform:translateX(-50%)">+0.5</span><span style="left:95.2%;transform:translateX(-50%)">+1.0</span></div>` +
      `<p class="rb-note">Each dot is the Hype-Score effect from one re-run of the model — dropping Messi &amp; Ronaldo, dropping newcomers, leaving a year out, shifting the window. When the dots stay <strong>bunched and far from zero</strong> (Gate A), the result doesn't hinge on any single choice. Gate B's sit low and near zero — real, but slight.</p>`;
    host.querySelectorAll(".rb-dot").forEach(d => bindTip(d, d.getAttribute("data-tip")));
  }

  // ---- scatter (D3 SVG, distortion-free; redraws on resize) ----
  // Labelled markers — kept well-separated for legibility. (Rodri '24 sits almost exactly on
  // Kvaratskhelia '23, so it stays an unlabelled dot to avoid a collision.)
  const MARKERS = [["Modrić", 2018], ["Lewandowski", 2019], ["Messi", 2023],
    ["Kvaratskhelia", 2023], ["Yamal", 2024], ["Jorginho", 2021]];
  function drawScatter() {
    const host = el("scatter-plot"); if (!host) return;
    const pts = (D.scatter || []).filter(p => p.merit != null && p.attention != null);
    if (!pts.length) return;
    const W = host.clientWidth, H = host.clientHeight;
    if (!W || !H) return;
    const pad = { t: 14, r: 16, b: 16, l: 16 };
    const x = d3.scaleLinear().domain(d3.extent(pts, d => d.merit)).nice().range([pad.l, W - pad.r]);
    const y = d3.scaleLinear().domain(d3.extent(pts, d => d.attention)).nice().range([H - pad.b, pad.t]);

    d3.select(host).select("svg.scatter").remove();
    const s = d3.select(host).append("svg").attr("class", "scatter")
      .attr("viewBox", `0 0 ${W} ${H}`).attr("preserveAspectRatio", "none");

    const isMk = p => MARKERS.some(([n, yr]) => p.year === yr && p.player.includes(n));
    const ptTip = (d, cx, cy) => showTip(
      `<b>${esc(d.player)}</b> · ${d.year}<br>Hype Score ${sgn(d.h_perp)} · finished #${d.rank}`, cx, cy);

    const circ = s.selectAll("circle").data(pts).join("circle")
      .attr("cx", d => x(d.merit)).attr("cy", d => y(d.attention))
      .attr("r", d => isMk(d) ? 7 : 4)
      .attr("fill", d => hcol(d.h_perp))
      .attr("stroke", d => isMk(d) ? BG : "none").attr("stroke-width", d => isMk(d) ? 2 : 0);
    if (!MOBILE) {
      circ.style("cursor", "pointer")
        .on("mousemove", (e, d) => ptTip(d, e.clientX, e.clientY))
        .on("mouseleave", hideTip)
        .on("touchstart", (e, d) => { e.stopPropagation(); ptTip(d, e.touches[0].clientX, e.touches[0].clientY); });
    }

    // labelled markers: brighter (lightened) haloed text + leader line, with collision-avoidance.
    // On a narrow (phone) plot, only the 4 well-separated anchors are labelled to avoid crowding.
    const fewMarks = W < 520;
    const MK_MOBILE = new Set(["Messi", "Yamal", "Lewandowski", "Jorginho"]);
    const useMarkers = fewMarks ? MARKERS.filter(m => MK_MOBILE.has(m[0])) : MARKERS;
    const lighten = c => mix(c, INK, 0.5);   // keep the hue cue but lift it for legibility
    const mk = useMarkers.map(([n, yr]) => {
      const p = pts.find(d => d.year === yr && d.player.includes(n));
      if (!p) return null;
      const right = x(p.merit) > W * 0.62;
      return { p, px: x(p.merit), py: y(p.attention), right, col: lighten(hcol(p.h_perp)),
        lx: x(p.merit) + (right ? -14 : 14), ly: y(p.attention) + 4,
        txt: `${n} '${String(yr).slice(2)}`, anchor: right ? "end" : "start" };
    }).filter(Boolean);
    const drawn = mk.map(m => {
      const leader = s.append("line").attr("class", "mk-leader").attr("stroke", m.col).attr("opacity", 0.55);
      const t = s.append("text").attr("class", "mk").attr("text-anchor", m.anchor)
        .attr("fill", m.col).style("pointer-events", "none").text(m.txt);
      return { m, leader, t };
    });
    const place = () => drawn.forEach(o => {
      o.t.attr("x", o.m.lx).attr("y", o.m.ly);
      o.leader.attr("x1", o.m.px).attr("y1", o.m.py).attr("x2", o.m.lx).attr("y2", o.m.ly - 4)
        .style("opacity", Math.abs(o.m.ly - 4 - o.m.py) > 8 || Math.abs(o.m.lx - o.m.px) > 18 ? 0.55 : 0);
    });
    place();
    // nudge overlapping labels apart vertically using measured boxes
    const hit = (a, b) => a.x < b.x + b.width + 2 && b.x < a.x + a.width + 2 && a.y < b.y + b.height + 1 && b.y < a.y + a.height + 1;
    for (let it = 0; it < 8; it++) {
      let moved = false;
      for (let i = 0; i < drawn.length; i++) for (let j = i + 1; j < drawn.length; j++) {
        const a = drawn[i].t.node().getBBox(), b = drawn[j].t.node().getBBox();
        if (hit(a, b)) {
          const lo = a.y <= b.y ? drawn[j] : drawn[i];
          lo.m.ly = Math.min(H - 6, lo.m.ly + 9);
          lo.t.attr("y", lo.m.ly);
          lo.leader.attr("y2", lo.m.ly - 4)
            .style("opacity", Math.abs(lo.m.ly - 4 - lo.m.py) > 8 || Math.abs(lo.m.lx - lo.m.px) > 18 ? 0.55 : 0);
          moved = true;
        }
      }
      if (!moved) break;
    }
  }

  // ---- on-scroll reveal ----
  function initReveal() {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { threshold: 0.12 });
    document.querySelectorAll(".reveal").forEach(n => io.observe(n));
  }

  function start() {
    fillHuman();
    renderDefame();
    renderGates();
    renderLeaderboard();
    renderPerYear();
    renderRobust();
    drawScatter();
    initReveal();
    let rt;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(drawScatter, 200); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
