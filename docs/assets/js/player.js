/*
 * Episode player: one pursuit episode drawn to scale, with the verdict of each capture rule.
 *
 *   <div class="player" data-src="assets/data/passing_cars.json"></div>
 *   <div class="player" data-sources='[{"label": "Pursuit", "src": "..."}, ...]'></div>
 *
 * Optional attributes: data-view (metres across), data-speed, data-start (seconds), data-loop.
 *
 * The data are written by tools/build_site_data.py. Nothing about the rules is decided here:
 * each frame carries, for the pursuer in focus, which conditions of the operational capture rule
 * hold (a bit mask) and for how long they have held. This script only draws.
 */
(function () {
  "use strict";

  const LABELS = {
    bodies_overlap: "bodies apart",
    gap_below_minimum: "gap ≥ 0.3 m",
    gap_above_maximum: "gap ≤ 2 m",
    evader_moving: "evader ≤ 1 m/s",
    pursuer_moving: "pursuer ≤ 1 m/s",
    headings_differ: "headings within 15°",
    evader_not_behind_pursuer: "evader behind",
    lateral_offset: "in file (≤ 1 m aside)",
  };
  const PROXIMITY_M = 5.0;
  const SPEEDS = [1, 4, 10, 20];
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ICON_PLAY = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z"/></svg>';
  const ICON_PAUSE = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg>';

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }

  function seconds(value) {
    return value.toFixed(1) + " s";
  }

  function mixAngle(a, b, t) {
    let delta = b - a;
    while (delta > Math.PI) delta -= 2 * Math.PI;
    while (delta < -Math.PI) delta += 2 * Math.PI;
    return a + delta * t;
  }

  class Player {
    constructor(root) {
      this.root = root;
      this.sources = root.dataset.sources
        ? JSON.parse(root.dataset.sources)
        : [{ label: "", src: root.dataset.src, start: root.dataset.start }];
      this.cache = new Map();
      this.playing = false;
      this.visible = false;
      this.touched = false;
      this.position = 0;
      this.camera = null;
      this.scaffold();
      this.select(0);
      new ResizeObserver(() => this.resize()).observe(this.canvas);
      new IntersectionObserver(
        (entries) => {
          this.visible = entries[0].isIntersecting;
          if (!this.visible) this.pause(true);
          else if (!REDUCED && !this.touched && this.data) this.play();
        },
        { threshold: 0.45 }
      ).observe(this.canvas);
    }

    scaffold() {
      const root = this.root;
      root.innerHTML = "";
      if (this.sources.length > 1) {
        const tabs = node("div", "player-tabs");
        tabs.setAttribute("role", "tablist");
        this.tabs = this.sources.map((source, index) => {
          const tab = node("button", "player-tab", source.label);
          tab.type = "button";
          tab.setAttribute("role", "tab");
          tab.addEventListener("click", () => {
            this.touched = false;
            this.select(index);
          });
          tabs.appendChild(tab);
          return tab;
        });
        root.appendChild(tabs);
      }

      const verdicts = node("div", "player-verdicts");
      this.proximity = this.verdict(verdicts, "prox", "5 m rule");
      this.capture = this.verdict(verdicts, "oc", "Operational capture");
      root.appendChild(verdicts);

      this.canvas = node("canvas", "player-canvas");
      this.canvas.setAttribute("role", "img");
      root.appendChild(this.canvas);

      const bar = node("div", "player-bar");
      this.button = node("button", "player-button");
      this.button.type = "button";
      this.button.innerHTML = ICON_PLAY;
      this.button.setAttribute("aria-label", "Play");
      this.button.addEventListener("click", () => {
        this.touched = true;
        if (this.playing) this.pause();
        else this.play();
      });
      bar.appendChild(this.button);

      const track = node("div", "player-track");
      this.marks = node("div", "player-marks");
      track.appendChild(this.marks);
      this.slider = node("input", "player-slider");
      this.slider.type = "range";
      this.slider.min = "0";
      this.slider.step = "1";
      this.slider.setAttribute("aria-label", "Time in the episode");
      this.slider.addEventListener("input", () => {
        this.touched = true;
        this.pause();
        this.seek(parseInt(this.slider.value, 10));
      });
      track.appendChild(this.slider);
      bar.appendChild(track);

      this.clock = node("span", "player-clock", "");
      bar.appendChild(this.clock);
      this.speedButton = node("button", "player-speed", "");
      this.speedButton.type = "button";
      this.speedButton.setAttribute("aria-label", "Playback speed");
      this.speedButton.addEventListener("click", () => {
        const next = SPEEDS[(SPEEDS.indexOf(this.speed) + 1) % SPEEDS.length];
        this.setSpeed(next);
      });
      bar.appendChild(this.speedButton);
      root.appendChild(bar);

      const conditions = node("div", "player-conditions");
      this.pills = node("div", "player-pills");
      conditions.appendChild(this.pills);
      const dwell = node("div", "player-dwell");
      this.dwellFill = node("span", "player-dwell-fill");
      const meter = node("span", "player-dwell-track");
      meter.appendChild(this.dwellFill);
      dwell.appendChild(meter);
      this.dwellText = node("span", "player-dwell-text", "");
      dwell.appendChild(this.dwellText);
      conditions.appendChild(dwell);
      root.appendChild(conditions);
    }

    verdict(parent, kind, title) {
      const item = node("div", "verdict verdict-" + kind);
      item.appendChild(node("span", "verdict-dot"));
      item.appendChild(node("span", "verdict-title", title));
      const state = node("span", "verdict-state", "");
      item.appendChild(state);
      parent.appendChild(item);
      return { item, state };
    }

    select(index) {
      this.pause(true);
      this.current = index;
      if (this.tabs) {
        this.tabs.forEach((tab, i) => tab.setAttribute("aria-selected", i === index ? "true" : "false"));
      }
      const source = this.sources[index];
      const url = new URL(source.src, document.baseURI).href;
      const ready = (data) => {
        this.load(data, source);
        if (this.visible && !REDUCED && !this.touched) this.play();
      };
      if (this.cache.has(url)) {
        ready(this.cache.get(url));
        return;
      }
      fetch(url)
        .then((response) => {
          if (!response.ok) throw new Error(String(response.status));
          return response.json();
        })
        .then((data) => {
          data.lanes.forEach((lane) => {
            const xs = lane.shape.map((p) => p[0]);
            const ys = lane.shape.map((p) => p[1]);
            lane.box = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
          });
          this.cache.set(url, data);
          if (this.current === index) ready(data);
        })
        .catch(() => {
          this.canvas.replaceWith(node("p", "player-error", "The animation could not be loaded."));
        });
    }

    load(data, source) {
      this.data = data;
      this.step = data.times.length > 1 ? data.times[1] - data.times[0] : 0.1;
      this.viewMetres = parseFloat(this.root.dataset.view || (data.kind === "synthetic" ? "64" : "150"));
      this.loop = this.root.dataset.loop !== undefined || data.kind === "synthetic";
      this.setSpeed(parseFloat(this.root.dataset.speed || (data.kind === "synthetic" ? "1" : "10")));
      this.canvas.setAttribute("aria-label", "Animation: " + data.title);
      this.slider.max = String(data.times.length - 1);

      this.pills.innerHTML = "";
      this.pillNodes = [];
      data.conditions.forEach((name, bit) => {
        if (!LABELS[name]) return;
        const pill = node("span", "pill", LABELS[name]);
        this.pills.appendChild(pill);
        this.pillNodes.push({ pill, bit });
      });

      const last = data.times[data.times.length - 1] || 1;
      this.marks.innerHTML = "";
      const mark = (result, kind) => {
        if (!result.reached) return;
        const tick = node("span", "mark mark-" + kind);
        tick.style.left = (result.time / last) * 100 + "%";
        this.marks.appendChild(tick);
      };
      mark(data.results.body_5m, "prox");
      mark(data.results.oc, "oc");

      const xs = [];
      const ys = [];
      data.lanes.forEach((lane) => {
        xs.push(lane.box[0], lane.box[2]);
        ys.push(lane.box[1], lane.box[3]);
      });
      this.extent = xs.length ? [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] : null;
      this.overview =
        data.kind === "simulated" &&
        this.extent &&
        Math.max(this.extent[2] - this.extent[0], this.extent[3] - this.extent[1]) > 2.5 * this.viewMetres;

      const start = parseFloat(source.start || this.root.dataset.start || "0");
      this.startIndex = Math.max(0, data.times.findIndex((t) => t >= start));
      this.camera = null;
      this.seek(this.startIndex);
      this.resize();
    }

    setSpeed(value) {
      this.speed = value;
      this.speedButton.textContent = value + "×";
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

    play() {
      if (!this.data || this.playing) return;
      if (this.position >= this.data.times.length - 1) this.seek(this.startIndex);
      this.playing = true;
      this.button.innerHTML = ICON_PAUSE;
      this.button.setAttribute("aria-label", "Pause");
      this.last = null;
      requestAnimationFrame((now) => this.tick(now));
    }

    pause(silent) {
      this.playing = false;
      if (silent && !this.button) return;
      this.button.innerHTML = ICON_PLAY;
      this.button.setAttribute("aria-label", "Play");
    }

    tick(now) {
      if (!this.playing) return;
      if (this.last !== null) {
        const end = this.data.times.length - 1;
        this.position = Math.min(end, this.position + ((now - this.last) / 1000) * (this.speed / this.step));
        this.update();
        this.draw();
        if (this.position >= end) {
          if (this.loop && !this.touched) {
            this.playing = false;
            setTimeout(() => {
              if (this.visible && !this.touched) {
                this.seek(this.startIndex);
                this.play();
              } else {
                this.pause();
              }
            }, 1400);
            return;
          }
          this.pause();
          return;
        }
      }
      this.last = now;
      requestAnimationFrame((later) => this.tick(later));
    }

    seek(index) {
      this.position = index;
      this.camera = null;
      this.update();
      this.draw();
    }

    vehicle(slot) {
      const frames = this.data.frames;
      const i = Math.min(frames.length - 1, Math.floor(this.position));
      const j = Math.min(frames.length - 1, i + 1);
      const t = this.position - i;
      const a = frames[i];
      const b = frames[j];
      const o = slot * 4;
      if (a[o] === null) return null;
      if (b[o] === null || t === 0) return { x: a[o], y: a[o + 1], heading: a[o + 2], speed: a[o + 3] };
      return {
        x: a[o] + (b[o] - a[o]) * t,
        y: a[o + 1] + (b[o + 1] - a[o + 1]) * t,
        heading: mixAngle(a[o + 2], b[o + 2], t),
        speed: a[o + 3] + (b[o + 3] - a[o + 3]) * t,
      };
    }

    update() {
      const data = this.data;
      const i = Math.min(data.times.length - 1, Math.floor(this.position));
      const time = data.times[i];
      const results = data.results;
      this.slider.value = String(i);
      this.clock.textContent = seconds(time);

      const fired = results.body_5m.reached && time >= results.body_5m.time;
      this.proximity.item.classList.toggle("is-on", fired);
      this.proximity.state.textContent = fired ? "capture at " + seconds(results.body_5m.time) : "no capture";
      const captured = results.oc.reached && time >= results.oc.time;
      this.capture.item.classList.toggle("is-on", captured);
      this.capture.state.textContent = captured ? "capture at " + seconds(results.oc.time) : "no capture";

      const mask = data.mask[i];
      const focused = data.focus[i] >= 0;
      this.pillNodes.forEach(({ pill, bit }) => {
        pill.classList.toggle("holds", focused && (mask & (1 << bit)) !== 0);
      });
      const run = data.run[i];
      this.dwellFill.style.width = Math.min(100, (run / data.dwell) * 100) + "%";
      this.dwellText.textContent = "held " + run.toFixed(1) + " of " + data.dwell.toFixed(0) + " s";
    }

    palette() {
      const style = getComputedStyle(this.root);
      const read = (name) => style.getPropertyValue(name).trim();
      return {
        ground: read("--p-ground"),
        road: read("--p-road"),
        evader: read("--p-evader"),
        pursuer: read("--p-pursuer"),
        focus: read("--p-focus"),
        prox: read("--prox"),
        oc: read("--oc"),
        text: read("--ink-2"),
        trail: read("--p-trail"),
        surface: read("--surface"),
      };
    }

    draw() {
      const canvas = this.canvas;
      const data = this.data;
      if (!data || !canvas.width) return;
      const c = canvas.getContext("2d");
      const ratio = window.devicePixelRatio || 1;
      const colour = this.palette();
      const i = Math.min(data.times.length - 1, Math.floor(this.position));
      const evader = this.vehicle(0);

      const target = evader || this.camera || { x: 0, y: 0 };
      if (!this.camera) this.camera = { x: target.x, y: target.y };
      this.camera.x += (target.x - this.camera.x) * 0.18;
      this.camera.y += (target.y - this.camera.y) * 0.18;
      const centre = this.camera;
      const scale = canvas.width / this.viewMetres;
      const halfW = this.viewMetres / 2;
      const halfH = canvas.height / scale / 2;
      const sx = (x) => canvas.width / 2 + (x - centre.x) * scale;
      const sy = (y) => canvas.height / 2 - (y - centre.y) * scale;

      c.setTransform(1, 0, 0, 1, 0, 0);
      c.fillStyle = colour.ground;
      c.fillRect(0, 0, canvas.width, canvas.height);

      // Lanes: every lane whose bounding box touches the view, so a long straight street is
      // drawn even when both of its ends are far outside the picture.
      c.strokeStyle = colour.road;
      c.lineCap = "round";
      c.lineJoin = "round";
      const pad = 6;
      data.lanes.forEach((lane) => {
        const box = lane.box;
        if (
          box[2] < centre.x - halfW - pad ||
          box[0] > centre.x + halfW + pad ||
          box[3] < centre.y - halfH - pad ||
          box[1] > centre.y + halfH + pad
        ) {
          return;
        }
        c.lineWidth = lane.width * scale + ratio;
        c.beginPath();
        lane.shape.forEach((p, k) => {
          if (k === 0) c.moveTo(sx(p[0]), sy(p[1]));
          else c.lineTo(sx(p[0]), sy(p[1]));
        });
        c.stroke();
      });

      // The way the evader has come.
      c.strokeStyle = colour.trail;
      c.lineWidth = 1.5 * ratio;
      c.beginPath();
      let started = false;
      for (let k = 0; k <= i; k += 1) {
        const x = data.frames[k][0];
        if (x === null) continue;
        const px = sx(x);
        const py = sy(data.frames[k][1]);
        if (started) c.lineTo(px, py);
        else c.moveTo(px, py);
        started = true;
      }
      if (evader && started) c.lineTo(sx(evader.x), sy(evader.y));
      c.stroke();

      // Where each rule declared its capture.
      const pin = (result, tone, label) => {
        if (!result.reached || data.times[i] < result.time) return;
        const k = data.times.findIndex((t) => t >= result.time);
        const frame = data.frames[Math.max(0, k)];
        if (frame[0] === null) return;
        const px = sx(frame[0]);
        const py = sy(frame[1]);
        c.fillStyle = colour.surface;
        c.beginPath();
        c.arc(px, py, 7 * ratio, 0, 2 * Math.PI);
        c.fill();
        c.fillStyle = tone;
        c.beginPath();
        c.arc(px, py, 4.5 * ratio, 0, 2 * Math.PI);
        c.fill();
        c.font = "600 " + 11 * ratio + "px system-ui, sans-serif";
        c.fillStyle = colour.text;
        c.fillText(label + " · " + seconds(result.time), px + 11 * ratio, py + 4 * ratio);
      };
      pin(data.results.body_5m, colour.prox, "5 m rule");
      pin(data.results.oc, colour.oc, "operational capture");

      const body = (vehicle, fill, ring) => {
        c.save();
        c.translate(sx(vehicle.x), sy(vehicle.y));
        c.rotate(-vehicle.heading);
        const length = data.length * scale;
        const width = data.width * scale;
        c.fillStyle = fill;
        c.beginPath();
        c.roundRect(-length / 2, -width / 2, length, width, Math.min(width / 3, 3 * ratio));
        c.fill();
        if (ring) {
          c.lineWidth = 2 * ratio;
          c.strokeStyle = ring;
          c.stroke();
        }
        c.fillStyle = colour.surface;
        c.globalAlpha = 0.75;
        c.fillRect(length / 2 - 0.95 * scale, -width / 2 + 0.2 * scale, 0.45 * scale, width - 0.4 * scale);
        c.globalAlpha = 1;
        c.restore();
      };

      const gap = data.gap[i];
      if (evader) {
        c.save();
        c.translate(sx(evader.x), sy(evader.y));
        c.rotate(-evader.heading);
        const margin = PROXIMITY_M * scale;
        const halfLength = (data.length / 2) * scale + margin;
        const halfWidth = (data.width / 2) * scale + margin;
        c.beginPath();
        c.roundRect(-halfLength, -halfWidth, 2 * halfLength, 2 * halfWidth, margin);
        if (gap !== null && gap <= PROXIMITY_M) {
          c.globalAlpha = 0.14;
          c.fillStyle = colour.prox;
          c.fill();
          c.globalAlpha = 1;
        }
        c.setLineDash([5 * ratio, 4 * ratio]);
        c.lineWidth = 1.5 * ratio;
        c.strokeStyle = colour.prox;
        c.stroke();
        c.restore();
      }

      const focus = data.focus[i];
      const holding = data.run[i] > 0 || (focus >= 0 && this.allHold(i));
      for (let slot = 1; slot < data.vehicles.length; slot += 1) {
        const pursuer = this.vehicle(slot);
        if (!pursuer) continue;
        const inFocus = slot === focus;
        body(pursuer, inFocus ? colour.focus : colour.pursuer, inFocus && holding ? colour.oc : null);
      }
      if (evader) body(evader, colour.evader, holding ? colour.oc : null);

      // The dwell, as an arc that closes around the evader.
      if (evader && data.run[i] > 0) {
        const share = Math.min(1, data.run[i] / data.dwell);
        c.strokeStyle = colour.oc;
        c.lineWidth = 3 * ratio;
        c.beginPath();
        c.arc(sx(evader.x), sy(evader.y), (data.length / 2 + 1.6) * scale, -Math.PI / 2, -Math.PI / 2 + share * 2 * Math.PI);
        c.stroke();
      }

      c.font = 11 * ratio + "px system-ui, sans-serif";
      c.fillStyle = colour.text;
      const tag = (vehicle, text) => {
        const reach =
          (Math.abs(Math.sin(vehicle.heading)) * data.length + Math.abs(Math.cos(vehicle.heading)) * data.width) / 2;
        const width = c.measureText(text).width;
        c.fillText(text, sx(vehicle.x) - width / 2, sy(vehicle.y) - reach * scale - 7 * ratio);
      };
      if (evader) tag(evader, "evader");
      if (data.vehicles.length <= 3) {
        for (let slot = 1; slot < data.vehicles.length; slot += 1) {
          const pursuer = this.vehicle(slot);
          if (pursuer) tag(pursuer, "pursuer");
        }
      }

      const bar = 10 * scale;
      const left = 14 * ratio;
      const bottom = canvas.height - 14 * ratio;
      c.strokeStyle = colour.text;
      c.lineWidth = 1.5 * ratio;
      c.beginPath();
      c.moveTo(left, bottom);
      c.lineTo(left + bar, bottom);
      c.stroke();
      c.fillText("10 m", left, bottom - 6 * ratio);

      if (this.overview) this.drawOverview(c, colour, ratio, i, evader);
    }

    allHold(i) {
      const data = this.data;
      return this.pillNodes.every(({ bit }) => (data.mask[i] & (1 << bit)) !== 0);
    }

    drawOverview(c, colour, ratio, i, evader) {
      const data = this.data;
      const [x0, y0, x1, y1] = this.extent;
      const width = Math.min(168, this.canvas.clientWidth * 0.3) * ratio;
      const height = (width * (y1 - y0)) / (x1 - x0);
      const left = this.canvas.width - width - 12 * ratio;
      const top = 12 * ratio;
      const mx = (x) => left + ((x - x0) / (x1 - x0)) * width;
      const my = (y) => top + height - ((y - y0) / (y1 - y0)) * height;
      c.fillStyle = colour.surface;
      c.globalAlpha = 0.92;
      c.beginPath();
      c.roundRect(left - 6 * ratio, top - 6 * ratio, width + 12 * ratio, height + 12 * ratio, 6 * ratio);
      c.fill();
      c.globalAlpha = 1;
      c.strokeStyle = colour.road;
      c.lineWidth = ratio;
      data.lanes.forEach((lane) => {
        if (lane.internal) return;
        c.beginPath();
        lane.shape.forEach((p, k) => {
          if (k === 0) c.moveTo(mx(p[0]), my(p[1]));
          else c.lineTo(mx(p[0]), my(p[1]));
        });
        c.stroke();
      });
      c.strokeStyle = colour.evader;
      c.lineWidth = 1.5 * ratio;
      c.beginPath();
      let started = false;
      for (let k = 0; k <= i; k += 2) {
        const x = data.frames[k][0];
        if (x === null) continue;
        if (started) c.lineTo(mx(x), my(data.frames[k][1]));
        else c.moveTo(mx(x), my(data.frames[k][1]));
        started = true;
      }
      c.stroke();
      for (let slot = 1; slot < data.vehicles.length; slot += 1) {
        const pursuer = this.vehicle(slot);
        if (!pursuer) continue;
        c.fillStyle = colour.pursuer;
        c.beginPath();
        c.arc(mx(pursuer.x), my(pursuer.y), 2.5 * ratio, 0, 2 * Math.PI);
        c.fill();
      }
      if (evader) {
        c.fillStyle = colour.evader;
        c.beginPath();
        c.arc(mx(evader.x), my(evader.y), 3.5 * ratio, 0, 2 * Math.PI);
        c.fill();
      }
    }
  }

  function setup() {
    document.querySelectorAll(".player:not([data-ready])").forEach((root) => {
      root.dataset.ready = "1";
      new Player(root);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup);
  else setup();
})();
