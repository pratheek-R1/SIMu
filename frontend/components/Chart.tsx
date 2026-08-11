"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useStore } from "@/lib/store";

/** Canvas cannot resolve `var(--x)`, so chart colours are read off the document
 *  root at use time rather than baked in. Reading lazily (rather than at module
 *  scope) is what lets the palette follow `data-theme` without a rebuild.
 *
 *  Fallbacks are the dark theme's values, used during server rendering where
 *  there is no document to compute against. */
const FALLBACKS: Record<string, string> = {
  "--chart-primary": "#2dd4bf",
  "--chart-accent": "#5eead4",
  "--chart-positive": "#2dd4bf",
  "--chart-negative": "#f2776a",
  "--chart-neutral": "#9fb3ac",
  "--chart-muted": "rgba(255,255,255,.46)",
  "--chart-grid": "rgba(94,234,212,.1)",
  "--chart-axis": "rgba(255,255,255,.55)",
};

function token(name: string): string {
  if (typeof document === "undefined") return FALLBACKS[name];
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || FALLBACKS[name];
}

/** Names are kept from the previous palette so every call site still reads
 *  COLORS.GREEN for "this series is the good one". What they resolve to is now
 *  a theme token, not a hex literal. */
export const COLORS = {
  get NAVY() { return token("--chart-neutral"); },
  get ORANGE() { return token("--chart-accent"); },
  get GREEN() { return token("--chart-positive"); },
  get RED() { return token("--chart-negative"); },
  get MUTED() { return token("--chart-muted"); },
  get PRIMARY() { return token("--chart-primary"); },
};

/** Canvas will not resolve `var(--font-mono)` inside a font string -- the whole
 *  declaration fails to parse and the context silently keeps the previous font.
 *  Every axis and value label in the prototype was therefore drawn in default
 *  sans, not the mono it asked for. Canvas needs real family names. */
export const MONO = '"Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace';



function roundedRect(
  ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number,
) {
  r = Math.min(r, w / 2, Math.abs(h) / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

/** Tick values on a 1/2/5 x 10^n ladder, so labels land on numbers a person
 *  would actually say out loud. */
function niceTicks(lo: number, hi: number, target = 5): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [lo];
  const raw = (hi - lo) / target;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) {
    out.push(Math.abs(t) < step * 1e-9 ? 0 : t);
  }
  return out;
}

function fmt(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (a >= 10000) return `${Math.round(v / 1000)}k`;
  if (a >= 100) return String(Math.round(v));
  if (a >= 10) return v.toFixed(1).replace(/\.0$/, "");
  if (a >= 1) return v.toFixed(2).replace(/\.?0+$/, "");
  if (a === 0) return "0";
  return v.toFixed(3).replace(/\.?0+$/, "");
}

/* --------------------------------------------------------------------------
   Canvas plumbing
   -------------------------------------------------------------------------- */

/** DPR-aware canvas that redraws on resize, on `deps` change, and once the
 *  webfonts land (text measured before the mono loads is measured wrong). */
function useCanvas(
  height: number,
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void,
  deps: unknown[],
) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drawRef = useRef(draw);
  drawRef.current = draw;

  const render = useCallback(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = c.offsetWidth;
    if (!w) return;
    c.width = Math.round(w * dpr);
    c.height = Math.round(height * dpr);
    c.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, height);
    drawRef.current(ctx, w, height);
  }, [height]);

  useLayoutEffect(() => {
    render();
    const c = ref.current;
    if (!c) return;
    const ro = new ResizeObserver(render);
    ro.observe(c);
    let alive = true;
    void document.fonts?.ready.then(() => { if (alive) render(); });
    return () => { alive = false; ro.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [render, ...deps]);

  return { ref, render };
}

/** Drives a 0→1 progress value for entry animations. Restarts when `key`
 *  changes, and resolves immediately for reduced-motion users. */
function useIntro(duration: number, key: unknown) {
  const progress = useRef(0);
  const [, force] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      progress.current = 1;
      force((n) => n + 1);
      return;
    }
    progress.current = 0;
    let raf = 0;
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      // easeOutCubic
      progress.current = 1 - Math.pow(1 - t, 3);
      force((n) => n + 1);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [duration, key]);

  return progress;
}

interface CanvasProps {
  chartId: string;
  height?: number;
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void;
  ariaLabel: string;
}

/** Plain canvas for callers that draw something bespoke (the company profile's
 *  small multiples). Reports engagement exactly once, on first hover.
 *
 *  In the prototype chart credit fired on `openWin()` -- opening a company
 *  profile awarded full chart-engagement points without a chart ever being
 *  looked at. Credit is tied to the chart itself here. */
export function ChartCanvas({ chartId, height = 200, draw, ariaLabel }: CanvasProps) {
  const { chartSeen } = useStore();
  const { ref } = useCanvas(height, draw, [draw]);
  return (
    <div className="chart-wrap">
      <canvas
        ref={ref}
        role="img"
        aria-label={ariaLabel}
        onMouseEnter={() => chartSeen(chartId)}
        onFocus={() => chartSeen(chartId)}
        tabIndex={0}
      />
    </div>
  );
}

/* --------------------------------------------------------------------------
   Tooltip
   -------------------------------------------------------------------------- */

interface TipRow { k: string; v: string }

function Tooltip({
  x, y, title, color, rows, width,
}: { x: number; y: number; title: string; color?: string; rows: TipRow[]; width: number }) {
  // Keep the card inside the plot even when the mark is near an edge.
  const clamped = Math.max(66, Math.min(width - 66, x));
  return (
    <div className="chart-tip" style={{ left: clamped, top: y }}>
      <div className="tip-title">
        {color && <span className="dot" style={{ background: color }} />}
        {title}
      </div>
      {rows.map((r) => (
        <div className="tip-row" key={r.k}>
          <span className="tk">{r.k}</span>
          <span className="tv">{r.v}</span>
        </div>
      ))}
    </div>
  );
}

/* --------------------------------------------------------------------------
   Bars
   -------------------------------------------------------------------------- */

export interface Bar { label: string; value: number; color?: string; note?: string }

/** Vertical bars with value labels. `max` defaults to the tallest bar.
 *
 *  Hovering (or arrowing through) a bar dims its neighbours and opens a
 *  readout, so a column can be read exactly rather than estimated against the
 *  gridline. */
export function BarChart({
  chartId, bars, max, height = 200, suffix = "", ariaLabel, valueLabel = "Value",
}: {
  chartId: string; bars: Bar[]; max?: number; height?: number; suffix?: string;
  ariaLabel: string; valueLabel?: string;
}) {
  const { chartSeen } = useStore();
  const [hover, setHover] = useState<number | null>(null);
  const [w, setW] = useState(0);
  const intro = useIntro(560, bars.map((b) => `${b.label}:${b.value}`).join("|"));

  const top = max ?? Math.max(...bars.map((b) => b.value), 1);
  const PAD_T = 26, PAD_B = 24;

  const geom = useCallback(
    (width: number, i: number) => {
      const bw = width / bars.length;
      const inset = Math.min(14, bw * 0.16);
      return { x: i * bw + inset, w: bw - inset * 2, bw };
    },
    [bars.length],
  );

  const { ref } = useCanvas(
    height,
    (ctx, width, h) => {
      if (!bars.length) return;
      setW(width);
      const plotH = h - PAD_T - PAD_B;
      ctx.font = `500 10px ${MONO}`;
      ctx.textAlign = "center";

      // Baseline.
      ctx.strokeStyle = token("--chart-grid");
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, h - PAD_B + 0.5);
      ctx.lineTo(width, h - PAD_B + 0.5);
      ctx.stroke();

      bars.forEach((b, i) => {
        // Each bar starts a beat after the one before it.
        const stagger = Math.max(0, Math.min(1, intro.current * 1.6 - i * 0.08));
        const eased = 1 - Math.pow(1 - stagger, 3);
        const full = top > 0 ? (b.value / top) * plotH : 0;
        const bh = full * eased;
        const { x, w: barW } = geom(width, i);
        const y = h - PAD_B - bh;
        const dim = hover !== null && hover !== i;

        ctx.globalAlpha = dim ? 0.28 : 1;
        ctx.fillStyle = b.color ?? COLORS.PRIMARY;
        roundedRect(ctx, x, y, barW, bh, 5);
        ctx.fill();

        if (hover === i) {
          ctx.globalAlpha = 0.18;
          roundedRect(ctx, x - 4, h - PAD_B - full - 4, barW + 8, full + 8, 7);
          ctx.fill();
          ctx.globalAlpha = 1;
        }

        ctx.globalAlpha = dim ? 0.35 : 1;
        ctx.fillStyle = token("--chart-muted");
        ctx.fillText(b.label, x + barW / 2, h - 7);
        // The readout replaces the printed value while a bar is hovered --
        // otherwise the tooltip lands on top of its own number.
        if (hover !== i) {
          ctx.fillStyle = COLORS.PRIMARY;
          ctx.fillText(
            `${Number.isInteger(b.value) ? b.value : b.value.toFixed(1)}${suffix}`,
            x + barW / 2, Math.max(11, y - 8),
          );
        }
        ctx.globalAlpha = 1;
      });
    },
    [bars, top, hover, height, intro.current],
  );

  const onMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = Math.floor(((e.clientX - r.left) / r.width) * bars.length);
    setHover(i >= 0 && i < bars.length ? i : null);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    setHover((h) => {
      const next = h === null ? 0 : h + (e.key === "ArrowRight" ? 1 : -1);
      return Math.max(0, Math.min(bars.length - 1, next));
    });
  };

  const hb = hover !== null ? bars[hover] : null;
  const g = hover !== null && w ? geom(w, hover) : null;

  return (
    <div className="chart-wrap bars">
      <canvas
        ref={ref}
        role="img"
        aria-label={ariaLabel}
        tabIndex={0}
        onMouseEnter={() => chartSeen(chartId)}
        onFocus={() => chartSeen(chartId)}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onBlur={() => setHover(null)}
        onKeyDown={onKey}
      />
      {hb && g && (
        <Tooltip
          x={g.x + g.w / 2}
          y={height - PAD_B - (top > 0 ? (hb.value / top) * (height - PAD_T - PAD_B) : 0)}
          title={hb.label}
          color={hb.color ?? COLORS.PRIMARY}
          width={w}
          rows={[
            { k: valueLabel, v: `${hb.value.toLocaleString("en-IN")}${suffix}` },
            ...(hb.note ? [{ k: "Note", v: hb.note }] : []),
          ]}
        />
      )}
    </div>
  );
}

/* --------------------------------------------------------------------------
   Scatter
   -------------------------------------------------------------------------- */

export interface ScatterSeries {
  points: [number, number][];
  color: string;
  alpha?: number;
  radius?: number;
  /** Shown in the legend and the hover readout. */
  label?: string;
}

const PAD = { l: 52, r: 14, t: 14, b: 34 };

/** Cross-plot with axis ticks, a crosshair, per-point hit testing and a
 *  toggleable legend.
 *
 *  The prototype drew a fog of dots with two axis captions and no scale: you
 *  could see there was a cloud but you could not read a single company out of
 *  it, and there was no way to tell which of the two overlaid series you were
 *  looking at in the overlap. */
export function ScatterChart({
  chartId, series, xLabel, yLabel, xRange, yRange, height = 240, ariaLabel,
  xUnit = "", yUnit = "",
}: {
  chartId: string; series: ScatterSeries[]; xLabel: string; yLabel: string;
  xRange: [number, number]; yRange: [number, number]; height?: number; ariaLabel: string;
  xUnit?: string; yUnit?: string;
}) {
  const { chartSeen } = useStore();
  const [off, setOff] = useState<Set<number>>(new Set());
  const [hover, setHover] = useState<{ s: number; i: number; px: number; py: number } | null>(null);
  const [w, setW] = useState(0);

  const [x0, x1] = xRange;
  const [y0, y1] = yRange;
  const introKey = useMemo(
    () => `${xLabel}|${yLabel}|${series.map((s) => s.points.length).join(",")}`,
    [xLabel, yLabel, series],
  );
  const intro = useIntro(480, introKey);

  const toPx = useCallback(
    (px: number, py: number, width: number, h: number) => {
      const plotW = width - PAD.l - PAD.r;
      const plotH = h - PAD.t - PAD.b;
      return [
        PAD.l + ((px - x0) / (x1 - x0)) * plotW,
        PAD.t + plotH - ((py - y0) / (y1 - y0)) * plotH,
      ] as [number, number];
    },
    [x0, x1, y0, y1],
  );

  const { ref } = useCanvas(
    height,
    (ctx, width, h) => {
      setW(width);
      const plotW = width - PAD.l - PAD.r;
      const plotH = h - PAD.t - PAD.b;

      const xTicks = niceTicks(x0, x1, 5);
      const yTicks = niceTicks(y0, y1, 4);

      // Grid + tick labels. Real numbers on both axes: the old chart showed
      // only a rounded min and max on y and nothing at all on x.
      ctx.font = `500 9.5px ${MONO}`;
      ctx.lineWidth = 1;
      ctx.strokeStyle = token("--chart-grid");

      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (const t of yTicks) {
        const [, py] = toPx(x0, t, width, h);
        ctx.beginPath();
        ctx.moveTo(PAD.l, Math.round(py) + 0.5);
        ctx.lineTo(PAD.l + plotW, Math.round(py) + 0.5);
        ctx.stroke();
        ctx.fillStyle = token("--chart-muted");
        ctx.fillText(fmt(t), PAD.l - 8, py);
      }

      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      for (const t of xTicks) {
        const [px] = toPx(t, y0, width, h);
        ctx.beginPath();
        ctx.moveTo(Math.round(px) + 0.5, PAD.t);
        ctx.lineTo(Math.round(px) + 0.5, PAD.t + plotH);
        ctx.stroke();
        ctx.fillStyle = token("--chart-muted");
        ctx.fillText(fmt(t), px, PAD.t + plotH + 8);
      }

      // Crosshair sits under the marks so it never obscures one.
      if (hover) {
        ctx.strokeStyle = token("--chart-accent");
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(PAD.l, Math.round(hover.py) + 0.5);
        ctx.lineTo(PAD.l + plotW, Math.round(hover.py) + 0.5);
        ctx.moveTo(Math.round(hover.px) + 0.5, PAD.t);
        ctx.lineTo(Math.round(hover.px) + 0.5, PAD.t + plotH);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      ctx.save();
      ctx.beginPath();
      ctx.rect(PAD.l, PAD.t, plotW, plotH);
      ctx.clip();

      series.forEach((s, si) => {
        if (off.has(si)) return;
        const r = (s.radius ?? 2.8) * (0.4 + 0.6 * intro.current);
        const dim = hover !== null && hover.s !== si;
        ctx.globalAlpha = (s.alpha ?? 0.45) * intro.current * (dim ? 0.45 : 1);
        ctx.fillStyle = s.color;
        for (const [dx, dy] of s.points) {
          const [cx, cy] = toPx(dx, dy, width, h);
          ctx.beginPath();
          ctx.arc(cx, cy, r, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      // The hovered mark, drawn last and opaque with a halo.
      if (hover) {
        const s = series[hover.s];
        ctx.globalAlpha = 1;
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(hover.px, hover.py, (s.radius ?? 2.8) + 1.4, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = s.color;
        ctx.globalAlpha = 0.35;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(hover.px, hover.py, (s.radius ?? 2.8) + 6, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
      ctx.globalAlpha = 1;

      // Axis captions.
      ctx.fillStyle = token("--chart-axis");
      ctx.font = `500 10px ${MONO}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(xLabel, PAD.l + plotW / 2, h - 6);
      ctx.save();
      ctx.translate(13, PAD.t + plotH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(yLabel, 0, 0);
      ctx.restore();
    },
    [series, off, hover, x0, x1, y0, y1, xLabel, yLabel, height, intro.current],
  );

  /** Nearest mark within 20px, searched in screen space so the hit radius is
   *  the same regardless of how stretched the axes are. */
  const onMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const c = e.currentTarget;
    const r = c.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    const width = c.offsetWidth;

    let best: { s: number; i: number; px: number; py: number } | null = null;
    let bestD = 20 * 20;
    series.forEach((s, si) => {
      if (off.has(si)) return;
      s.points.forEach(([dx, dy], i) => {
        const [px, py] = toPx(dx, dy, width, height);
        const d = (px - mx) * (px - mx) + (py - my) * (py - my);
        if (d < bestD) { bestD = d; best = { s: si, i, px, py }; }
      });
    });
    setHover(best);
  };

  const hp = hover ? series[hover.s].points[hover.i] : null;

  return (
    <div className="chart-wrap">
      <canvas
        ref={ref}
        role="img"
        aria-label={ariaLabel}
        tabIndex={0}
        onMouseEnter={() => chartSeen(chartId)}
        onFocus={() => chartSeen(chartId)}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      />
      {hover && hp && (
        <Tooltip
          x={hover.px}
          y={hover.py}
          width={w}
          title={series[hover.s].label ?? "Point"}
          color={series[hover.s].color}
          rows={[
            { k: xLabel, v: `${fmt(hp[0])}${xUnit}` },
            { k: yLabel, v: `${fmt(hp[1])}${yUnit}` },
          ]}
        />
      )}

      {series.some((s) => s.label) && (
        <div className="chart-legend">
          {series.map((s, i) => (
            <button
              key={s.label ?? i}
              type="button"
              className={`legend-item${off.has(i) ? " off" : ""}`}
              aria-pressed={!off.has(i)}
              onClick={() =>
                setOff((prev) => {
                  const next = new Set(prev);
                  if (next.has(i)) next.delete(i); else next.add(i);
                  return next;
                })
              }
            >
              <span className="swatch" style={{ background: s.color }} />
              {s.label}
              <span className="lcount">{s.points.length.toLocaleString("en-IN")}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
