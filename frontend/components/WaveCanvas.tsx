"use client";

import { useEffect, useRef } from "react";

/** The layered sine field behind the landing and auth screens.
 *  Ported from the prototype's initLandingBg / initBgCanvas. */
export default function WaveCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, t = 0, raf = 0;

    const resize = () => {
      w = c.width = c.offsetWidth || window.innerWidth;
      h = c.height = c.offsetHeight || window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < 5; i++) {
        ctx.beginPath();
        ctx.moveTo(0, h);
        for (let x = 0; x <= w; x += 5) {
          const y =
            h / 2 +
            Math.sin(x * 0.003 + t * 0.001 + i * 1.2) * 80 +
            Math.sin(x * 0.008 + t * 0.002) * 20 +
            i * 30;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fillStyle = `rgba(248, 246, 240, ${0.02 + i * 0.005})`;
        ctx.fill();
      }
      t++;
      if (!reduced) raf = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} aria-hidden="true" />;
}
