(() => {
  const DATA_URL = 'data/exp001.json';
  const colors = {
    teal: '#45dfc4',
    red: '#f27f7f',
    amber: '#f3b85d',
    blue: '#82aaff',
    muted: '#96a7b7',
    grid: 'rgba(148, 163, 184, 0.12)',
    track: 'rgba(148, 163, 184, 0.12)'
  };

  const inr = new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 2
  });
  const wholeInr = new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0
  });
  const int = new Intl.NumberFormat('en-IN');
  const dateTime = new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata'
  });

  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[ch]));
  const pct = (value) => `${value > 0 ? '+' : ''}${Number(value).toFixed(2)}%`;

  function svgEl(tag, attrs = {}, text = '') {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text) node.textContent = text;
    return node;
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function activateTabs() {
    const selectTab = (name, updateHash = true) => {
      const button = document.querySelector(`.tab[data-tab="${name}"]`) || document.querySelector('.tab');
      document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab === button));
      document.querySelectorAll('.panel').forEach((panel) => {
        const active = panel.id === button.dataset.tab;
        panel.classList.toggle('active', active);
        panel.hidden = !active;
      });
      if (updateHash) history.replaceState(null, '', `#${button.dataset.tab}`);
    };
    document.querySelectorAll('.tab').forEach((button) => {
      button.addEventListener('click', () => selectTab(button.dataset.tab));
    });
    const initial = location.hash.slice(1);
    if (initial) {
      selectTab(initial, false);
      document.getElementById(initial)?.scrollIntoView({ block: 'start' });
    }
  }

  function renderComparison(summary) {
    const host = $('#comparison-chart');
    host.textContent = '';
    const rows = [
      { label: 'SMA 20/60 after modeled costs', value: summary.total_return_pct, color: colors.teal },
      { label: 'NIFTY 50 price return', value: summary.benchmark_nifty50_return_pct, color: colors.blue }
    ];
    const width = 680, height = 190, left = 210, top = 24, barH = 34, gap = 42;
    const max = Math.max(...rows.map((row) => row.value)) * 1.16;
    const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, role: 'presentation' });
    rows.forEach((row, i) => {
      const y = top + i * (barH + gap);
      const barW = Math.max(4, (width - left - 90) * row.value / max);
      svg.append(svgEl('text', { x: 0, y: y + 21, class: 'chart-label' }, row.label));
      svg.append(svgEl('rect', { x: left, y, width: width - left - 90, height: barH, rx: 10, class: 'bar-bg' }));
      const bar = svgEl('rect', { x: left, y, width: barW, height: barH, rx: 10, fill: row.color });
      bar.append(svgEl('title', {}, `${row.label}: ${pct(row.value)}`));
      svg.append(bar);
      svg.append(svgEl('text', { x: left + barW + 10, y: y + 22, class: 'chart-value' }, pct(row.value)));
    });
    svg.append(svgEl('text', { x: 0, y: 174, class: 'chart-label' },
      'Treatments differ: adjusted strategy prices with modeled costs vs price-return index without dividends or costs.'));
    host.append(svg);
  }

  function renderOutcome(summary) {
    const host = $('#outcome-chart');
    host.textContent = '';
    const total = summary.trades_executed + summary.skipped_decisions;
    const fraction = summary.trades_executed / total;
    const r = 68, c = 2 * Math.PI * r;
    const svg = svgEl('svg', { viewBox: '0 0 220 220', role: 'presentation' });
    svg.append(svgEl('circle', { cx: 110, cy: 110, r, fill: 'none', stroke: colors.red, 'stroke-width': 24, opacity: 0.7 }));
    svg.append(svgEl('circle', {
      cx: 110, cy: 110, r, fill: 'none', stroke: colors.teal, 'stroke-width': 24,
      'stroke-linecap': 'round', 'stroke-dasharray': `${fraction * c} ${c}`,
      transform: 'rotate(-90 110 110)'
    }));
    const center = document.createElement('div');
    center.className = 'donut-center';
    center.innerHTML = `<strong>${int.format(summary.trades_executed)}</strong><span>fills of ${int.format(total)} decisions</span>`;
    const wrap = document.createElement('div');
    wrap.style.position = 'relative';
    center.style.position = 'absolute';
    center.style.inset = '0';
    center.style.display = 'grid';
    center.style.placeContent = 'center';
    wrap.append(svg, center);
    const legend = document.createElement('div');
    legend.className = 'legend';
    legend.innerHTML = `<span><i style="background:${colors.teal}"></i>${summary.trades_executed} fills</span><span><i style="background:${colors.red}"></i>${summary.skipped_decisions} skipped</span>`;
    host.append(wrap, legend);
  }

  function renderActivity(monthly) {
    const host = $('#activity-chart');
    host.textContent = '';
    const n = monthly.length;
    const width = Math.max(760, n * 28), height = 300;
    const left = 44, right = 12, top = 18, bottom = 48;
    const chartH = height - top - bottom;
    const chartW = width - left - right;
    const max = Math.max(...monthly.map((row) => row.buy + row.sell));
    const step = chartW / n;
    const barW = Math.min(18, step * 0.68);
    const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, role: 'presentation' });
    svg.style.width = `${width}px`;

    for (let i = 0; i <= 4; i += 1) {
      const y = top + chartH - (chartH * i / 4);
      svg.append(svgEl('line', { x1: left, x2: width - right, y1: y, y2: y, class: i === 0 ? 'axis' : 'gridline' }));
      svg.append(svgEl('text', { x: 4, y: y + 4, class: 'chart-label' }, String(Math.round(max * i / 4))));
    }

    monthly.forEach((row, i) => {
      const x = left + i * step + (step - barW) / 2;
      const buyH = chartH * row.buy / max;
      const sellH = chartH * row.sell / max;
      const buyY = top + chartH - buyH;
      const sellY = buyY - sellH;
      const buy = svgEl('rect', { x, y: buyY, width: barW, height: buyH, rx: 4, class: 'buy' });
      buy.append(svgEl('title', {}, `${row.month}: ${row.buy} buys`));
      const sell = svgEl('rect', { x, y: sellY, width: barW, height: sellH, rx: 4, class: 'sell' });
      sell.append(svgEl('title', {}, `${row.month}: ${row.sell} sells`));
      svg.append(buy, sell);
      if (i % 3 === 0 || i === n - 1) {
        const label = svgEl('text', { x: x + barW / 2, y: height - 24, class: 'chart-label', 'text-anchor': 'end', transform: `rotate(-35 ${x + barW / 2} ${height - 24})` }, row.month);
        svg.append(label);
      }
    });
    const legend = document.createElement('div');
    legend.className = 'legend';
    legend.innerHTML = `<span><i style="background:${colors.teal}"></i>Buy decisions</span><span><i style="background:${colors.red}"></i>Sell decisions</span>`;
    host.append(svg, legend);
  }

  function renderAllocation(summary) {
    const host = $('#allocation-chart');
    host.textContent = '';
    const rows = [
      { label: 'Cash', value: summary.cash_inr, color: colors.amber },
      ...Object.entries(summary.open_position_values_inr)
        .sort((a, b) => b[1] - a[1])
        .map(([symbol, value]) => ({ label: symbol, value, color: colors.teal }))
    ];
    const width = 640, height = 230, left = 120, top = 14, barH = 27, gap = 13;
    const max = Math.max(...rows.map((row) => row.value));
    const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, role: 'presentation' });
    rows.forEach((row, i) => {
      const y = top + i * (barH + gap);
      const barW = Math.max(5, (width - left - 115) * row.value / max);
      svg.append(svgEl('text', { x: 0, y: y + 19, class: 'chart-label' }, row.label));
      svg.append(svgEl('rect', { x: left, y, width: width - left - 115, height: barH, rx: 8, class: 'bar-bg' }));
      svg.append(svgEl('rect', { x: left, y, width: barW, height: barH, rx: 8, fill: row.color }));
      svg.append(svgEl('text', { x: left + barW + 9, y: y + 19, class: 'chart-value' }, wholeInr.format(row.value)));
    });
    host.append(svg);
  }

  function renderHoldings(summary) {
    const tbody = $('#holding-rows');
    const rows = Object.entries(summary.open_positions_at_end)
      .map(([symbol, qty]) => ({ symbol, qty, value: summary.open_position_values_inr[symbol] }))
      .sort((a, b) => b.value - a.value);
    tbody.innerHTML = rows.map((row) => `
      <tr><td><strong>${esc(row.symbol)}</strong></td><td class="num">${int.format(row.qty)}</td><td class="num">${inr.format(row.value)}</td></tr>
    `).join('');
    setText('open-count', String(rows.length));
    setText('cash-value', inr.format(summary.cash_inr));
  }

  function decisionMatches(row, query, side, symbol) {
    const haystack = `${row.date} ${row.decision_id} ${row.symbol} ${row.side} ${row.rule} ${row.rationale}`.toLowerCase();
    return (!query || haystack.includes(query))
      && (side === 'all' || row.side === side)
      && (symbol === 'all' || row.symbol === symbol);
  }

  function renderDecisionDetail(row) {
    const host = $('#decision-detail');
    host.innerHTML = `
      <span class="state">Recorded decision</span>
      <h3>${esc(row.symbol)} · ${esc(row.side.toUpperCase())} ${int.format(row.qty)}</h3>
      <p>${esc(row.rationale)}</p>
      <dl>
        <div><dt>Date</dt><dd>${esc(row.date)}</dd></div>
        <div><dt>ID</dt><dd>${esc(row.decision_id)}</dd></div>
        <div><dt>Rule</dt><dd>${esc(row.rule)}</dd></div>
        <div><dt>Quantity</dt><dd>${int.format(row.qty)}</dd></div>
      </dl>
      <p class="muted">This row is from the deterministic decision-log backfill. The committed record proves 96 fills and 86 skips in aggregate, but does not carry each row's fill price or skip status.</p>
    `;
  }

  function renderDecisions(data) {
    const tbody = $('#decision-rows');
    const search = $('#decision-search');
    const side = $('#side-filter');
    const symbol = $('#symbol-filter');
    const symbols = [...new Set(data.decisions.map((row) => row.symbol))].sort();
    symbol.insertAdjacentHTML('beforeend', symbols.map((item) => `<option value="${esc(item)}">${esc(item)}</option>`).join(''));

    const draw = () => {
      const query = search.value.trim().toLowerCase();
      const rows = data.decisions.filter((row) => decisionMatches(row, query, side.value, symbol.value));
      tbody.innerHTML = rows.map((row, index) => `
        <tr tabindex="0" data-index="${data.decisions.indexOf(row)}">
          <td>${esc(row.date)}</td>
          <td>${esc(row.decision_id)}</td>
          <td><strong>${esc(row.symbol)}</strong></td>
          <td><span class="side ${esc(row.side)}">${esc(row.side)}</span></td>
          <td class="num">${int.format(row.qty)}</td>
          <td>${esc(row.rule)}</td>
        </tr>
      `).join('');
      $('#decision-count').textContent = `${int.format(rows.length)} of ${int.format(data.decisions.length)} shown`;
      tbody.querySelectorAll('tr').forEach((tr) => {
        const select = () => {
          tbody.querySelectorAll('tr').forEach((item) => item.classList.remove('selected'));
          tr.classList.add('selected');
          renderDecisionDetail(data.decisions[Number(tr.dataset.index)]);
        };
        tr.addEventListener('click', select);
        tr.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            select();
          }
        });
      });
    };
    [search, side, symbol].forEach((control) => control.addEventListener('input', draw));
    draw();
  }

  function renderProvenance(data) {
    const sourceBase = 'https://github.com/Rajatendu1/paper-trading-india/tree/main/';
    $('#source-list').innerHTML = Object.entries(data.sources).map(([name, path]) => `
      <li><strong>${esc(name.replaceAll('_', ' '))}:</strong> <a href="${sourceBase}${esc(path)}" target="_blank" rel="noopener">${esc(path)}</a></li>
    `).join('');
    $('#caveat-list').innerHTML = data.caveats.map((item) => `<li>${esc(item)}</li>`).join('');
  }

  function render(data) {
    const s = data.summary;
    setText('experiment-start', '14 Nov 2026');
    setText('historical-window', s && data.timeline.historical_window.replace('->', '→'));
    setText('as-of', `Data bundle generated ${dateTime.format(new Date(data.generated_at_utc))} IST · latest verified mark 13 Nov 2026`);
    setText('final-equity', inr.format(s.final_equity_inr));
    setText('net-return', pct(s.total_return_pct));
    setText('max-dd', inr.format(s.max_drawdown_inr));
    setText('loss-limit', `${inr.format(s.loss_limit_inr)} · not hit`);
    setText('strategy-return', pct(s.total_return_pct));
    setText('strategy-fills', int.format(s.trades_executed));
    setText('strategy-skips', int.format(s.skipped_decisions));
    setText('strategy-dd', inr.format(s.max_drawdown_inr));

    renderComparison(s);
    renderOutcome(s);
    renderActivity(data.monthly_activity);
    renderHoldings(s);
    renderAllocation(s);
    renderDecisions(data);
    renderProvenance(data);
  }

  function showError(error) {
    const box = document.createElement('div');
    box.className = 'error';
    box.textContent = `The dashboard data bundle could not be loaded: ${error.message}`;
    $('#main').prepend(box);
  }

  activateTabs();
  fetch(DATA_URL, { cache: 'no-store' })
    .then((response) => {
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.json();
    })
    .then(render)
    .catch(showError);
})();
