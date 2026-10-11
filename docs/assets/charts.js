/* Figures. All data comes from window.SITE_DATA (assets/data.js).
   Look: pgfplots-style closed frame, inward ticks, boxed legend, serif labels. */
(function () {
  const D = window.SITE_DATA;
  if (!D || !window.d3) return;
  const $ = (s, r = document) => r.querySelector(s);

  const CLS = D.classes;                                // fixed order = fixed colour slots
  const LABEL = Object.fromEntries([...D.classes, ...D.subclasses].map(c => [c.key, c.label]));
  const SHORT = { lattice: 'Lattices', ecdlp: 'ECDLP', code: 'Codes', factoring: 'Factoring', isogeny: 'Isogenies', mq: 'Multivariate', mlwe: 'MLWE', lwe: 'Plain LWE' };
  const col = k => `var(--s-${k})`;
  const YEARS = D.years;

  const fmt = {
    n0: d3.format(',.0f'), n1: v => d3.format(',.1f')(Math.round((v + 1e-9) * 10) / 10),
    usd: v => v >= 1e9 ? '$' + d3.format('.3~g')(v / 1e9) + 'B' : v >= 1e6 ? '$' + d3.format('.3~g')(v / 1e6) + 'M'
      : v >= 1e3 ? '$' + d3.format('.3~g')(v / 1e3) + 'k' : '$' + d3.format(',.0f')(v),
    tok: v => v >= 1e12 ? d3.format('.2~r')(v / 1e12) + 'T' : v >= 1e9 ? d3.format('.2~r')(v / 1e9) + 'B' : d3.format('.2~r')(v / 1e6) + 'M',
  };
  const sum = a => a.reduce((x, y) => x + y, 0);
  const cumsum = a => { let s = 0; return a.map(v => (s += v)); };
  const movavg = a => a.map((_, i) => { const w = a.slice(Math.max(0, i - 1), i + 2); return sum(w) / w.length; });

  // ---------- shared plumbing ----------
  function segState(fig, name, initial, onChange) {
    const seg = fig.querySelector(`.seg[data-ctl="${name}"]`);
    let v = initial;
    if (seg) seg.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      seg.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
      v = b.dataset.v; onChange(v);
    });
    return () => v;
  }
  function tooltip(container) {
    let t = container.querySelector('.tip');
    if (!t) { t = document.createElement('div'); t.className = 'tip'; container.appendChild(t); }
    return {
      show(html, x, y) {
        t.innerHTML = html; t.classList.add('on');
        const cw = container.clientWidth, tw = t.offsetWidth, th = t.offsetHeight;
        let left = x + 16; if (left + tw > cw) left = x - tw - 16;
        t.style.left = Math.max(0, left) + 'px'; t.style.top = Math.max(0, y - th / 2) + 'px';
      },
      hide() { t.classList.remove('on'); },
    };
  }
  function frame(g, w, h) {
    g.append('rect').attr('class', 'frame').attr('width', w).attr('height', h);
  }
  // pgfplots ticks: inward, on both opposite sides
  function xTicks(g, x, h, ticks, f) {
    const t = g.append('g').attr('class', 'xt');
    ticks.forEach(v => {
      const px = x(v);
      const k = t.append('g').attr('class', 'tick').attr('transform', `translate(${px},0)`);
      k.append('line').attr('y1', h).attr('y2', h - 5);
      k.append('line').attr('y1', 0).attr('y2', 5);
      k.append('text').attr('y', h + 18).attr('text-anchor', 'middle').text(f(v));
    });
  }
  function yTicks(g, y, w, ticks, f, grid = true) {
    const t = g.append('g');
    if (grid) g.insert('g', ':first-child').attr('class', 'grid').selectAll('line').data(ticks).join('line')
      .attr('x1', 0).attr('x2', w).attr('y1', d => y(d)).attr('y2', d => y(d));
    ticks.forEach(v => {
      const k = t.append('g').attr('class', 'tick').attr('transform', `translate(0,${y(v)})`);
      k.append('line').attr('x1', 0).attr('x2', 5);
      k.append('line').attr('x1', w).attr('x2', w - 5);
      k.append('text').attr('x', -8).attr('dy', '0.32em').attr('text-anchor', 'end').text(f(v));
    });
  }
  function legend(g, items, x0, y0, hidden, onToggle) {
    const L = g.append('g').attr('class', 'legend').attr('transform', `translate(${x0},${y0})`);
    const box = L.append('rect').attr('class', 'box');
    const rows = L.selectAll('g.item').data(items).join('g').attr('class', d => 'item' + (hidden.has(d.key) ? ' off' : ''))
      .attr('transform', (d, i) => `translate(10,${14 + i * 19})`)
      .attr('role', 'button').attr('tabindex', 0).attr('aria-label', d => `toggle ${d.label}`)
      .on('click', (e, d) => onToggle(d.key))
      .on('keydown', (e, d) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(d.key); } });
    rows.append('rect').attr('x', -4).attr('y', -9).attr('width', 1).attr('height', 18).attr('fill', 'transparent');
    rows.append('line').attr('x1', 0).attr('x2', 18).attr('stroke', d => d.color).attr('stroke-width', d => d.mark === 'dot' ? 0 : 2);
    rows.filter(d => d.mark === 'dot').append('circle').attr('cx', 9).attr('r', 4.5).attr('fill', d => d.color).attr('stroke', d => d.stroke || 'none').attr('stroke-width', 1.5);
    rows.append('text').attr('x', 25).attr('dy', '0.34em').text(d => d.label);
    const bb = L.node().getBBox();
    box.attr('x', 0).attr('y', 0).attr('width', bb.width + 18).attr('height', items.length * 19 + 8);
    rows.select('rect').attr('width', bb.width + 14);
    return L;
  }
  // nudge end labels apart (simple 1-D relaxation)
  function spread(labels, minGap, lo, hi) {
    labels.sort((a, b) => a.y - b.y);
    for (let it = 0; it < 60; it++) {
      let moved = false;
      for (let i = 1; i < labels.length; i++) {
        const d = labels[i].y - labels[i - 1].y;
        if (d < minGap) { const s = (minGap - d) / 2; labels[i].y += s; labels[i - 1].y -= s; moved = true; }
      }
      labels.forEach(l => { l.y = Math.max(lo, Math.min(hi, l.y)); });
      if (!moved) break;
    }
    return labels;
  }
  function dataTable(fig, head, rows) {
    let box = fig.querySelector('.datatable');
    if (!box) { box = document.createElement('div'); box.className = 'datatable'; fig.querySelector('.fig-foot').after(box); }
    box.innerHTML = `<table class="booktabs"><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function wireFoot(fig, getTable) {
    const tb = fig.querySelector('[data-table]'), sv = fig.querySelector('[data-png]');
    const updateTable = () => { const [h, r] = getTable(); dataTable(fig, h, r); };
    if (tb) tb.addEventListener('click', () => {
      updateTable();
      const box = fig.querySelector('.datatable'); box.classList.toggle('on');
      tb.textContent = box.classList.contains('on') ? 'hide data' : 'show data';
    });
    fig.addEventListener('click', e => {
      if (e.target.closest('[data-ctl]') && fig.querySelector('.datatable.on')) updateTable();
    });
    if (sv) sv.addEventListener('click', () => saveSVG(fig.querySelector('.chart svg'), fig.id));
  }
  // inline computed styles so the exported SVG renders without the page CSS
  function saveSVG(svg, name) {
    const clone = svg.cloneNode(true);
    const src = svg.querySelectorAll('*'), dst = clone.querySelectorAll('*');
    const props = ['fill', 'stroke', 'stroke-width', 'opacity', 'font-family', 'font-size', 'font-style', 'font-weight', 'stroke-dasharray', 'stroke-linecap', 'stroke-linejoin'];
    src.forEach((n, i) => { const cs = getComputedStyle(n); dst[i].setAttribute('style', props.map(p => `${p}:${cs.getPropertyValue(p)}`).join(';')); });
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.insertAdjacentHTML('afterbegin', `<rect width="100%" height="100%" fill="${getComputedStyle(document.body).backgroundColor}"/>`);
    const blob = new Blob([clone.outerHTML], { type: 'image/svg+xml' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name + '.svg'; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function onResize(fn) {
    let w = 0, t;
    const ro = new ResizeObserver(es => { const nw = Math.round(es[0].contentRect.width); if (nw !== w) { w = nw; clearTimeout(t); t = setTimeout(fn, 60); } });
    return el => ro.observe(el);
  }

  // ---------- generic multi-series line chart ----------
  function lineChart(fig, opts) {
    const box = fig.querySelector('.chart');
    const hidden = new Set(opts.hidden || []);
    const tip = tooltip(box);
    function render() {
      const cfg = opts.get();
      const W = box.clientWidth, narrow = W < 560;
      const M = { t: 12, r: narrow ? 12 : 92, b: 46, l: 56 };
      const H = Math.max(300, Math.min(440, W * 0.5));
      const w = W - M.l - M.r, h = H - M.t - M.b;
      d3.select(box).select('svg').remove();
      const svg = d3.select(box).insert('svg', '.tip').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', opts.aria);
      const g = svg.append('g').attr('transform', `translate(${M.l},${M.t})`);
      const yrs = YEARS.filter(y => y >= cfg.from);
      const i0 = YEARS.indexOf(cfg.from);
      const series = cfg.series.map(s => ({ ...s, v: s.values.slice(i0) }));
      const vis = series.filter(s => !hidden.has(s.key));
      const x = d3.scaleLinear().domain([cfg.from, YEARS[YEARS.length - 1]]).range([0, w]);
      const ymax = d3.max(vis.flatMap(s => s.v)) || 1;
      const y = cfg.log ? d3.scaleLog().domain([1, ymax * 1.3]).range([h, 0]).clamp(true)
                        : d3.scaleLinear().domain([0, ymax * 1.08]).nice(5).range([h, 0]);
      const yt = cfg.log ? y.ticks(4).filter(v => [1, 10, 100, 1000, 10000].includes(v)) : y.ticks(5);
      yTicks(g, y, w, yt, cfg.log ? d3.format(',') : fmt.n0);
      xTicks(g, x, h, d3.range(Math.ceil(cfg.from / 10) * 10, 2030, 10).filter(v => v <= YEARS[YEARS.length - 1]), String);
      frame(g, w, h);
      g.append('text').attr('class', 'axis-label').attr('transform', `translate(${-44},${h / 2}) rotate(-90)`).attr('text-anchor', 'middle').text(cfg.yLabel);
      g.append('text').attr('class', 'axis-label').attr('x', w / 2).attr('y', h + 38).attr('text-anchor', 'middle').text('year');

      const clipId = fig.id + '-clip';
      svg.append('clipPath').attr('id', clipId).append('rect').attr('width', w).attr('height', h);
      const plot = g.append('g').attr('clip-path', `url(#${clipId})`);
      // optional gray band over recent years whose values are known to be incomplete
      if (cfg.shade) {
        const sx = Math.max(0, x(cfg.shade.from - 0.5));
        plot.append('rect').attr('class', 'shade').attr('x', sx).attr('y', 0).attr('width', Math.max(0, w - sx)).attr('height', h);
        g.append('text').attr('class', 'shade-label').attr('text-anchor', 'end')
          .attr('transform', `translate(${(sx + w) / 2 + 4},6) rotate(-90)`).text(cfg.shade.label);
      }
      const line = d3.line().x((d, i) => x(yrs[i])).y(d => y(cfg.log ? Math.max(1, d) : d)).curve(d3.curveMonotoneX);
      if (cfg.area) {
        const area = d3.area().x((d, i) => x(yrs[i])).y0(h).y1(d => y(cfg.log ? Math.max(1, d) : d)).curve(d3.curveMonotoneX);
        plot.selectAll('path.series-area').data(vis).join('path').attr('class', 'series-area').attr('fill', d => col(d.key)).attr('d', d => area(d.v));
      }
      plot.selectAll('path.series-line').data(vis).join('path').attr('class', 'series-line').attr('stroke', d => col(d.key)).attr('d', d => line(d.v));

      // annotation (e.g. crossover)
      if (cfg.note) {
        const nx = x(cfg.note.x), ny = y(cfg.note.y);
        const N = g.append('g').attr('class', 'note');
        N.append('circle').attr('cx', nx).attr('cy', ny).attr('r', 5).attr('fill', 'none').attr('stroke', 'var(--ink)').attr('stroke-width', 1.2);
        const tx = nx - 20, ty = ny - 46;
        N.append('path').attr('d', `M${nx - 4},${ny - 5} L${tx + 6},${ty + 6}`);
        if (!narrow) N.append('text').attr('x', tx).attr('y', ty).attr('text-anchor', 'end').text(cfg.note.text);
        else N.select('path').remove();
      }

      // direct end labels (secondary identity channel next to the legend)
      if (!narrow) {
        const labs = spread(vis.map(s => ({ key: s.key, y: y(cfg.log ? Math.max(1, s.v[s.v.length - 1]) : s.v[s.v.length - 1]), v: s.v[s.v.length - 1] })), 15, 6, h);
        const E = g.append('g');
        labs.forEach(l => {
          E.append('text').attr('class', 'dlabel').attr('x', w + 8).attr('y', l.y).attr('dy', '0.33em').text(SHORT[l.key]);
        });
        vis.forEach(s => g.append('circle').attr('class', 'dot-ring').attr('cx', w).attr('cy', y(cfg.log ? Math.max(1, s.v[s.v.length - 1]) : s.v[s.v.length - 1])).attr('r', 4).attr('fill', col(s.key)));
      }
      legend(g, series.map(s => ({ key: s.key, label: s.label, color: col(s.key) })), 12, 12, hidden, k => {
        hidden.has(k) ? hidden.delete(k) : hidden.add(k); if (hidden.size === series.length) hidden.delete(k); render();
      });

      // crosshair + tooltip
      const cross = g.append('line').attr('class', 'crosshair').attr('y1', 0).attr('y2', h).style('opacity', 0);
      const dots = g.append('g');
      g.append('rect').attr('width', w).attr('height', h).attr('fill', 'transparent')
        .on('pointermove', e => {
          const [mx] = d3.pointer(e); const yr = Math.round(x.invert(mx)); const i = yrs.indexOf(yr); if (i < 0) return;
          cross.attr('x1', x(yr)).attr('x2', x(yr)).style('opacity', 1);
          const rows = vis.map(s => ({ s, v: s.v[i] })).sort((a, b) => b.v - a.v);
          dots.selectAll('circle').data(rows).join('circle').attr('class', 'dot-ring').attr('r', 4)
            .attr('cx', x(yr)).attr('cy', d => y(cfg.log ? Math.max(1, d.v) : d.v)).attr('fill', d => col(d.s.key));
          const inc = cfg.shade && yr >= cfg.shade.from ? ' <span style="font-weight:400;color:var(--ink-3)">· likely incomplete</span>' : '';
          tip.show(`<div class="t-head">${yr}${inc}</div>` + rows.map(r =>
            `<div class="row"><span class="sw" style="background:${col(r.s.key)}"></span>${r.s.label}<span class="val">${cfg.fmt(r.v)}</span></div>`).join(''),
            x(yr) + M.l, Math.min(h * 0.45, h - 60) + M.t);
        })
        .on('pointerleave', () => { cross.style('opacity', 0); dots.selectAll('*').remove(); tip.hide(); });
    }
    onResize(render)(box);
    wireFoot(fig, () => {
      const cfg = opts.get(); const i0 = YEARS.indexOf(cfg.from);
      return [['year', ...cfg.series.map(s => SHORT[s.key])],
        YEARS.slice(i0).map((yr, i) => [yr, ...cfg.series.map(s => cfg.fmt(s.values[i0 + i]))]).reverse()];
    });
    return render;
  }

  function crossover(a, b) {          // most recent year in which series a overtakes b
    for (let i = YEARS.length - 1; i > 0; i--) if (a[i] > b[i] && a[i - 1] <= b[i - 1]) return i;
    return -1;
  }

  // ---------- Figure: papers per year ----------
  (function () {
    const fig = $('#fig-papers'); if (!fig) return;
    let render;
    const mode = segState(fig, 'mode', 'annual', () => render());
    const src = segState(fig, 'src', 'all', () => render());
    const qf = segState(fig, 'qf', 'all', () => render());
    const title = fig.querySelector('.fig-title');
    render = lineChart(fig, {
      aria: 'Line chart of cryptanalytic research items per year by assumption class',
      get() {
        const P = qf() === 'all' || !D.papers_q ? D.papers[src()] : D.papers_q[src()][qf()], cum = mode() === 'cumulative';
        title.textContent = { all: 'Papers per year', quantum: 'Quantum papers per year', classical: 'Non-quantum papers per year' }[qf()];
        const series = CLS.map(c => ({ key: c.key, label: c.label, values: cum ? cumsum(P[c.key]) : movavg(P[c.key]) }));
        let note = null;
        if (cum) {
          const i = crossover(series[0].values, series[1].values);
          if (i > 0) note = { x: YEARS[i], y: series[0].values[i], text: `lattices pass ECDLP, ${YEARS[i]}` };
        }
        // peer-reviewed counts lag: publication takes a year or more and DBLP indexes with a further delay
        const shade = src() === 'peer' ? { from: 2025, label: 'likely incomplete' } : null;
        return { from: 1978, series, yLabel: cum ? 'papers (cumulative)' : 'papers per year', fmt: cum ? fmt.n0 : fmt.n1, note, shade };
      },
    });
  })();

  // ---------- Figure: researchers per year ----------
  (function () {
    const fig = $('#fig-fte'); if (!fig) return;
    let render;
    const unit = segState(fig, 'unit', 'fte', () => render());
    render = lineChart(fig, {
      aria: 'Line chart of estimated research allocation per year by assumption class',
      get() {
        return { from: 1980, yLabel: unit() === 'fte' ? 'allocation years per year' : 'adjusted years per year', fmt: fmt.n1,
          series: CLS.map(c => ({ key: c.key, label: c.label, values: D.fte[c.key][unit()] })) };
      },
    });
  })();

  // ---------- Figure: cumulative research-years ----------
  (function () {
    const fig = $('#fig-cum'); if (!fig) return;
    let render;
    const unit = segState(fig, 'unit', 'fte_cum', () => render());
    const scale = segState(fig, 'scale', 'linear', () => render());
    render = lineChart(fig, {
      aria: 'Line chart of cumulative estimated research-allocation years by assumption class',
      get() {
        const series = CLS.map(c => ({ key: c.key, label: c.label, values: D.fte[c.key][unit()] }));
        const i = crossover(series[0].values, series[1].values);
        const note = i > 0 ? { x: YEARS[i], y: series[0].values[i], text: `lattices pass ECDLP, ${YEARS[i]}` } : null;
        return { from: 1980, series, area: scale() === 'linear', log: scale() === 'log', note, fmt: fmt.n0,
          yLabel: unit() === 'fte_cum' ? 'estimated allocation years' : 'estimated adjusted years' };
      },
    });
  })();

  // ---------- Table: summary ----------
  (function () {
    const t = $('#tab-summary table'); if (!t) return;
    const last = YEARS.length - 1, rec = YEARS.indexOf(2022);
    const ec = D.fte.ecdlp.fte_cum[last];
    const row = (k, sub) => {
      const p = D.paper_totals.all[k], pv = D.paper_totals.vetted[k], f = D.fte[k].fte_cum[last];
      const pr = D.paper_totals.peer ? D.paper_totals.peer[k] : NaN;
      const rate = sum(D.fte[k].fte.slice(rec)) / (last - rec + 1);
      const sw = sub ? '' : `<span class="sw" style="background:${col(k)}"></span>`;
      return `<tr><td class="${sub ? 'sub' : ''}">${sw}${LABEL[k]}</td><td>${fmt.n1(p)}</td><td>${fmt.n1(pv)}</td><td>${Number.isFinite(pr) ? fmt.n1(pr) : '&ndash;'}</td><td>${fmt.n0(f)}</td><td>${fmt.n0(rate)}</td><td>${(f / ec).toFixed(2)}</td></tr>`;
    };
    t.innerHTML = `<thead><tr><th></th><th colspan="3" style="text-align:center">Research items</th><th colspan="3" style="text-align:center">Estimated allocation years</th></tr>
      <tr><th>Class</th><th>all</th><th>ePrint/DBLP</th><th>peer-reviewed</th><th>cumulative</th><th>per yr, 2022&ndash;26</th><th>&divide; ECDLP</th></tr></thead><tbody>` +
      row('ecdlp') + row('lattice') + row('mlwe', true) + row('lwe', true) + row('code') +
      `<tr class="midrule"><td colspan="7" style="padding:0"></td></tr>` + row('factoring') + row('isogeny') + row('mq') + '</tbody>';
    const kp = document.querySelector('[data-kf="ratio"]');
    if (kp) kp.firstChild.textContent = (D.fte.lattice.fte_cum[last] / ec).toFixed(1);
    const paperCount = document.querySelector('[data-kf="papers"]');
    if (paperCount) paperCount.textContent = fmt.n0(D.corpus_counts.effort_works ?? D.corpus_counts.effort_items);
  })();

  // ---------- Figure: frontier gaps ----------
  (function () {
    const fig = $('#fig-gaps'); if (!fig) return;
    const box = fig.querySelector('.chart'); const tip = tooltip(box);
    function render() {
      const W = box.clientWidth, narrow = W < 560;
      const rows = D.gaps, band = 46;
      const M = { t: 10, r: 70, b: 44, l: narrow ? 118 : 170 };
      const H = M.t + M.b + rows.length * band, w = W - M.l - M.r, h = rows.length * band;
      d3.select(box).select('svg').remove();
      const svg = d3.select(box).insert('svg', '.tip').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'Bar chart of frontier gaps in bits');
      const g = svg.append('g').attr('transform', `translate(${M.l},${M.t})`);
      const x = d3.scaleLinear().domain([0, 160]).range([0, w]);
      const xt = [0, 40, 80, 120, 160];
      g.append('g').attr('class', 'grid').selectAll('line').data(xt).join('line').attr('x1', x).attr('x2', x).attr('y1', 0).attr('y2', h);
      xTicks(g, x, h, xt, String);
      frame(g, w, h);
      g.append('text').attr('class', 'axis-label').attr('x', w / 2).attr('y', h + 36).attr('text-anchor', 'middle').text('modeled work gap, bits');
      const bh = 16;
      rows.forEach((r, i) => {
        const cy = i * band + band / 2;
        const R = g.append('g').style('cursor', 'default');
        R.append('rect').attr('x', 0).attr('y', cy - bh / 2).attr('height', bh).attr('width', x(r.lo)).attr('fill', col(r.cls)).attr('rx', 0);
        if (r.hi > r.lo) R.append('rect').attr('x', x(r.lo) + 2).attr('y', cy - bh / 2).attr('height', bh).attr('width', x(r.hi) - x(r.lo) - 2).attr('fill', col(r.cls)).attr('opacity', 0.35);
        R.append('text').attr('class', 'dlabel').attr('x', x(r.hi) + 8).attr('y', cy).attr('dy', '0.33em')
          .text(r.hi > r.lo ? `${r.lo}–${r.hi}` : (r.approx ? '≈' : '') + r.lo);
        g.append('text').attr('class', 'dlabel').attr('x', -12).attr('y', cy - (narrow ? 0 : 6)).attr('dy', '0.33em').attr('text-anchor', 'end').text(r.target);
        if (!narrow) g.append('text').attr('class', 'dlabel muted').attr('x', -12).attr('y', cy + 10).attr('dy', '0.33em').attr('text-anchor', 'end').style('font-size', '11px').text(LABEL[r.cls]);
        R.append('rect').attr('x', -M.l).attr('y', cy - band / 2).attr('width', W).attr('height', band).attr('fill', 'transparent')
          .on('pointermove', e => {
            const [mx, my] = d3.pointer(e, box);
            const ratio = r.hi > r.lo ? `2<sup>${r.lo}</sup>–2<sup>${r.hi}</sup>` : `2<sup>${r.lo}</sup>`;
            tip.show(`<div class="t-head">${r.target}</div><div>gap ≈ ${r.hi > r.lo ? r.lo + '–' + r.hi : r.lo} bits (${ratio}&times; modeled work)</div><div style="color:var(--ink-2)">vs. ${r.vs}</div><div>${r.basis}</div>`, mx, my);
          }).on('pointerleave', () => tip.hide());
      });
    }
    onResize(render)(box);
  })();

  // ---------- Figure: selected algorithmic bounds ----------
  (function () {
    const fig = $('#fig-stability'); if (!fig || !D.attack_history) return;
    const A = D.attack_history, box = fig.querySelector('.chart'), tip = tooltip(box);
    const SHORTP = {ecdlp: 'ECDLP', svp: 'SVP oracle', sd: 'Decoding bound', rsa: 'Factoring', mq: 'Boolean MQ'};
    const hidden = new Set();
    let render;
    const view = segState(fig, 'view', 'cost', () => render());
    const scope = segState(fig, 'scope', 'primary', () => render());
    const probs = () => A.problems.filter(p => p.display_kind === 'index' && (scope() === 'all' || p.role === 'primary'));
    const points = p => (view() === 'cost' ? p.steps : p.size_steps).map(s => ({
      year: s.year, v: view() === 'cost' ? s.cost : s.size / p.metrics.current_size, s: s
    }));
    render = function () {
      const P = probs(), cost = view() === 'cost';
      const W = box.clientWidth, narrow = W < 560;
      const M = {t: 14, r: narrow ? 12 : 112, b: 46, l: 56};
      const H = Math.max(300, Math.min(440, W * 0.5)), w = W - M.l - M.r, h = H - M.t - M.b;
      d3.select(box).select('svg').remove();
      const svg = d3.select(box).insert('svg', '.tip').attr('viewBox', '0 0 ' + W + ' ' + H).attr('role', 'img')
        .attr('aria-label', cost ? 'Selected leading-term indices over time' : 'Sizes giving index 128, relative to latest selected bound');
      const g = svg.append('g').attr('transform', 'translate(' + M.l + ',' + M.t + ')');
      const from = d3.min(P, p => points(p)[0].year) - 2;
      const x = d3.scaleLinear().domain([from, A.end_year]).range([0, w]);
      const cap = cost ? Math.ceil(d3.max(P, p => d3.max(points(p), d => d.v)) / 50) * 50 : 1.1;
      const y = d3.scaleLinear().domain([0, cap]).range([h, 0]);
      yTicks(g, y, w, cost ? y.ticks(5) : [0, .25, .5, .75, 1], cost ? String : v => v.toFixed(2));
      xTicks(g, x, h, d3.range(Math.ceil(from / 10) * 10, 2030, 10).filter(v => v <= A.end_year), String);
      frame(g, w, h);
      g.append('text').attr('class', 'axis-label').attr('transform', 'translate(-44,' + h / 2 + ') rotate(-90)').attr('text-anchor', 'middle')
        .text(cost ? 'leading-term index at reference size' : 'size for index 128 / latest size');
      g.append('text').attr('class', 'axis-label').attr('x', w / 2).attr('y', h + 38).attr('text-anchor', 'middle').text('analysis year');
      if (cost) {
        const R = g.append('g').attr('class', 'note');
        R.append('line').attr('x1', 0).attr('x2', w).attr('y1', y(128)).attr('y2', y(128)).style('stroke-dasharray', '2 3');
        R.append('text').attr('x', 4).attr('y', y(128) - 5).text('index 128');
      }
      const line = d3.line().x(d => x(d.year)).y(d => y(d.v)).curve(d3.curveStepAfter);
      const ends = [];
      P.filter(p => !hidden.has(p.key)).forEach(p => {
        const pts = points(p), last = pts[pts.length - 1];
        g.append('path').attr('class', 'series-line').attr('stroke', col(p.cls))
          .attr('d', line(pts.concat([{year: A.end_year, v: last.v}])));
        pts.forEach(d => g.append('circle').attr('class', 'dot-ring').attr('cx', x(d.year)).attr('cy', y(d.v))
          .attr('r', 4.5).attr('fill', col(p.cls)).on('pointermove', e => {
            const [mx, my] = d3.pointer(e, box);
            const val = cost ? 'index ' + d.s.cost.toFixed(1) + ' at ' + p.reference.label
              : d3.format(',.1f')(d.s.size) + ' ' + p.size_unit + ' for index 128';
            tip.show('<div class="t-head">' + p.label + ', ' + d.year + '</div><div>' + d.s.name
              + '</div><div>' + val + '</div><div style="color:var(--ink-3)">Selected bound; not measured security.</div>', mx, my);
          }).on('pointerleave', () => tip.hide()));
        ends.push({key: p.key, y: y(last.v)});
      });
      if (!narrow) spread(ends, 15, 6, h).forEach(l => g.append('text').attr('class', 'dlabel')
        .attr('x', w + 8).attr('y', l.y).attr('dy', '.33em').text(SHORTP[l.key]));
      const lw = 132, lh = P.length * 19 + 8;
      legend(g, P.map(p => ({key: p.key, label: SHORTP[p.key], color: col(p.cls)})),
        cost ? 12 : w - lw - 12, h - lh - 12, hidden, k => {
          hidden.has(k) ? hidden.delete(k) : hidden.add(k);
          if (P.every(p => hidden.has(p.key))) hidden.delete(k);
          render();
        });
    };
    wireFoot(fig, () => [
      ['Track', 'Year', 'Selected analysis', view() === 'cost' ? 'Leading-term index' : 'Size for index 128', 'Source'],
      probs().flatMap(p => points(p).map(d => [p.label, d.year, d.s.name,
        view() === 'cost' ? d.s.cost.toFixed(2) : d.s.size.toFixed(1) + ' ' + p.size_unit, d.s.source_url]))
    ]);
    onResize(render)(box);
  })();

  // ---------- Tables: index summary and qualitative attack events ----------
  (function () {
    if (!D.attack_history) return;
    const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
    const t = $('#tab-stability table');
    if (t) {
      t.innerHTML = '<thead><tr><th>Reference</th><th>First index</th><th>Latest index</th><th>Index decrease</th><th>Latest plotted bound</th></tr></thead><tbody>'
        + D.attack_history.problems.filter(p => p.display_kind === 'index').map(p => {
          const m = p.metrics;
          return '<tr><td>' + esc(p.reference.label) + '</td><td>' + m.first_year + ': ' + m.first_cost.toFixed(1)
            + '</td><td>' + m.current_cost.toFixed(1) + '</td><td>' + m.index_drop.toFixed(1)
            + '</td><td>' + m.last_bound_year + '</td></tr>';
        }).join('') + '</tbody>';
    }
    const e = $('#tab-attack-events table');
    if (e) e.innerHTML = '<thead><tr><th>Date / problem</th><th>Result and limits</th></tr></thead><tbody>'
      + D.attack_history.problems.filter(p => p.display_kind === 'events').flatMap(p => p.milestones.map(m =>
        '<tr><td>' + esc(m.date) + '<br>' + esc(p.label) + '</td><td><a href="' + esc(m.source_url) + '">'
        + esc(m.name) + '</a>. ' + esc(m.event) + ' ' + esc(m.notes) + ' ' + esc(m.assumptions || '') + '</td></tr>'
      )).join('') + '</tbody>';
  })();

  // ---------- Figure: budget explorer ----------
  (function () {
    const fig = $('#fig-budget'); if (!fig) return;
    const box = fig.querySelector('.chart'); const tip = tooltip(box);
    const sIn = $('#ctl-s'), cIn = $('#ctl-c'), pIn = $('#ctl-p');
    const out = k => fig.querySelector(`[data-out="${k}"]`);
    const last = YEARS.length - 1;
    const presetSeg = fig.querySelector('.seg[data-ctl="preset"]');
    const unit = segState(fig, 'unit', 'usd', () => render());
    let focus = 'lattice';
    const S = () => Math.pow(10, +sIn.value), C = () => +cIn.value, PRICE = () => Math.pow(10, +pIn.value);
    function pressPreset(v) { presetSeg.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === v)); }
    presetSeg.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      sIn.value = Math.log10(+b.dataset.v);
      pressPreset(b.dataset.v); render();
    });
    [sIn, cIn, pIn].forEach(i => i.addEventListener('input', () => {
      const s = S(); const p = [1, 10, 100].find(v => Math.abs(s - v) / v < 0.02);
      pressPreset(p ? String(p) : ''); render();
    }));
    const REFS = [
      { v: D.problems.find(p => p.key === 'hawk').ai_usd, label: 'HAWK discovery budget' },
    ];
    function render() {
      const s = S(), c = C(), price = PRICE();
      out('s').textContent = (s < 10 ? s.toFixed(1) : d3.format(',.0f')(s)) + '×';
      out('c').textContent = fmt.usd(c);
      out('p').textContent = '$' + d3.format('.3~g')(price);
      const rows = CLS.map(k => ({ key: k.key, label: k.label, H: D.fte[k.key].fte_cum[last] })).map(r => ({ ...r, usd: c * r.H / s }));
      const f = rows.find(r => r.key === focus);
      const tokenMode = unit() === 'tokens';
      const tokenCount = f.usd / price * 1e6;
      const tokenUnits = tokenCount >= 1e12 ? [1e12, 'trillion'] : tokenCount >= 1e9 ? [1e9, 'billion'] : [1e6, 'million'];
      out('tokens').textContent = d3.format('.3~g')(tokenCount / tokenUnits[0]) + ' ' + tokenUnits[1] + ' reference tokens';
      out('token-calculation').textContent = `${SHORT[f.key]}: ${fmt.usd(f.usd)} ÷ ${out('p').textContent} per million tokens.`;
      if (window.katex) katex.render(
        `D_{\\text{${SHORT[f.key]}}} = \\frac{\\text{${fmt.usd(c).replace('$', '\\$')}} \\times ${fmt.n0(f.H).replace(',', '{,}')}}{${s < 10 ? s.toFixed(1) : d3.format(',.0f')(s).replace(',', '{,}')}} = \\text{${fmt.usd(f.usd).replace('$', '\\$')}}`,
        out('formula'), { displayMode: true, throwOnError: false });

      const W = box.clientWidth, narrow = W < 520, band = 40;
      const M = { t: 30, r: 16, b: 44, l: narrow ? 92 : 132 };
      const h = rows.length * band, H = h + M.t + M.b, w = W - M.l - M.r;
      d3.select(box).select('svg').remove();
      const svg = d3.select(box).insert('svg', '.tip').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img')
        .attr('aria-label', tokenMode ? 'Reference-token allowance per class on a fixed log scale' : 'Equivalent inference budget per class on a fixed log scale');
      const g = svg.append('g').attr('transform', `translate(${M.l},${M.t})`);
      const value = usd => tokenMode ? usd / price * 1e6 : usd;
      const x = d3.scaleLog().domain(tokenMode ? [1e8, 1e15] : [1e3, 1e9]).range([0, w]).clamp(true);
      const xt = tokenMode ? [1e8, 1e10, 1e12, 1e14] : [1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9];
      g.append('g').attr('class', 'grid').selectAll('line').data(xt).join('line').attr('x1', x).attr('x2', x).attr('y1', 0).attr('y2', h);
      xTicks(g, x, h, xt, tokenMode ? fmt.tok : fmt.usd);
      frame(g, w, h);
      g.append('text').attr('class', 'axis-label').attr('x', w / 2).attr('y', h + 36).attr('text-anchor', 'middle')
        .text(tokenMode ? 'reference tokens (log scale)' : 'equivalent inference budget (log scale)');
      // reference spends
      REFS.forEach(r => {
        const px = x(value(r.v));
        const N = g.append('g').attr('class', 'note');
        N.append('line').attr('x1', px).attr('x2', px).attr('y1', -6).attr('y2', h).style('stroke-dasharray', '2 3');
        N.append('text').attr('x', px).attr('y', -12).attr('text-anchor', px < w / 2 ? 'start' : 'end').attr('dx', px < w / 2 ? 4 : -4)
          .text(tokenMode ? 'HAWK budget → tokens' : narrow ? fmt.usd(r.v) : r.label);
      });
      rows.forEach((r, i) => {
        const cy = i * band + band / 2, px = x(value(r.usd));
        const G = g.append('g').style('cursor', 'pointer');
        G.append('line').attr('x1', 0).attr('x2', px).attr('y1', cy).attr('y2', cy).attr('stroke', col(r.key)).attr('stroke-width', 2).attr('opacity', .55);
        G.append('circle').attr('class', 'dot-ring').attr('cx', px).attr('cy', cy).attr('r', r.key === focus ? 7 : 5.5).attr('fill', col(r.key));
        const tokens = r.usd / price * 1e6;
        const right = px > w - 150;
        G.append('text').attr('class', 'dlabel').attr('x', right ? px - 12 : px + 12).attr('y', cy).attr('dy', '0.33em').attr('text-anchor', right ? 'end' : 'start')
          .text(tokenMode ? fmt.tok(tokens) + ' tok' : fmt.usd(r.usd));
        g.append('text').attr('class', 'dlabel').attr('x', -12).attr('y', cy).attr('dy', '0.33em').attr('text-anchor', 'end')
          .style('font-weight', r.key === focus ? 700 : 400).text(narrow ? SHORT[r.key] : r.label);
        G.append('rect').attr('x', -M.l).attr('y', cy - band / 2).attr('width', W).attr('height', band).attr('fill', 'transparent')
          .on('click', () => { focus = r.key; render(); })
          .on('pointermove', e => {
            const [mx, my] = d3.pointer(e, box);
            tip.show(`<div class="t-head">${r.label}</div><div class="row">effort proxy<span class="val">${fmt.n0(r.H)} allocation yr</span></div><div class="row">scenario budget<span class="val">${fmt.usd(r.usd)}</span></div><div class="row">reference tokens at ${out('p').textContent}/M<span class="val">${fmt.tok(tokens)}</span></div><div style="color:var(--ink-3);margin-top:.2rem">May overestimate actual time. Click to show in formula.</div>`, mx, my);
          }).on('pointerleave', () => tip.hide());
      });
    }
    pIn.value = 1;  // $10 per million tokens, the method's illustrative price
    onResize(render)(box);
  })();

  // ---------- Figure: literature-effort scenarios vs AI budgets ----------
  (function () {
    const fig = $('#fig-problems'); if (!fig) return;
    const box = fig.querySelector('.chart'); const tip = tooltip(box);
    let render;
    const show = segState(fig, 'show', 'priced', () => render());
    const C = D.usd_per_year;
    const GROUP = { crypto: 'Anthropic, 2026', astra: 'GPT-6 Astra (Epoch)', alphaproof: 'AlphaProof Nexus: variants/parts', openai: 'OpenAI, claimed', unsolved: 'unresolved in sampled attempts' };
    render = function () {
      const all = show() === 'all';
      const rows = D.problems.filter(p => all ? true : p.ai_usd).sort((a, b) => (b.ai_usd ? 1 : 0) - (a.ai_usd ? 1 : 0) || b.py - a.py);
      const W = box.clientWidth, narrow = W < 560, band = all ? 26 : 40;
      const M = { t: 44, r: 22, b: 44, l: narrow ? 100 : 150 };
      const h = rows.length * band, H = h + M.t + M.b, w = W - M.l - M.r;
      d3.select(box).select('svg').remove();
      const svg = d3.select(box).insert('svg', '.tip').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'Dot plot comparing assumed literature-effort valuations with AI budgets');
      const g = svg.append('g').attr('transform', `translate(${M.l},${M.t})`);
      const x = d3.scaleLog().domain([50, 5e7]).range([0, w]).clamp(true);
      const xt = [1e2, 1e3, 1e4, 1e5, 1e6, 1e7];
      g.append('g').attr('class', 'grid').selectAll('line').data(xt).join('line').attr('x1', x).attr('x2', x).attr('y1', 0).attr('y2', h);
      xTicks(g, x, h, xt, v => fmt.usd(v));
      frame(g, w, h);
      g.append('text').attr('class', 'axis-label').attr('x', w / 2).attr('y', h + 36).attr('text-anchor', 'middle').text('dollars (log scale)');
      legend(g, [
        { key: 'ai', label: 'AI budget (see caption)', color: 'var(--accent)', mark: 'dot' },
        { key: 'h', label: 'literature-effort estimate', color: 'var(--paper)', stroke: 'var(--ink)', mark: 'dot' },
      ], 0, -40, new Set(), () => {}).select('rect.box').style('stroke', 'none').style('fill', 'none');
      g.select('.legend').attr('transform', `translate(-8,-42)`).selectAll('g.item').attr('transform', (d, i) => `translate(${10 + i * (narrow ? 0 : 230)},${14 + (narrow ? i * 18 : 0)})`);
      rows.forEach((r, i) => {
        const cy = i * band + band / 2;
        const hu = r.py * C, lo = r.py_lo * C, hi = r.py_hi * C;
        const G = g.append('g');
        G.append('line').attr('x1', x(lo)).attr('x2', x(hi)).attr('y1', cy).attr('y2', cy).attr('stroke', 'var(--ink-2)').attr('stroke-width', 1);
        [lo, hi].forEach(v => G.append('line').attr('x1', x(v)).attr('x2', x(v)).attr('y1', cy - 4).attr('y2', cy + 4).attr('stroke', 'var(--ink-2)'));
        if (r.ai_usd) {
          G.append('line').attr('x1', x(r.ai_usd)).attr('x2', x(hu)).attr('y1', cy).attr('y2', cy).attr('stroke', 'var(--accent)').attr('stroke-width', 2).attr('opacity', .35);
          G.append('circle').attr('class', 'dot-ring').attr('cx', x(r.ai_usd)).attr('cy', cy).attr('r', 5.5).attr('fill', 'var(--accent)');
        }
        G.append('circle').attr('cx', x(hu)).attr('cy', cy).attr('r', 5).attr('fill', 'var(--paper)').attr('stroke', 'var(--ink)').attr('stroke-width', 1.6);
        g.append('text').attr('class', 'dlabel').attr('x', -12).attr('y', cy - (all || narrow ? 0 : 6)).attr('dy', '0.33em').attr('text-anchor', 'end').text(r.label + (r.ai_flagged_items ? '*' : ''));
        if (!all && !narrow) g.append('text').attr('class', 'dlabel muted').attr('x', -12).attr('y', cy + 10).attr('dy', '0.33em').attr('text-anchor', 'end').style('font-size', '11px').text(GROUP[r.group]);
        G.append('rect').attr('x', -M.l).attr('y', cy - band / 2).attr('width', W).attr('height', band).attr('fill', 'transparent')
          .on('pointermove', e => {
            const [mx, my] = d3.pointer(e, box);
            tip.show(`<div class="t-head">${r.label}</div><div style="color:var(--ink-3)">${GROUP[r.group]}</div>
              <div class="row">literature estimate<span class="val">${fmt.n1(r.py)} yr (${fmt.n1(r.py_lo)}–${fmt.n1(r.py_hi)})</span></div>
              <div class="row">at ${fmt.usd(C)}/yr<span class="val">${fmt.usd(hu)}</span></div>
              ${r.ai_flagged_items ? `<div>Includes ${fmt.n1(r.ai_flagged_py)} assumed years from ${r.ai_flagged_items} AI-flagged item(s).</div>` : ''}
              <div class="row">${r.ai_priced_successes ? 'mean priced success' : 'disclosed budget'}<span class="val">${r.ai_usd ? fmt.usd(r.ai_usd) : 'not available'}</span></div>
              ${r.ai_priced_successes ? `<div>${r.ai_priced_successes} priced successful runs; unsuccessful runs excluded.</div>` : ''}
              <div style="color:var(--ink-3)">Historical cutoff not audited; not measured human time.</div>`, mx, my);
          }).on('pointerleave', () => tip.hide());
      });
    };
    onResize(render)(box);
    wireFoot(fig, () => [['problem', 'source', 'literature yr', 'prior endpoints', 'AI-flagged yr', 'AI budget', 'priced successes'],
      D.problems.filter(p => show() === 'all' || p.ai_usd).map(p => [p.label, GROUP[p.group], fmt.n1(p.py), `${fmt.n1(p.py_lo)}–${fmt.n1(p.py_hi)}`, fmt.n1(p.ai_flagged_py), p.ai_usd ? fmt.usd(p.ai_usd) : '—', p.ai_priced_successes || '—'])]);
  })();
})();
