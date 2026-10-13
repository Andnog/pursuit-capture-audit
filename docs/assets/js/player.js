/*
 * Episode player: one pursuit episode, drawn to scale, with the state of every capture rule.
 *
 * Markup:  <div class="episode-player" data-src="assets/data/passing_cars.json"
 *               data-view="70" data-speed="1" data-start="0"></div>
 *
 * The data are written by tools/build_site_data.py. Nothing about the rules is decided here:
 * each frame carries, for the pursuer in focus, which conditions of the operational capture
 * rule hold (a bit mask) and for how long they have held. This script only draws.
 */
(function () {
  "use strict";

  const LABELS = {
    invalid_values: "values are valid",
    bodies_overlap: "the bodies do not touch",
    gap_below_minimum: "gap of at least 0.3 m",
    gap_above_maximum: "gap of at most 2.0 m",
    evader_moving: "evader at most 1 m/s",
    pursuer_moving: "pursuer at most 1 m/s",
    relative_speed: "speeds within 1 m/s of each other",
    headings_differ: "headings within 15°",
    evader_not_behind_pursuer: "evader behind the pursuer",
    lateral_offset: "lateral offset of at most 1 m",
  };
  const HIDDEN = new Set(["invalid_values", "relative_speed"]);
  const PROXIMITY_M = 5.0;
  const SPEEDS = [0.5, 1, 4, 10, 20];

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function formatTime(seconds) {
    return seconds === null || seconds === undefined ? "–" : seconds.toFixed(1) + " s";
  }

  class Player {
    constructor(root, data) {
      this.root = root;
      this.data = data;
      this.index = 0;
      this.position = 0;
      this.playing = false;
      this.viewMetres = parseFloat(root.dataset.view || (data.kind === "synthetic" ? "70" : "150"));
      this.speed = parseFloat(root.dataset.speed || (data.kind === "synthetic" ? "1" : "10"));
      this.step = data.times.length > 1 ? data.times[1] - data.times[0] : 0.1;
      this.build();
      const start = parseFloat(root.dataset.start || "0");
      this.seek(Math.max(0, data.times.findIndex((t) => t >= start)));
      new ResizeObserver(() => this.resize()).observe(this.canvas);
      this.resize();
    }

    build() {
      const data = this.data;
      this.root.innerHTML = "";
      this.root.appendChild(element("p", "ep-title", data.title));

      const stage = element("div", "ep-stage");
      this.canvas = element("canvas", "ep-canvas");
      this.canvas.setAttribute("role", "img");
      this.canvas.setAttribute("aria-label", "Animation of the episode: " + data.title);
      stage.appendChild(this.canvas);

      const panel = element("div", "ep-panel");
      this.proximityChip = this.chip(panel, "Proximity rule", "body gap ≤ 5 m");
      this.captureChip = this.chip(panel, "Operational capture", "held for 2 s");
      panel.appendChild(element("p", "ep-heading", "Conditions, for the nearest pursuer"));
      this.conditionNodes = [];
      const list = element("ul", "ep-conditions");
      data.conditions.forEach((name, bit) => {
        if (HIDDEN.has(name)) return;
        const item = element("li", "", LABELS[name] || name);
        list.appendChild(item);
        this.conditionNodes.push({ item, bit });
      });
      panel.appendChild(list);
      panel.appendChild(element("p", "ep-heading", "Held without interruption"));
      const bar = element("div", "ep-dwell");
      this.dwellFill = element("div", "ep-dwell-fill");
      bar.appendChild(this.dwellFill);
      panel.appendChild(bar);
      this.dwellText = element("p", "ep-readout", "");
      panel.appendChild(this.dwellText);
      this.readout = element("p", "ep-readout", "");
      panel.appendChild(this.readout);
      stage.appendChild(panel);
      this.root.appendChild(stage);

      const controls = element("div", "ep-controls");
      this.playButton = element("button", "ep-button", "Play");
      this.playButton.type = "button";
      this.playButton.addEventListener("click", () => this.toggle());
      controls.appendChild(this.playButton);
      this.slider = element("input", "ep-slider");
      this.slider.type = "range";
      this.slider.min = "0";
      this.slider.max = String(data.times.length - 1);
      this.slider.step = "1";
      this.slider.setAttribute("aria-label", "Time in the episode");
      this.slider.addEventListener("input", () => {
        this.pause();
        this.seek(parseInt(this.slider.value, 10));
      });
      controls.appendChild(this.slider);
      this.clock = element("span", "ep-clock", "");
      controls.appendChild(this.clock);
      const select = element("select", "ep-speed");
      select.setAttribute("aria-label", "Playback speed");
      SPEEDS.forEach((value) => {
        const option = element("option", "", value + "×");
        option.value = String(value);
        if (value === this.speed) option.selected = true;
        select.appendChild(option);
      });
      select.addEventListener("change", () => {
        this.speed = parseFloat(select.value);
      });
      controls.appendChild(select);
      this.root.appendChild(controls);

      const results = data.results;
      const summary =
        "In this episode the 5 m body-gap rule " +
        (results.body_5m.reached ? "is met at " + formatTime(results.body_5m.time) : "is never met") +
        ", and operational capture " +
        (results.oc.reached ? "is reached at " + formatTime(results.oc.time) : "is never reached") +
        ".";
      this.root.appendChild(element("p", "ep-summary", summary));
    }

    chip(parent, title, detail) {
      const node = element("div", "ep-chip");
      node.appendChild(element("span", "ep-chip-title", title));
      node.appendChild(element("span", "ep-chip-detail", detail));
      const state = element("span", "ep-chip-state", "not met");
      node.appendChild(state);
      parent.appendChild(node);
      return { node, state };
    }

    resize() {
      const ratio = window.devicePixelRatio || 1;
      const width = this.canvas.clientWidth;
      const height = this.canvas.clientHeight;
      if (!width || !height) return;
      this.canvas.width = Math.round(width * ratio);
      this.canvas.height = Math.round(height * ratio);
      this.draw();
    }

    toggle() {
      if (this.playing) this.pause();
      else this.play();
    }

    play() {
      if (this.index >= this.data.times.length - 1) this.seek(0);
      this.playing = true;
      this.playButton.textContent = "Pause";
      this.last = null;
      requestAnimationFrame((now) => this.tick(now));
    }

    pause() {
      this.playing = false;
      this.playButton.textContent = "Play";
    }

    tick(now) {
      if (!this.playing) return;
      if (this.last !== null) {
        this.position += ((now - this.last) / 1000) * (this.speed / this.step);
        const next = Math.min(this.data.times.length - 1, Math.floor(this.position));
        if (next !== this.index) this.seek(next, true);
        if (next >= this.data.times.length - 1) this.pause();
      }
      this.last = now;
      requestAnimationFrame((later) => this.tick(later));
    }

    seek(index, keepPosition) {
      this.index = index;
      if (!keepPosition) this.position = index;
      this.slider.value = String(index);
      this.update();
      this.draw();
    }

    vehicle(frame, slot) {
      const offset = slot * 4;
      if (frame[offset] === null) return null;
      return { x: frame[offset], y: frame[offset + 1], heading: frame[offset + 2], speed: frame[offset + 3] };
    }

    update() {
      const data = this.data;
      const i = this.index;
      const time = data.times[i];
      const results = data.results;
      this.clock.textContent = time.toFixed(1) + " s";

      const proximity = results.body_5m.reached && time >= results.body_5m.time;
      this.proximityChip.node.classList.toggle("is-on", proximity);
      this.proximityChip.state.textContent = proximity
        ? "met at " + formatTime(results.body_5m.time)
        : "not met";
      const captured = results.oc.reached && time >= results.oc.time;
      this.captureChip.node.classList.toggle("is-on", captured);
      this.captureChip.state.textContent = captured
        ? "reached at " + formatTime(results.oc.time)
        : "not reached";

      const mask = data.mask[i];
      this.conditionNodes.forEach(({ item, bit }) => {
        const holds = data.focus[i] >= 0 && (mask & (1 << bit)) !== 0;
        item.classList.toggle("holds", holds);
        item.classList.toggle("fails", !holds);
      });
      const run = data.run[i];
      this.dwellFill.style.width = Math.min(100, (run / data.dwell) * 100) + "%";
      this.dwellText.textContent = run.toFixed(1) + " s of " + data.dwell.toFixed(1) + " s";
      const evader = this.vehicle(data.frames[i], 0);
      const gap = data.gap[i];
      this.readout.textContent =
        "Gap to the nearest pursuer: " +
        (gap === null ? "–" : gap.toFixed(1) + " m") +
        ". Evader speed: " +
        (evader ? evader.speed.toFixed(1) + " m/s" : "–") +
        ".";
    }

    colours() {
      const style = getComputedStyle(this.root);
      const read = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
      return {
        ground: read("--ep-ground", "#eef1f4"),
        road: read("--ep-road", "#c5ccd4"),
        evader: read("--ep-evader", "#c0392b"),
        pursuer: read("--ep-pursuer", "#1f6feb"),
        focus: read("--ep-focus", "#0b3d91"),
        halo: read("--ep-halo", "#d98200"),
        text: read("--ep-text", "#1b1f24"),
      };
    }

    draw() {
      const canvas = this.canvas;
      const context = canvas.getContext("2d");
      if (!canvas.width) return;
      const data = this.data;
      const frame = data.frames[this.index];
      const colour = this.colours();
      const evader = this.vehicle(frame, 0);
      const centre = evader || this.lastCentre || { x: 0, y: 0 };
      this.lastCentre = centre;
      const scale = canvas.width / this.viewMetres;
      const toScreen = (x, y) => [
        canvas.width / 2 + (x - centre.x) * scale,
        canvas.height / 2 - (y - centre.y) * scale,
      ];

      context.setTransform(1, 0, 0, 1, 0, 0);
      context.fillStyle = colour.ground;
      context.fillRect(0, 0, canvas.width, canvas.height);

      context.strokeStyle = colour.road;
      context.lineCap = "round";
      context.lineJoin = "round";
      const reach = this.viewMetres;
      data.lanes.forEach((lane) => {
        const shape = lane.shape;
        const near = shape.some(
          (p) => Math.abs(p[0] - centre.x) < reach && Math.abs(p[1] - centre.y) < reach
        );
        if (!near) return;
        context.lineWidth = Math.max(1, lane.width * scale);
        context.beginPath();
        shape.forEach((p, k) => {
          const [sx, sy] = toScreen(p[0], p[1]);
          if (k === 0) context.moveTo(sx, sy);
          else context.lineTo(sx, sy);
        });
        context.stroke();
      });

      const body = (vehicle, fill, outline) => {
        const [sx, sy] = toScreen(vehicle.x, vehicle.y);
        context.save();
        context.translate(sx, sy);
        context.rotate(-vehicle.heading);
        if (outline) {
          const margin = PROXIMITY_M * scale;
          const halfLength = (data.length / 2) * scale + margin;
          const halfWidth = (data.width / 2) * scale + margin;
          context.beginPath();
          context.roundRect(-halfLength, -halfWidth, 2 * halfLength, 2 * halfWidth, margin);
          context.setLineDash([6 * (window.devicePixelRatio || 1), 5 * (window.devicePixelRatio || 1)]);
          context.lineWidth = 1.5 * (window.devicePixelRatio || 1);
          context.strokeStyle = colour.halo;
          context.stroke();
          context.setLineDash([]);
          if (outline === "inside") {
            context.globalAlpha = 0.16;
            context.fillStyle = colour.halo;
            context.fill();
            context.globalAlpha = 1;
          }
        }
        context.fillStyle = fill;
        context.fillRect(
          (-data.length / 2) * scale,
          (-data.width / 2) * scale,
          data.length * scale,
          data.width * scale
        );
        context.fillStyle = "rgba(255,255,255,0.75)";
        context.fillRect((data.length / 2 - 0.9) * scale, (-data.width / 2) * scale, 0.5 * scale, data.width * scale);
        context.restore();
      };

      const gap = data.gap[this.index];
      if (evader) body(evader, colour.evader, gap !== null && gap <= PROXIMITY_M ? "inside" : "outside");
      const focus = data.focus[this.index];
      for (let slot = 1; slot < data.vehicles.length; slot += 1) {
        const pursuer = this.vehicle(frame, slot);
        if (pursuer) body(pursuer, slot === focus ? colour.focus : colour.pursuer, null);
      }

      const ratio = window.devicePixelRatio || 1;
      context.fillStyle = colour.text;
      context.font = 12 * ratio + "px system-ui, sans-serif";
      const label = (vehicle, text) => {
        const [sx, sy] = toScreen(vehicle.x, vehicle.y);
        context.fillText(text, sx + 8 * ratio, sy - 8 * ratio);
      };
      if (evader) label(evader, "evader");
      for (let slot = 1; slot < data.vehicles.length; slot += 1) {
        const pursuer = this.vehicle(frame, slot);
        if (pursuer) label(pursuer, data.vehicles[slot]);
      }

      const bar = 10 * scale;
      const left = 14 * ratio;
      const bottom = canvas.height - 14 * ratio;
      context.strokeStyle = colour.text;
      context.lineWidth = 2 * ratio;
      context.beginPath();
      context.moveTo(left, bottom);
      context.lineTo(left + bar, bottom);
      context.stroke();
      context.fillText("10 m", left, bottom - 6 * ratio);
    }
  }

  function setup() {
    document.querySelectorAll(".episode-player:not([data-ready])").forEach((root) => {
      root.dataset.ready = "1";
      const source = new URL(root.dataset.src, document.baseURI).href;
      fetch(source)
        .then((response) => {
          if (!response.ok) throw new Error(response.status + " " + source);
          return response.json();
        })
        .then((data) => new Player(root, data))
        .catch((error) => {
          root.textContent = "The animation could not be loaded (" + error.message + ").";
        });
    });
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(setup);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    setup();
  }
})();
