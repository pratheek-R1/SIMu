import Link from "next/link";
import WaveCanvas from "@/components/WaveCanvas";
import { IconArrowRight } from "@/components/Icon";

/** Public landing page.
 *
 * This is a static server component with no auth dependency -- it is the reason
 * the stack is Next.js App Router rather than a plain SPA: a marketing surface
 * that renders on the server sits alongside the app itself.
 */
export default function Landing() {
  return (
    <div id="landing">
      <WaveCanvas />
      <div className="landing-inner">
        <div className="landing-hero">
          <div className="pre">Meridian Partners · Fund IV</div>
          {/* Hardcoded because this is a static server component with no config
              fetch. It must track FUND_POOL_USD x INR_RATE -- 50M x 83. */}
          <h1>
            You have five days to deploy <em>₹415 Cr</em>
          </h1>
          <p className="desc">
            Step into the analyst seat. Research the firm&apos;s portfolio history, build an
            investment thesis, defend it to the partners, and decide where the capital goes.
          </p>
          <Link href="/login" className="landing-cta">
            Begin Session
            <IconArrowRight size={17} />
          </Link>
        </div>
        <div className="landing-feat">
          <div>
            <div className="fk">Portfolio</div>
            <div className="fv">500</div>
            <div className="fd">companies to analyze</div>
          </div>
          <div>
            <div className="fk">Cheques</div>
            <div className="fv">5</div>
            <div className="fd">of ₹83 Cr each</div>
          </div>
          <div>
            <div className="fk">Timeline</div>
            <div className="fv">4 Q</div>
            <div className="fd">to prove your thesis</div>
          </div>
        </div>
      </div>
      <div className="landing-foot">
        MERIDIAN PARTNERS · ANALYST TERMINAL v4.1 · CONFIDENTIAL
      </div>
    </div>
  );
}
