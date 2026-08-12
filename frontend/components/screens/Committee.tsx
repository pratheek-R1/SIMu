"use client";

/** The investment committee, as a hub-and-spoke table.
 *
 * The five partners used to sit on a bare circle with no centre and no
 * connections, which read as five unrelated avatars rather than as a committee
 * you are sitting in front of. They are now spokes off a central chair, and the
 * partner holding the floor is lit while the rest recede.
 *
 * On the selector: the server requires the partners be answered in order
 * (`POST /committee/answer` rejects any index that is not the next one), and
 * that ordering is deliberate -- Priya's provenance question lands last, after
 * the other four have already committed you to a position. So the seats are not
 * a free choice of who to answer next. What they do allow is going back to read
 * a partner you have already answered, which is the useful half of that
 * interaction and costs nothing.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { IconAlert, IconCheck } from "@/components/Icon";
import { useStore } from "@/lib/store";

interface Partner { index: number; name: string; title: string; question: string }
interface Answered {
  partner_index: number; partner: string; question: string;
  answer: string; signals: string[];
}

/* Seat angles in degrees, keyed by first name, so the arrangement is stable
   even though committee.py orders the partners Ana, Vikram, Rashi, David, Priya.
   Ana top, Priya left, Vikram right, David bottom-left, Rashi bottom-right. */
const SEATS: Record<string, number> = {
  Ana: -90,
  Vikram: -18,
  Rashi: 54,
  David: 126,
  Priya: 198,
};

/* The viewBox is mapped 1:1 onto the container's max width (400px) so that one
   SVG user unit is one CSS pixel. That matters because the seat discs are sized
   in CSS pixels while the spokes are drawn in SVG units -- without a shared
   scale there is no way to stop a line at the edge of a disc, which is why the
   spokes used to run to the node centres and cut straight through them. */
const VIEW_W = 400;
const VIEW_H = 300;
const CX = VIEW_W / 2;
const CY = 132;
const R = 108;          // hub -> seat centre
const DISC_R = 23;      // half of .cm-disc's 46px
const SPOKE_GAP = 7;    // breathing room between line end and disc edge
const LINE_END = R - DISC_R - SPOKE_GAP;

function seatAngle(p: Partner, i: number, n: number): number {
  const first = p.name.split(" ")[0];
  // Fall back to an even spread if the cast ever changes server-side.
  return SEATS[first] ?? (i / n) * 360 - 90;
}

function initials(name: string): string {
  return name.split(" ").map((w) => w[0]).join("").slice(0, 2);
}

export default function Committee() {
  const { go, sessionId, refreshState } = useStore();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [answers, setAnswers] = useState<Answered[]>([]);
  const [current, setCurrent] = useState(0);
  const [viewing, setViewing] = useState(0);
  const [answer, setAnswer] = useState("");
  const [warn, setWarn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    api
      .get<{ partners: Partner[]; answers: Answered[]; complete: boolean }>(
        `/sessions/${sessionId}/committee`,
      )
      .then((r) => {
        setPartners(r.partners);
        setAnswers(r.answers ?? []);
        setCurrent(r.answers.length);
        setViewing(r.answers.length);
      })
      .catch(() => {});
  }, [sessionId]);

  const submit = useCallback(async () => {
    if (!answer.trim()) { setWarn(true); return; }
    if (!sessionId) return;
    setWarn(false);
    setBusy(true);
    try {
      const r = await api.post<{ answered: number; total: number; complete: boolean }>(
        `/sessions/${sessionId}/committee/answer`,
        { partner_index: current, answer },
      );
      const submitted = answer;
      setAnswer("");
      if (r.complete) {
        await refreshState();
        await go("deliberation");
        return;
      }
      setAnswers((prev) => [
        ...prev,
        {
          partner_index: current,
          partner: partners[current]?.name ?? "",
          question: partners[current]?.question ?? "",
          answer: submitted,
          signals: [],
        },
      ]);
      setCurrent(r.answered);
      setViewing(r.answered);
    } finally {
      setBusy(false);
    }
  }, [answer, sessionId, current, partners, refreshState, go]);

  const nodes = useMemo(
    () =>
      partners.map((p, i) => {
        const rad = (seatAngle(p, i, partners.length) * Math.PI) / 180;
        const cos = Math.cos(rad);
        const sin = Math.sin(rad);
        return {
          partner: p,
          // Seat centre, and where the spoke stops short of it.
          x: CX + R * cos,
          y: CY + R * sin,
          lx: CX + LINE_END * cos,
          ly: CY + LINE_END * sin,
          state: i === current ? "active" : i < current ? "done" : "pending",
        };
      }),
    [partners, current],
  );

  const onSeat = (i: number) => {
    if (i <= current) setViewing(i);
  };

  const shown = partners[viewing];
  const reviewing = viewing < current;
  const reviewed = answers.find((a) => a.partner_index === viewing);

  return (
    <>
      <div className="cm-screen">
        <div className="eyebrow">Step three</div>
        <h2 className="stitle" style={{ fontSize: 22 }}>Investment committee</h2>
        <p style={{ color: "var(--ink-3)", marginTop: 4, marginBottom: 18 }}>
          {partners.length} partners, in their order. Answer on the record.
        </p>

        {/* ---------------- diagram ---------------- */}
        <div className="cm-diagram">
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="cm-svg"
            role="img"
            aria-label="The committee table. Each partner is a seat around a central chair."
          >
            {/* Spokes are drawn before the nodes so the lines sit underneath.
                The lit spoke is painted twice -- a wide soft pass under a thin
                bright one -- which reads as a glow without an SVG filter. */}
            {nodes.map((n) => (
              <g key={`spoke-${n.partner.index}`} className={`cm-spoke ${n.state}`}>
                {n.state === "active" && (
                  <line className="cm-spoke-glow" x1={CX} y1={CY} x2={n.lx} y2={n.ly} />
                )}
                <line className="cm-spoke-line" x1={CX} y1={CY} x2={n.lx} y2={n.ly} />
              </g>
            ))}
            <circle className="cm-hub-ring" cx={CX} cy={CY} r={22} />
            <circle className="cm-hub" cx={CX} cy={CY} r={6} />
            {/* Captioned at the foot of the diagram rather than under the hub:
                at 44px below centre it sat on top of the two downward spokes. */}
            <text className="cm-hub-label" x={CX} y={VIEW_H - 6} textAnchor="middle">
              THE TABLE
            </text>
          </svg>

          {/* Nodes are HTML on top of the SVG: real buttons, so they are
              focusable and announce their own state. */}
          {nodes.map((n, i) => (
            <button
              key={n.partner.index}
              className={`cm-seat ${n.state}${viewing === i ? " viewing" : ""}`}
              style={{
                left: `${(n.x / VIEW_W) * 100}%`,
                top: `${(n.y / VIEW_H) * 100}%`,
              }}
              onClick={() => onSeat(i)}
              disabled={i > current}
              aria-current={i === current ? "step" : undefined}
              title={
                i > current
                  ? `${n.partner.name} has not spoken yet`
                  : i < current
                    ? `Review your answer to ${n.partner.name}`
                    : `${n.partner.name} has the floor`
              }
            >
              <span className="cm-disc">
                {n.state === "done" ? <IconCheck size={15} /> : initials(n.partner.name)}
              </span>
              <span className="cm-seat-name">{n.partner.name.split(" ")[0]}</span>
            </button>
          ))}
        </div>

        {/* ---------------- who has the floor ---------------- */}
        <div className="cm-panel">
          <div className="cm-floor">
            <span className="cm-floor-k">
              {reviewing ? "Reviewing" : "Now speaking"}
            </span>
            <span className="cm-floor-name">{shown?.name ?? "—"}</span>
            <span className="cm-floor-title">{shown?.title ?? ""}</span>
            <span className="cm-floor-step mono">
              Partner {viewing + 1} of {partners.length}
              {reviewing && " · already answered"}
            </span>
          </div>

          <div className="cm-selector" role="group" aria-label="Committee seats">
            {partners.map((p, i) => (
              <button
                key={p.index}
                className={`chip${viewing === i ? " on" : ""}`}
                onClick={() => onSeat(i)}
                disabled={i > current}
              >
                {p.name.split(" ")[0]}
              </button>
            ))}
          </div>

          {shown && (
            <>
              <p className="cm-question editorial">{shown.question}</p>

              {reviewing ? (
                <div className="cm-locked">
                  <div className="eyebrow" style={{ marginBottom: 6 }}>Your answer</div>
                  <p style={{ fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-2)" }}>
                    {reviewed?.answer}
                  </p>
                  <button
                    style={{ marginTop: 12 }}
                    onClick={() => setViewing(current)}
                  >
                    Back to {partners[current]?.name.split(" ")[0]}
                  </button>
                </div>
              ) : (
                <>
                  <textarea
                    rows={5} value={answer} placeholder="Type your answer…"
                    onChange={(e) => setAnswer(e.target.value)}
                  />
                  <div className="committee-warning">
                    {warn && (
                      <>
                        <IconAlert size={13} />
                        Please provide an answer before proceeding.
                      </>
                    )}
                  </div>
                  <button className="pri" style={{ marginTop: 8 }} onClick={submit} disabled={busy}>
                    {busy
                      ? "Submitting…"
                      : current === partners.length - 1
                        ? "Submit and withdraw"
                        : "Submit response"}
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
