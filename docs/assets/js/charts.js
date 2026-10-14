/*
 * Three small chart forms, built from plain elements so that every label is real text.
 *
 *   Charts.bars(element, spec)    magnitudes from a common baseline, with intervals
 *   Charts.forest(element, spec)  differences around zero, with intervals
 *   Charts.strip(element, spec)   a few series compared along one scale, row by row
 *
 * Marks carry a series colour; text never does. Every chart has a legend when it shows more
 * than one series, a tooltip with the exact values on each mark, and a table of the same data.
 */
(function () {
  "use strict";

  const NBSP = " ";
  const MINUS = "−";

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  function fixed(value, digits) {
    return value.toFixed(digits).replace("-", MINUS);
  }

  function signed(value, digits) {
    return (value > 0 ? "+" : "") + fixed(value, digits);
  }

  function percent(value, digits) {
    return fixed(value, digits === undefined ? 1 : digits) + NBSP + "%";
  }

  function range(low, high, digits, sign) {
    const show = sign ? signed : fixed;
    return "[" + show(low, digits) + ", " + show(high, digits) + "]";
  }

  // One tooltip for the page, moved to whichever mark is under the pointer or has the focus.
  let tip = null;
  function tooltip(target, lines) {
    target.tabIndex = 0;
    const show = (x, y) => {
      if (!tip) {
        tip = node("div", "chart-tip");
        tip.setAttribute("role", "status");
        document.body.appendChild(tip);
      }
      tip.innerHTML = "";
      lines.forEach((line, index) => tip.appendChild(node("span", index ? "" : "chart-tip-title", line)));
      tip.hidden = false;
      const box = tip.getBoundingClientRect();
      const left = Math.min(window.innerWidth - box.width - 8, Math.max(8, x - box.width / 2));
      tip.style.left = left + window.scrollX + "px";
      tip.style.top = y + window.scrollY - box.height - 12 + "px";
    };
    const hide = () => {
      if (tip) tip.hidden = true;
    };
    target.addEventListener("pointermove", (event) => show(event.clientX, event.clientY));
    target.addEventListener("pointerleave", hide);
    target.addEventListener("focus", () => {
      const box = target.getBoundingClientRect();
      show(box.left + box.width / 2, box.top);
    });
    target.addEventListener("blur", hide);
  }

  function legend(series) {
    const list = node("ul", "chart-legend");
    series.forEach((item) => {
      const entry = node("li");
      entry.appendChild(node("i", "swatch tone-" + item.tone + (item.shape ? " swatch-" + item.shape : "")));
      entry.appendChild(document.createTextNode(item.name));
      list.appendChild(entry);
    });
    return list;
  }

  function table(caption, header, rows) {
    const details = node("details", "chart-table");
    details.appendChild(node("summary", "", "Show the numbers"));
    const grid = node("table");
    grid.appendChild(node("caption", "", caption));
    const head = node("tr");
    header.forEach((text) => head.appendChild(node("th", "", text)));
    grid.appendChild(head);
    rows.forEach((cells) => {
      const line = node("tr");
      cells.forEach((text, index) => line.appendChild(node(index ? "td" : "th", "", text)));
      grid.appendChild(line);
    });
    details.appendChild(grid);
    return details;
  }

  function axis(ticks, position, format) {
    const line = node("div", "chart-axis");
    ticks.forEach((tick) => {
      const label = node("span", "", format(tick));
      label.style.left = position(tick) + "%";
      line.appendChild(label);
    });
    return line;
  }

  function grid(plot, ticks, position, zero) {
    ticks.forEach((tick) => {
      const rule = node("i", "chart-grid" + (tick === zero ? " chart-zero" : ""));
      rule.style.left = position(tick) + "%";
      plot.appendChild(rule);
    });
  }

  function rowLabel(row) {
    const label = node("div", "chart-label");
    label.appendChild(node("span", "", row.label));
    if (row.note) label.appendChild(node("small", "", row.note));
    return label;
  }

  /*
   * spec: { series: [{key, name, tone}], rows: [{label, note, values: {key: {v, lo, hi}}}],
   *         max, ticks, caption }
   */
  function bars(root, spec) {
    root.classList.add("chart", "chart-bars");
    const position = (value) => (value / spec.max) * 100;
    if (spec.series.length > 1) root.appendChild(legend(spec.series));
    const body = node("div", "chart-rows");
    const numbers = [];
    spec.rows.forEach((row) => {
      const line = node("div", "chart-row");
      line.appendChild(rowLabel(row));
      const plot = node("div", "chart-plot");
      grid(plot, spec.ticks, position, 0);
      spec.series.forEach((series) => {
        const value = row.values[series.key];
        if (!value) return;
        const track = node("div", "bar-track");
        const bar = node("span", "bar tone-" + series.tone);
        bar.style.width = position(value.v) + "%";
        track.appendChild(bar);
        let end = value.v;
        let detail = percent(value.v);
        if (value.lo !== undefined) {
          const whisker = node("span", "whisker");
          whisker.style.left = position(value.lo) + "%";
          whisker.style.width = position(value.hi - value.lo) + "%";
          track.appendChild(whisker);
          end = value.hi;
          detail += " " + range(value.lo, value.hi, 1);
        }
        const text = node("span", "bar-value", percent(value.v));
        text.style.left = position(end) + "%";
        track.appendChild(text);
        tooltip(track, [row.label + (row.note ? ", " + row.note : ""), series.name + ": " + detail]);
        plot.appendChild(track);
        numbers.push([row.label + (row.note ? ", " + row.note : ""), series.name, detail]);
      });
      line.appendChild(plot);
      body.appendChild(line);
    });
    const foot = node("div", "chart-row chart-foot");
    foot.appendChild(node("div", "chart-label"));
    foot.appendChild(axis(spec.ticks, position, (tick) => percent(tick, 0)));
    body.appendChild(foot);
    root.appendChild(body);
    root.appendChild(table(spec.caption, ["", "Rule", "Episodes scored as a capture"], numbers));
  }

  /*
   * spec: { rows: [{label, note, v, lo, hi, tone, strong}], domain: [min, max], ticks, digits,
   *         series (optional, for the legend), caption, unit }
   */
  function forest(root, spec) {
    root.classList.add("chart", "chart-forest");
    const [low, high] = spec.domain;
    const position = (value) => ((value - low) / (high - low)) * 100;
    const digits = spec.digits === undefined ? 1 : spec.digits;
    if (spec.series && spec.series.length > 1) root.appendChild(legend(spec.series));
    const body = node("div", "chart-rows");
    const numbers = [];
    spec.rows.forEach((row) => {
      if (row.heading) {
        body.appendChild(node("div", "chart-group", row.heading));
        return;
      }
      const line = node("div", "chart-row" + (row.strong ? " is-strong" : ""));
      line.appendChild(rowLabel(row));
      const plot = node("div", "chart-plot");
      grid(plot, spec.ticks, position, 0);
      const span = node("span", "interval tone-" + (row.tone || "ink"));
      span.style.left = position(row.lo) + "%";
      span.style.width = position(row.hi) - position(row.lo) + "%";
      plot.appendChild(span);
      const dot = node("span", "dot tone-" + (row.tone || "ink"));
      dot.style.left = position(row.v) + "%";
      plot.appendChild(dot);
      const detail = signed(row.v, digits) + " " + range(row.lo, row.hi, digits, true);
      tooltip(plot, [row.label + (row.note ? ", " + row.note : ""), detail + " " + spec.unit]);
      line.appendChild(plot);
      const value = node("div", "chart-value");
      value.appendChild(node("strong", "", signed(row.v, digits)));
      value.appendChild(node("span", "", " " + range(row.lo, row.hi, digits, true)));
      line.appendChild(value);
      body.appendChild(line);
      numbers.push([row.label + (row.note ? ", " + row.note : ""), signed(row.v, digits), range(row.lo, row.hi, digits, true)]);
    });
    const foot = node("div", "chart-row chart-foot");
    foot.appendChild(node("div", "chart-label"));
    foot.appendChild(axis(spec.ticks, position, (tick) => signed(tick, 0)));
    foot.appendChild(node("div", "chart-value"));
    body.appendChild(foot);
    root.appendChild(body);
    root.appendChild(table(spec.caption, ["", "Difference (" + spec.unit + ")", "Interval"], numbers));
  }

  /*
   * spec: { series: [{key, name, tone, shape}], rows: [{label, note, values: {key: number}}],
   *         domain: [min, max], ticks, caption }
   */
  function strip(root, spec) {
    root.classList.add("chart", "chart-strip");
    const [low, high] = spec.domain;
    const position = (value) => ((value - low) / (high - low)) * 100;
    root.appendChild(legend(spec.series));
    const body = node("div", "chart-rows");
    const numbers = [];
    spec.rows.forEach((row) => {
      if (row.heading) {
        body.appendChild(node("div", "chart-group", row.heading));
        return;
      }
      const line = node("div", "chart-row");
      line.appendChild(rowLabel(row));
      const plot = node("div", "chart-plot");
      grid(plot, spec.ticks, position, low);
      const present = spec.series.filter((series) => row.values[series.key] !== undefined);
      const values = present.map((series) => row.values[series.key]);
      const link = node("span", "link");
      link.style.left = position(Math.min(...values)) + "%";
      link.style.width = position(Math.max(...values)) - position(Math.min(...values)) + "%";
      plot.appendChild(link);
      const lines = [row.label + (row.note ? ", " + row.note : "")];
      present.forEach((series) => {
        const dot = node("span", "dot tone-" + series.tone + (series.shape ? " dot-" + series.shape : ""));
        dot.style.left = position(row.values[series.key]) + "%";
        plot.appendChild(dot);
        lines.push(series.name + ": " + percent(row.values[series.key]));
      });
      tooltip(plot, lines);
      line.appendChild(plot);
      body.appendChild(line);
      numbers.push([lines[0]].concat(present.map((series) => percent(row.values[series.key]))));
    });
    const foot = node("div", "chart-row chart-foot");
    foot.appendChild(node("div", "chart-label"));
    foot.appendChild(axis(spec.ticks, position, (tick) => percent(tick, 0)));
    body.appendChild(foot);
    root.appendChild(body);
    root.appendChild(table(spec.caption, [""].concat(spec.series.map((series) => series.name)), numbers));
  }

  window.Charts = { bars, forest, strip, percent, signed, fixed };
})();
