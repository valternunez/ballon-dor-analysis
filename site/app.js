/* Ballon d'Or — hype vs merit · scrollytelling charts (D3 v7 + scrollama) */
(function () {
  "use strict";
  const D = window.BDOR;
  if (!D) { console.error("data.js missing"); return; }

  const C = { ink: "#ece9e2", muted: "#9a968c", faint: "#615e57", line: "#26262f",
              accent: "#f5b301", hot: "#ff5a3c", cool: "#4aa3ff" };
  const fmtN = d3.format(",");
  const fmtS = d3.format("+.2f");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const DUR = reduce ? 0 : 750;

  // shared tooltip
  const tip = d3.select("body").append("div").attr("class", "tooltip");
  const showTip = (html, e) => tip.style("opacity", 1).html(html)
    .style("left", Math.min(e.clientX + 14, window.innerWidth - 250) + "px")
    .style("top", (e.clientY + 14) + "px");
  const hideTip = () => tip.style("opacity", 0);

  // diverging colour by Hype Score (positive = hot, negative = cool)
  const hAbs = d3.max(D.scatter, d => Math.abs(d.h_perp)) || 4;
  const colorH = d3.scaleDiverging(d3.interpolateRdBu).domain([hAbs, 0, -hAbs]);

  function svg(sel, w, h) {
    d3.select(sel).selectAll("*").remove();
    return d3.select(sel).append("svg").attr("viewBox", `0 0 ${w} ${h}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
  }

  /* ---------------- DE-FAMING (sticky, stepped) ----------------
     Built ONCE; each step only transitions what changed (the new bar / the gap), and switching the
     example player morphs the bars to the new values instead of restarting from zero. */
  const defameState = { step: 0 };
  let defame = null;
  const DF = { W: 720, H: 380, m: { t: 36, r: 30, b: 56, l: 60 }, bw: 130 };
  function drawDefame() {
    const yamal = D.defame.find(d => /Yamal/i.test(d.player));
    const dbr = D.defame.find(d => /Bruyne/i.test(d.player));
    const step = defameState.step;
    const cur = step >= 3 ? dbr : yamal;
    if (!cur) return;
    const { W, H, m, bw } = DF;
    const x = d3.scalePoint().domain(["actual", "expected"]).range([m.l, W - m.r]).padding(0.75);

    if (!defame) {
      const s = svg("#defame-chart", W, H);
      const baseY = H - m.b;
      const mk = (cls, fill) => s.append("rect").attr("width", bw).attr("rx", 4).attr("fill", fill)
        .attr("y", baseY).attr("height", 0);
      const txt = (cls) => s.append("text").attr("text-anchor", "middle").attr("class", cls).attr("opacity", 0);
      defame = {
        s, baseY,
        title: s.append("text").attr("x", W / 2).attr("y", 20).attr("text-anchor", "middle")
          .attr("class", "lab title").attr("fill", C.muted),
        actual: mk("a", C.ink).attr("x", x("actual") - bw / 2),
        aLab: txt("lab").attr("x", x("actual")),
        exp: mk("e", C.faint).attr("x", x("expected") - bw / 2).attr("opacity", 0),
        eLab: txt("lab").attr("x", x("expected")),
        gapLine: s.append("line").attr("stroke-width", 3).attr("opacity", 0),
        gapText: s.append("text").attr("class", "lab").attr("opacity", 0),
      };
      s.append("text").attr("x", x("actual")).attr("y", baseY + 26).attr("text-anchor", "middle")
        .attr("class", "lab sm").text("actual attention");
      s.append("text").attr("x", x("expected")).attr("y", baseY + 26).attr("text-anchor", "middle")
        .attr("class", "lab sm").text("merit + fame expected");
    }

    const d = defame, base = d.baseY;
    const maxv = Math.max(cur.actual, cur.expected) * 1.18;
    const y = d3.scaleLinear().domain([0, maxv]).range([base, m.t]);
    const showExp = step >= 1, showGap = step >= 2;
    const positive = cur.actual >= cur.expected;
    const T = () => d3.transition().duration(DUR);

    d.title.text(`${cur.player} · ${cur.year} award — daily Wikipedia views`);
    d.actual.transition(T()).attr("y", y(cur.actual)).attr("height", base - y(cur.actual));
    d.aLab.text(fmtN(Math.round(cur.actual))).transition(T())
      .attr("y", y(cur.actual) - 10).attr("opacity", 1);
    d.exp.transition(T()).attr("opacity", showExp ? 1 : 0)
      .attr("y", showExp ? y(cur.expected) : base).attr("height", showExp ? base - y(cur.expected) : 0);
    d.eLab.text(fmtN(Math.round(cur.expected))).transition(T())
      .attr("y", y(cur.expected) - 10).attr("opacity", showExp ? 1 : 0);

    const gx = x("actual") + bw / 2 + 12, top = y(cur.actual), expY = y(cur.expected);
    d.gapLine.attr("stroke", positive ? C.accent : C.cool)
      .transition(T()).attr("x1", gx).attr("x2", gx).attr("y1", expY).attr("y2", top)
      .attr("opacity", showGap ? 1 : 0);
    d.gapText.attr("x", gx + 8).attr("y", (top + expY) / 2).style("fill", positive ? C.accent : C.cool)
      .text(positive ? `Hype Score +${cur.h_perp} — the story` : `Hype Score ${cur.h_perp} — under-hyped`)
      .transition(T()).attr("opacity", showGap ? 1 : 0);
  }

  /* ---------------- LEADERBOARD (diverging bars) ---------------- */
  function drawLeaderboard() {
    const rows = D.leaderboard.slice().sort((a, b) => a.h_perp - b.h_perp);
    const W = 720, rh = 26, m = { t: 10, r: 20, b: 34, l: 215 };
    const H = m.t + m.b + rows.length * rh;
    const s = svg("#leaderboard-chart", W, H);
    const x = d3.scaleLinear().domain(d3.extent(rows, d => d.h_perp)).nice().range([m.l, W - m.r]);
    const y = d3.scaleBand().domain(rows.map(d => d.player + d.year)).range([m.t, H - m.b]).padding(0.22);
    const col = d => d.kind === "narrative excess" ? C.hot : C.cool;

    s.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(6));
    s.append("line").attr("class", "zero").attr("x1", x(0)).attr("x2", x(0))
      .attr("y1", m.t).attr("y2", H - m.b);

    s.selectAll("rect").data(rows).join("rect")
      .attr("y", d => y(d.player + d.year)).attr("height", y.bandwidth()).attr("rx", 3)
      .attr("x", x(0)).attr("width", 0).attr("fill", col)
      .on("mousemove", (e, d) => showTip(
        `<b>${d.player}</b> · ${d.year}<br>Hype Score ${fmtS(d.h_perp)} · finished #${d.rank}`, e))
      .on("mouseleave", hideTip)
      .transition().duration(DUR).delay((d, i) => i * 8)
      .attr("x", d => Math.min(x(0), x(d.h_perp)))
      .attr("width", d => Math.abs(x(d.h_perp) - x(0)));

    s.selectAll("text.name").data(rows).join("text").attr("class", "lab")
      .attr("x", m.l - 14).attr("y", d => y(d.player + d.year) + y.bandwidth() / 2 + 4)
      .attr("text-anchor", "end").text(d => `${d.player} '${String(d.year).slice(2)}`);
  }

  /* ---------------- TWO-GATE FOREST (sticky, stepped) ----------------
     Built ONCE; each gate animates in exactly once (the step that reveals it). Already-shown gates
     are left untouched, so scrolling never re-animates them from zero. */
  const gateState = { step: 0 };
  let forest = null;
  function drawForest() {
    const W = 720, H = 320, m = { t: 30, r: 40, b: 52, l: 190 };
    const x = d3.scaleLinear().domain([0, 1.05]).range([m.l, W - m.r]);
    const gates = [
      { key: "Gate A — nomination", sub: "get noticed", d: D.headline.gateA, col: C.accent },
      { key: "Gate B — placement", sub: "finish higher", d: D.headline.gateB, col: C.hot },
    ];
    const y = d3.scalePoint().domain(gates.map(g => g.key)).range([m.t + 44, H - m.b - 22]).padding(0.5);

    if (!forest) {
      const s = svg("#gates-chart", W, H);
      s.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
        .call(d3.axisBottom(x).ticks(6));
      s.append("line").attr("class", "zero").attr("x1", x(0)).attr("x2", x(0))
        .attr("y1", m.t).attr("y2", H - m.b);
      forest = { s, groups: {}, shown: new Set() };
      gates.forEach(g => {
        const yy = y(g.key), grp = s.append("g").attr("opacity", 0);
        grp.append("text").attr("x", m.l - 16).attr("y", yy - 5).attr("text-anchor", "end")
          .attr("class", "lab").text(g.key);
        grp.append("text").attr("x", m.l - 16).attr("y", yy + 15).attr("text-anchor", "end")
          .attr("class", "lab sm").text(g.sub);
        forest.groups[g.key] = {
          grp, g, yy,
          line: grp.append("line").attr("y1", yy).attr("y2", yy).attr("stroke", g.col)
            .attr("stroke-width", 3).attr("x1", x(0)).attr("x2", x(0)),
          dot: grp.append("circle").attr("cy", yy).attr("r", 8).attr("fill", g.col).attr("cx", x(0)),
          lab: grp.append("text").attr("y", yy - 16).attr("class", "lab").style("fill", g.col)
            .attr("text-anchor", "middle").attr("x", x(0)).attr("opacity", 0).text(fmtS(g.d.mean)),
        };
      });
      forest.note = s.append("text").attr("x", W / 2).attr("y", H - 8).attr("text-anchor", "middle")
        .attr("class", "lab sm").attr("fill", C.muted).attr("opacity", 0)
        .text("Narrative's pull on getting noticed is ~5× its pull on placement.");
    }

    const reveal = key => {
      if (forest.shown.has(key)) return;
      forest.shown.add(key);
      const o = forest.groups[key];
      o.grp.transition().duration(DUR).attr("opacity", 1);
      o.line.transition().duration(DUR).attr("x1", x(o.g.d.lo)).attr("x2", x(o.g.d.hi));
      o.dot.transition().duration(DUR).attr("cx", x(o.g.d.mean));
      o.lab.transition().delay(DUR / 2).duration(DUR).attr("x", x(o.g.d.mean)).attr("opacity", 1);
    };
    if (gateState.step >= 1) reveal("Gate A — nomination");
    if (gateState.step >= 2) reveal("Gate B — placement");
    forest.note.transition().duration(DUR).attr("opacity", gateState.step >= 3 ? 1 : 0);
  }

  /* ---------------- PER-YEAR SCOREBOARD (sticky, stepped) ----------------
     One step per award year. Three faces: who played best (top merit), who actually won, who drew
     the most attention BEYOND merit (top Hype Score). Built ONCE; each step swaps with a fade. */
  const perYearState = { step: 0 };
  let peryear = null;
  const PY = { W: 760, H: 392 };
  function drawPerYear() {
    const data = D.per_year;
    if (!data || !data.length) return;
    const yr = data[Math.max(0, Math.min(data.length - 1, perYearState.step))];
    const { W, H } = PY;
    const cols = [
      { key: "best_season", role: "BEST SEASON", sub: "top on-pitch merit", col: C.cool, stat: "merit_z", pre: "merit " },
      { key: "winner", role: "THE WINNER", sub: "took the trophy", col: C.accent, stat: null, pre: "" },
      { key: "most_hyped", role: "MOST OVER-HYPED", sub: "top Hype Score (buzz beyond merit)", col: C.hot, stat: "h_perp", pre: "Hype " },
    ];
    const cxs = cols.map((_, i) => W * (i * 2 + 1) / 6);

    if (!peryear) {
      const s = svg("#peryear-chart", W, H);
      const title = s.append("text").attr("x", W / 2).attr("y", 26).attr("text-anchor", "middle")
        .attr("class", "lab title").attr("fill", C.ink).attr("font-size", 22);
      const groups = cols.map((c, i) => {
        const g = s.append("g").attr("transform", `translate(${cxs[i]},0)`);
        g.append("text").attr("y", 92).attr("text-anchor", "middle").attr("class", "lab")
          .style("fill", c.col).attr("letter-spacing", "1.5px").attr("font-size", 12).text(c.role);
        g.append("text").attr("y", 110).attr("text-anchor", "middle").attr("class", "lab sm")
          .style("fill", C.faint).text(c.sub);
        return {
          card: g.append("rect").attr("x", -108).attr("y", 128).attr("width", 216).attr("height", 150)
            .attr("rx", 10).attr("fill", "rgba(255,255,255,0.02)").attr("stroke", c.col)
            .attr("stroke-opacity", 0.35),
          name: g.append("text").attr("y", 178).attr("text-anchor", "middle").attr("class", "lab")
            .attr("fill", C.ink).attr("font-size", 18),
          finish: g.append("text").attr("y", 214).attr("text-anchor", "middle").attr("class", "lab")
            .attr("fill", C.muted).attr("font-size", 14),
          stat: g.append("text").attr("y", 250).attr("text-anchor", "middle").attr("class", "lab")
            .style("fill", c.col).attr("font-size", 15),
        };
      });
      const verdict = s.append("text").attr("x", W / 2).attr("y", H - 14).attr("text-anchor", "middle")
        .attr("class", "lab sm").attr("fill", C.muted);
      peryear = { s, title, groups, verdict };
    }

    const ord = ["1st", "2nd", "3rd"];
    const place = n => ord[n - 1] || `${n}th`;
    const py = peryear;
    py.title.text(`The ${yr.year} Ballon d'Or`);
    cols.forEach((c, i) => {
      const f = yr[c.key], g = py.groups[i];
      g.name.transition().duration(DUR / 2).attr("opacity", 0).transition().duration(DUR / 2)
        .attr("opacity", 1).text(f.player);
      g.finish.text(`finished ${place(f.rank)}`);
      g.stat.text(c.stat ? `${c.pre}${fmtS(f[c.stat])}` : `merit ${fmtS(f.merit_z)} · Hype ${fmtS(f.h_perp)}`);
    });
    const w = yr.winner;
    const verdict = w.merit_rank === 1 ? "The best season won — merit and trophy agree."
      : w.hype_rank === 1 ? "The most over-hyped player (top Hype Score) won."
      : `The winner ranked #${w.merit_rank} on merit and #${w.hype_rank} on Hype Score — voted up from the middle of both.`;
    py.verdict.transition().duration(DUR).attr("opacity", 0).transition().duration(DUR)
      .attr("opacity", 1).text(verdict);
  }

  /* ---------------- MERIT vs ATTENTION (scatter) ---------------- */
  function drawScatter() {
    const W = 720, H = 460, m = { t: 20, r: 24, b: 46, l: 52 };
    const pts = D.scatter;
    const s = svg("#scatter-chart", W, H);
    const x = d3.scaleLinear().domain(d3.extent(pts, d => d.merit)).nice().range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain(d3.extent(pts, d => d.attention)).nice().range([H - m.b, m.t]);
    s.append("g").attr("class", "axis grid").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(7).tickSize(-(H - m.t - m.b)));
    s.append("g").attr("class", "axis grid").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(6).tickSize(-(W - m.l - m.r)));
    s.append("text").attr("x", W / 2).attr("y", H - 8).attr("text-anchor", "middle")
      .attr("class", "lab sm").text("merit  (role-adjusted, higher = better season)  →");
    s.append("text").attr("transform", `translate(14,${H / 2}) rotate(-90)`)
      .attr("text-anchor", "middle").attr("class", "lab sm").text("attention (log) →");

    s.selectAll("circle").data(pts).join("circle")
      .attr("cx", d => x(d.merit)).attr("cy", d => y(d.attention)).attr("r", 0)
      .attr("fill", d => colorH(d.h_perp)).attr("stroke", "#0c0c10").attr("stroke-width", 0.5)
      .on("mousemove", (e, d) => showTip(
        `<b>${d.player}</b> · ${d.year}<br>Hype Score ${fmtS(d.h_perp)} · finished #${d.rank}`, e))
      .on("mouseleave", hideTip)
      .transition().duration(DUR).delay((d, i) => i * 4).attr("r", 5);

    [["Messi", 2023], ["Lewandowski", 2019]].forEach(([nm, yr]) => {
      const p = pts.find(d => d.year === yr && d.player.includes(nm));
      if (!p) return;
      s.append("text").attr("x", x(p.merit) + 8).attr("y", y(p.attention) - 8)
        .attr("class", "lab").attr("opacity", 0).text(`${nm} '${String(yr).slice(2)}`)
        .transition().delay(DUR).duration(DUR).attr("opacity", 1);
    });
  }

  /* ---------------- ROBUSTNESS (caterpillar, grouped by gate) ----------------
     Two colour-coded blocks (Gate A amber, Gate B red); every stress-test gets its own clean row.
     The coloured gate headings double as the legend, so there's no separate legend chip. */
  function drawRobust() {
    const specOrder = ["baseline", "no_duopoly", "drop_low_baseline", "window_leaky", "jackknife_year"];
    const LABEL = {
      baseline: "main model",
      no_duopoly: "drop Messi & Ronaldo",
      drop_low_baseline: "drop low-fame players",
      window_leaky: "window past the ceremony",
      window_strict: "window before the ceremony",
      jackknife_year: "leave each year out",
    };
    const groups = [
      { gate: "A_nomination", title: "GATE A — getting noticed", sub: "getting noticed", col: C.accent },
      { gate: "B_placement", title: "GATE B — finishing higher", sub: "finishing higher", col: C.hot },
    ];
    const byKey = {};
    D.robustness.forEach(r => { byKey[`${r.gate}|${r.spec}`] = r; });

    const W = 720, m = { t: 16, r: 24, b: 40, l: 184 };
    const headerH = 30, rowH = 28, groupGap = 22, startY = m.t + 6;
    // lay out a gate heading then one row per spec, top to bottom
    const layout = [];
    let cy = startY;
    groups.forEach(grp => {
      layout.push({ type: "header", y: cy + 16, grp });
      cy += headerH;
      specOrder.forEach(spec => {
        const r = byKey[`${grp.gate}|${spec}`];
        if (!r) return;
        layout.push({ type: "row", y: cy + rowH / 2, spec, r, grp });
        cy += rowH;
      });
      cy += groupGap;
    });
    const H = cy - groupGap + m.b;

    const allRows = layout.filter(l => l.type === "row").map(l => l.r);
    const s = svg("#robust-chart", W, H);
    const x = d3.scaleLinear()
      .domain([Math.min(0, d3.min(allRows, d => d.ci_low)) - 0.05, d3.max(allRows, d => d.ci_high) + 0.05])
      .range([m.l, W - m.r]);

    s.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(6));
    s.append("line").attr("class", "zero").attr("x1", x(0)).attr("x2", x(0))
      .attr("y1", m.t).attr("y2", H - m.b);

    layout.forEach(item => {
      if (item.type === "header") {
        s.append("text").attr("x", 4).attr("y", item.y).attr("class", "lab")
          .style("fill", item.grp.col).attr("font-size", 13).attr("letter-spacing", "0.6px")
          .text(item.grp.title);
        return;
      }
      const { r, grp } = item, yy = item.y, col = grp.col;
      s.append("text").attr("x", m.l - 12).attr("y", yy + 4).attr("text-anchor", "end")
        .attr("class", "lab sm").text(LABEL[item.spec] || item.spec.replace(/_/g, " "));
      const g = s.append("g").attr("opacity", 0)
        .on("mousemove", (e) => showTip(
          `<b>${grp.sub}</b> · ${LABEL[item.spec] || item.spec}<br>` +
          `Hype Score ${fmtS(r.estimate)} · [${fmtS(r.ci_low)}, ${fmtS(r.ci_high)}]`, e))
        .on("mouseleave", hideTip);
      g.append("line").attr("x1", x(r.ci_low)).attr("x2", x(r.ci_high)).attr("y1", yy).attr("y2", yy)
        .attr("stroke", col).attr("stroke-width", 2);
      g.append("circle").attr("cx", x(r.estimate)).attr("cy", yy).attr("r", 4.5).attr("fill", col);
      g.transition().duration(DUR).attr("opacity", 1);
    });
  }

  /* ---------------- PAGEVIEW SPIKE ---------------- */
  function drawSpike() {
    const sp = D.spike;
    const W = 720, H = 340, m = { t: 20, r: 20, b: 40, l: 56 };
    const data = sp.dates.map((d, i) => ({ date: new Date(d), v: sp.views[i] }));
    const s = svg("#spike-chart", W, H);
    const x = d3.scaleTime().domain(d3.extent(data, d => d.date)).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, d3.max(data, d => d.v) * 1.08]).range([H - m.b, m.t]);
    s.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(6));
    s.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(d3.format("~s")));

    const area = d3.area().x(d => x(d.date)).y0(y(0)).y1(d => y(d.v)).curve(d3.curveMonotoneX);
    const line = d3.line().x(d => x(d.date)).y(d => y(d.v)).curve(d3.curveMonotoneX);
    s.append("path").datum(data).attr("fill", "rgba(245,179,1,0.12)").attr("d", area);
    const path = s.append("path").datum(data).attr("fill", "none").attr("stroke", C.accent)
      .attr("stroke-width", 2).attr("d", line);
    if (!reduce) {
      const L = path.node().getTotalLength();
      path.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L)
        .transition().duration(DUR * 2).attr("stroke-dashoffset", 0);
    }
    const marks = [["perf_start", "window start", C.muted], ["hype_cut", "shortlist cut", C.accent],
                   ["ceremony_date", "ceremony", C.hot]];
    marks.forEach(([k, lab, col], i) => {
      const dt = new Date(sp.markers[k]);
      if (dt < data[0].date || dt > data[data.length - 1].date) return;
      s.append("line").attr("x1", x(dt)).attr("x2", x(dt)).attr("y1", m.t).attr("y2", H - m.b)
        .attr("stroke", col).attr("stroke-dasharray", "4 4");
      // stagger labels so the close-together shortlist/ceremony markers don't overlap
      s.append("text").attr("x", x(dt)).attr("y", m.t - 6 - (i % 2) * 15).attr("text-anchor", "middle")
        .attr("class", "lab sm").style("fill", col).text(lab);
    });
  }

  /* ---------------- wiring: scrollama + intersection observers ---------------- */
  function initScrolly(section, state, draw) {
    draw();
    scrollama().setup({ step: `${section} .step`, offset: 0.6 })
      .onStepEnter(res => {
        d3.selectAll(`${section} .step`).classed("is-active", (d, i, n) => n[i] === res.element);
        state.step = +res.element.dataset.step; draw();
      });
  }

  function onView(sel, fn) {
    const el = document.querySelector(sel);
    if (!el) return;
    const io = new IntersectionObserver((es) => es.forEach(e => {
      if (e.isIntersecting) { fn(); io.disconnect(); }
    }), { threshold: 0.25 });
    io.observe(el);
  }

  /* deck navigation: one wheel / key / swipe gesture advances exactly one panel.
     Desktop only and skipped under reduced-motion — the CSS scroll-snap is the graceful fallback. */
  function initDeck() {
    if (reduce || window.matchMedia("(pointer: coarse), (max-width: 760px)").matches) return;
    const panels = Array.from(document.querySelectorAll("[data-panel], .step"));
    if (panels.length < 2) return;
    let locked = false;
    const current = () => {
      const mid = innerHeight / 2;
      let best = 0, bd = Infinity;
      panels.forEach((p, i) => {
        const r = p.getBoundingClientRect();
        const d = Math.abs(r.top + r.height / 2 - mid);
        if (d < bd) { bd = d; best = i; }
      });
      return best;
    };
    const lock = ms => { locked = true; setTimeout(() => { locked = false; }, ms); };
    const go = dir => {
      if (locked) return;
      const vh = innerHeight;
      const r = panels[current()].getBoundingClientRect();
      // a panel taller than the viewport scrolls WITHIN itself first, then advances (fullPage-style)
      if (dir > 0 && r.bottom > vh + 6) {
        lock(560); scrollBy({ top: Math.min(vh * 0.85, r.bottom - vh), behavior: "smooth" }); return;
      }
      if (dir < 0 && r.top < -6) {
        lock(560); scrollBy({ top: -Math.min(vh * 0.85, -r.top), behavior: "smooth" }); return;
      }
      const i = Math.max(0, Math.min(panels.length - 1, current() + dir));
      lock(780);
      panels[i].scrollIntoView({ behavior: "smooth", block: "start" });
    };
    addEventListener("wheel", e => {
      if (Math.abs(e.deltaY) < 4) return;
      e.preventDefault();
      go(e.deltaY > 0 ? 1 : -1);
    }, { passive: false });
    addEventListener("keydown", e => {
      if (["ArrowDown", "PageDown", " "].includes(e.key)) { e.preventDefault(); go(1); }
      else if (["ArrowUp", "PageUp"].includes(e.key)) { e.preventDefault(); go(-1); }
    });
    let ty = null;
    addEventListener("touchstart", e => { ty = e.touches[0].clientY; }, { passive: true });
    addEventListener("touchend", e => {
      if (ty != null && Math.abs(ty - e.changedTouches[0].clientY) > 40)
        go(ty - e.changedTouches[0].clientY > 0 ? 1 : -1);
      ty = null;
    }, { passive: true });
  }

  /* Plain-language effect sizes under the gates headline (kept in sync with the model via data.js). */
  function fillEffects() {
    const e = D.effects, el = document.getElementById("gates-plain");
    if (!e || !el) return;
    const a = e.gate_a_ame, orA = e.gate_a_or.or, orB = e.gate_b_or.or;
    const base = Math.round(a.base_pct), lift = Math.round(a.mean);
    el.innerHTML =
      `In plain terms: at equal merit and team success, a step up in Hype Score about ` +
      `<strong>${orA.toFixed(1)}×s the odds</strong> of making the 30 — roughly ` +
      `<strong>+${lift} points</strong> of probability, from ~${base}% to ~${base + lift}% — but ` +
      `adds only about <strong>${Math.round((orB - 1) * 100)}%</strong> to the odds once voting starts.`;
  }

  function start() {
    fillEffects();
    initScrolly("#defame", defameState, drawDefame);
    initScrolly("#gates", gateState, drawForest);
    initScrolly("#per-year", perYearState, drawPerYear);
    onView("#leaderboard-chart", drawLeaderboard);
    onView("#scatter-chart", drawScatter);
    onView("#robust-chart", drawRobust);
    onView("#spike-chart", drawSpike);
    initDeck();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
