"use client";

/** The onboarding brief.
 *
 * This used to restate the landing page: same dark hero, same big sentence
 * about five days and the fund size, same lone teal button. Arriving here felt
 * like the marketing page had reloaded rather than like you were now inside the
 * firm. So it is a document instead of a hero.
 *
 * The figures below are the MANDATE -- the constraints the run is played inside.
 * They were portfolio descriptives (median ARR, median retention, median
 * LTV/CAC), which is exactly what the Dashboard's Portfolio overview already
 * shows one screen later; repeating them here taught nothing and made the two
 * screens read as the same screen. What a student needs before they start is
 * what they are allowed to do, not summary statistics they are about to be given
 * properly.
 */

import { useStore } from "@/lib/store";
import { IconArrowRight } from "@/components/Icon";
import { money } from "@/lib/format";

const STAGES = [
  { n: "01", label: "Research", body: "Read the portfolio history however you like. Nothing is scored on speed." },
  { n: "02", label: "Thesis", body: "Name your variables and state how confident you are in each. This locks." },
  { n: "03", label: "Committee", body: "Five partners question the thesis. They read what you write." },
  { n: "04", label: "Evidence", body: "New records arrive after the committee. They may not agree with you." },
  { n: "05", label: "Model", body: "Weight the variables and rank live deals against your own model." },
  { n: "06", label: "Deploy", body: "Write the cheques, sized however you choose." },
];

export default function Brief() {
  const { go, config } = useStore();
  const cheques = config?.cheques ?? 5;
  const slots = config?.max_thesis_variables ?? 4;
  const catalogue = config?.variables?.length ?? 16;

  return (
    <div className="brief">
      <h1 className="stitle brief-title">
        You joined on Monday. The fund closes Friday.
      </h1>

      <p className="brief-lede">
        Meridian is raising a seed fund and the partners want a thesis before it closes.
        Your job is to work out what actually distinguishes a company worth backing — not
        what the winners have in common, which is a different question than it looks.
      </p>

      <div className="brief-figures">
        {config?.fund_pool_usd != null && (
          <div>
            <span className="bfk">Capital to deploy</span>
            <span className="bfv mono">{money(config.fund_pool_usd)}</span>
            <span className="bfd">committed in full, or not at all</span>
          </div>
        )}
        <div>
          <span className="bfk">Cheques</span>
          <span className="bfv mono">{cheques}</span>
          <span className="bfd">no more, no fewer</span>
        </div>
        {config?.cheque_min_usd != null && config?.cheque_max_usd != null && (
          <div>
            <span className="bfk">Cheque range</span>
            {/* Spaces around the dash so this wraps at a word boundary instead
                of being broken mid-figure by overflow-wrap. */}
            <span className="bfv mono">
              {money(config.cheque_min_usd)} – {money(config.cheque_max_usd)}
            </span>
            <span className="bfd">size each one yourself</span>
          </div>
        )}
        <div>
          <span className="bfk">Thesis slots</span>
          <span className="bfv mono">{slots} of {catalogue}</span>
          <span className="bfd">variables on file</span>
        </div>
      </div>

      <div className="brief-quote">
        <p>
          Don&apos;t bring me a list of things that sound clever. Bring me variables you can
          defend with evidence, and tell me how confident you are in each one.
        </p>
        <span className="bq-attr mono">Ana Behl · Managing Partner</span>
      </div>

      <div className="brief-stages">
        <div className="eyebrow" style={{ marginBottom: 12 }}>What the week asks of you</div>
        <ol>
          {STAGES.map((st) => (
            <li key={st.n}>
              <span className="bs-n mono">{st.n}</span>
              <span className="bs-body">
                <strong>{st.label}</strong>
                <span className="note">{st.body}</span>
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div className="brief-foot">
        <button className="pri" onClick={() => go("dashboard")}>
          Open the terminal <IconArrowRight size={14} />
        </button>
        <p className="note">
          One decision in here cannot be undone: locking the thesis. Everything before it
          is yours to revisit.
        </p>
      </div>
    </div>
  );
}
