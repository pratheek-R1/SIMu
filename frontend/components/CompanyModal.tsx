"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChartCanvas, COLORS, MONO, seqRamp } from "@/components/Chart";
import { IconCheck, IconClose, IconDash, StarRating } from "@/components/Icon";
import { api, type CompanyProfile, type CompanyRow, type DeepProfile } from "@/lib/api";
import { money, months, mult, num, pct } from "@/lib/format";
import { useStore } from "@/lib/store";

/** The company profile.
 *
 *  Layout is ported from the prototype's `renderProfileModal`. The difference is
 *  where the numbers come from: every figure here is served by the API from one
 *  canonical financial model, so the LTV/CAC on the row, the CAC payback in the
 *  unit-economics table and the burn on the balance sheet all describe the same
 *  company. In the prototype each was drawn separately, and a student who
 *  compared two of them found the dataset contradicting itself.
 *
 *  Board minutes and the founder interview stay behind their own requests --
 *  reading both on one company is what Triangulation measures, and the server
 *  can only see that if the client asks for them separately.
 */
export default function CompanyModal({
  companyId, onClose,
}: {
  companyId: number; onClose: () => void;
}) {
  const { sessionId, config, toast } = useStore();
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [compareId, setCompareId] = useState<number | null>(null);
  const [compare, setCompare] = useState<CompanyProfile | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CompanyRow[]>([]);

  const [minutes, setMinutes] = useState<string | null>(null);
  const [interview, setInterview] = useState<string | null>(null);
  const [flagVar, setFlagVar] = useState("");
  const [flagResult, setFlagResult] = useState<{ correct: boolean; resolution: string | null } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    setProfile(null); setCompareId(null); setCompare(null);
    setMinutes(null); setInterview(null); setFlagResult(null); setFlagVar("");
    api.get<CompanyProfile>(`/sessions/${sessionId}/companies/${companyId}`)
      .then(setProfile)
      .catch(() => onClose());
  }, [sessionId, companyId, onClose]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && (compareId ? setCompareId(null) : onClose());
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose, compareId]);

  const search = useCallback(async (q: string) => {
    setQuery(q);
    if (!q.trim() || !sessionId) { setResults([]); return; }
    const r = await api.get<{ rows: CompanyRow[] }>(
      `/sessions/${sessionId}/companies?q=${encodeURIComponent(q)}&limit=8`,
    );
    setResults(r.rows.filter((x) => x.id !== companyId));
  }, [sessionId, companyId]);

  async function selectCompare(id: number) {
    if (!sessionId) return;
    const r = await api.post<{ companies: CompanyProfile[] }>(`/sessions/${sessionId}/compare`, {
      company_ids: [companyId, id],
    });
    setCompare(r.companies.find((c) => c.id === id) ?? null);
    setCompareId(id);
    setResults([]); setQuery("");
  }

  const openMinutes = async () => {
    if (minutes !== null || !sessionId) return;
    const r = await api.get<{ board_minutes: string }>(`/sessions/${sessionId}/companies/${companyId}/board-minutes`);
    setMinutes(r.board_minutes);
  };
  const openInterview = async () => {
    if (interview !== null || !sessionId) return;
    const r = await api.get<{ founder_interview: string }>(`/sessions/${sessionId}/companies/${companyId}/founder-interview`);
    setInterview(r.founder_interview);
  };

  const flag = async () => {
    if (!sessionId || !flagVar) return;
    const r = await api.post<{ correct: boolean; message: string; resolution: string | null }>(
      `/sessions/${sessionId}/companies/${companyId}/flag-contradiction`,
      { company_id: companyId, feature: flagVar },
    );
    setFlagResult(r);
    toast(r.correct ? "Contradiction logged" : "Flag recorded", r.message);
  };

  if (!profile) {
    return (
      <div className="modal-backdrop" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-body"><p className="note">Loading profile…</p></div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 1040 }}>
        <div className="modal-body" style={{ padding: "28px 30px 30px", position: "relative" }}>
          <button onClick={onClose} style={{ position: "absolute", top: 16, right: 16, padding: "6px 10px", fontSize: 12 }}>
            <IconClose size={12} /> Close
          </button>

          {compareId && compare ? (
            <CompareView a={profile} b={compare} onClear={() => { setCompareId(null); setCompare(null); }} />
          ) : (
            <>
              <SingleView
                profile={profile}
                minutes={minutes} interview={interview}
                onOpenMinutes={openMinutes} onOpenInterview={openInterview}
                flagVar={flagVar} setFlagVar={setFlagVar} onFlag={flag} flagResult={flagResult}
              />
              <div className="cp-comparebar">
                <div className="eyebrow" style={{ marginBottom: 8 }}>Compare against another company</div>
                <div className="cp-searchbox">
                  <input
                    type="text" value={query} autoComplete="off"
                    placeholder="Search companies to compare…"
                    onChange={(e) => search(e.target.value)}
                  />
                  {results.length > 0 && (
                    <div className="cp-searchresults">
                      {results.map((r) => (
                        <div key={r.id} className="cp-searchresult" onClick={() => selectCompare(r.id)}>
                          <span className="n">{r.name}</span>
                          <span className="m">{r.sector} · {money(r.arr_usd)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {query.trim() && results.length === 0 && (
                    <div className="cp-searchresults">
                      <div className="cp-searchresult note">No matches</div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function SingleView({
  profile, minutes, interview, onOpenMinutes, onOpenInterview,
  flagVar, setFlagVar, onFlag, flagResult,
}: {
  profile: CompanyProfile;
  minutes: string | null; interview: string | null;
  onOpenMinutes: () => void; onOpenInterview: () => void;
  flagVar: string; setFlagVar: (v: string) => void; onFlag: () => void;
  flagResult: { correct: boolean; resolution: string | null } | null;
}) {
  const { config } = useStore();
  const d = profile.deep;
  const bs = profile.balance_sheet;

  return (
    <>
      <div className="cp-title">{profile.name}</div>
      <div className="cp-sub">
        {profile.sector} · {profile.city} · Founded {d.founded}
      </div>

      <div className="cp-metrics">
        <Stat k="ARR" v={money(profile.arr_usd)} />
        <Stat k="Gross margin" v={pct(profile.gross_margin)} />
        <Stat k="M6 retention" v={pct(profile.month6_retention)} />
        <Stat k="Net revenue ret." v={pct(profile.net_revenue_retention)} />
        <Stat k="Headcount" v={String(profile.headcount)} />
        <Stat k="Total raised" v={money(d.funding.total_raised_usd)} />
      </div>

      <div className="eyebrow">Attributes</div>
      <div className="cp-tagswrap">
        {(config?.variables ?? []).map((v) => {
          const on = profile.flag_map[v.key];
          return (
            <span key={v.key} className={`cp-tagpill ${on ? "yes" : "no"}`}>
              {on ? <IconCheck size={11} /> : <IconDash size={11} />}
              {v.label}
            </span>
          );
        })}
      </div>

      <div className="cp-cols" style={{ marginTop: 20 }}>
        {/* ---------------- left column ---------------- */}
        <div>
          <Card title="Unit economics">
            <table className="cp-table">
              <tbody>
                <R k="Customers" v={d.customers.toLocaleString("en-IN")} />
                <R k="ARPU (monthly)" v={money(d.arpu_monthly_usd)} />
                <R k="CAC" v={money(d.cac_usd)} />
                <R k="LTV" v={money(d.ltv_usd)} />
                <R k="LTV / CAC" v={mult(d.ltv_cac_ratio, 2)} />
                <R k="CAC payback" v={months(d.cac_payback_months)} />
                <R k="Avg customer lifetime" v={months(d.avg_customer_lifetime_months)} />
                <R k="Monthly logo churn" v={pct(d.monthly_churn, 2)} />
                <R k="Annual net burn" v={money(d.annual_net_burn_usd)} />
              </tbody>
            </table>
            <p className="note" style={{ marginTop: 6 }}>
              LTV/CAC is customer lifetime divided by CAC payback. Both figures are on
              this table; the ratio is not an independent number.
            </p>
          </Card>

          <Card title="Financial history">
            <table className="cp-table">
              <thead>
                <tr><th>Year</th><th className="r">Revenue</th><th className="r">Head</th><th className="r">Net burn</th></tr>
              </thead>
              <tbody>
                {d.financial_history.map((y) => (
                  <tr key={y.year}>
                    <td className="mono">{y.year}</td>
                    <td className="r mono">{money(y.revenue_usd)}</td>
                    <td className="r mono">{y.headcount}</td>
                    <td className="r mono">{money(y.net_burn_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title="Funding history">
            <table className="cp-table">
              <tbody>
                <R k="Seed" v={money(d.funding.seed_usd)} />
                <tr><td colSpan={2} className="note" style={{ paddingTop: 0 }}>
                  led by {d.funding.seed_investor} · {d.funding.seed_year}
                </td></tr>
                <R k="Series A" v={money(d.funding.series_a_usd)} />
                <tr><td colSpan={2} className="note" style={{ paddingTop: 0 }}>
                  led by {d.funding.series_a_investor} · {d.funding.series_a_year}
                </td></tr>
                {d.funding.has_series_b && (
                  <>
                    <R k="Series B" v={money(d.funding.series_b_usd)} />
                    <tr><td colSpan={2} className="note" style={{ paddingTop: 0 }}>
                      led by {d.funding.series_b_investor} · {d.funding.series_b_year}
                    </td></tr>
                  </>
                )}
                <R k="Total raised" v={money(d.funding.total_raised_usd)} bold />
              </tbody>
            </table>
          </Card>

          <Card title="Balance sheet">
            <div className="cp-section-label">Assets</div>
            <table className="cp-table"><tbody>
              <R k="Cash and equivalents" v={money(bs.cash)} />
              <R k="Accounts receivable" v={money(bs.accounts_receivable)} />
              <R k="Prepaid expenses" v={money(bs.prepaid)} />
              <R k="Capitalised software and equipment" v={money(bs.fixed_assets)} />
              <R k="Total assets" v={money(bs.total_assets)} bold />
            </tbody></table>
            <div className="cp-section-label">Liabilities</div>
            <table className="cp-table"><tbody>
              <R k="Accounts payable" v={money(bs.accounts_payable)} />
              <R k="Accrued payroll" v={money(bs.accrued_payroll)} />
              <R k="Deferred revenue" v={money(bs.deferred_revenue)} />
              <R k="Venture debt" v={money(bs.venture_debt)} />
              <R k="Total liabilities" v={money(bs.total_liabilities)} bold />
            </tbody></table>
            <div className="cp-section-label">Equity</div>
            <table className="cp-table"><tbody>
              <R k="Paid-in capital" v={money(bs.paid_in_capital)} />
              <R k="Accumulated deficit" v={`-${money(bs.accumulated_deficit)}`} neg />
              <R k="Total equity" v={money(bs.total_equity)} bold />
            </tbody></table>
            <p className="note" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
              <span>
                {money(bs.total_assets)} = {money(bs.total_liabilities)} + {money(bs.total_equity)}
              </span>
              {profile.balance_sheet_ties ? (
                <IconCheck size={12} style={{ color: "var(--green)" }} title="Balance sheet ties" />
              ) : (
                <span style={{ color: "var(--neg)" }}>— does not tie</span>
              )}
            </p>
          </Card>

          <Card title="Economic position">
            <table className="cp-table"><tbody>
              <R k="Customer equity" v={money(d.economic_position.customer_equity_usd)} />
              <R k="Customer equity + paid-in capital" v={money(d.economic_position.customer_equity_plus_paid_in_usd)} />
              <R k="Ratio" v={mult(d.economic_position.ratio, 2)} />
            </tbody></table>
            <p className="note" style={{ marginTop: 6 }}>
              Lifetime value of the current customer base against capital raised.
            </p>
          </Card>

          <Card title="Computed from the statements above">
            <table className="cp-table"><tbody>
              <R k="Accumulated deficit ÷ ARR" v={mult(d.computed_ratios.deficit_to_arr, 2)} />
              <R k="Deferred revenue ÷ ARR" v={`${d.computed_ratios.deferred_revenue_to_arr_pct}%`} />
              <R k="Runway on current burn" v={months(d.computed_ratios.runway_months)} />
              <R k="Burn multiple" v={d.computed_ratios.burn_multiple != null ? mult(d.computed_ratios.burn_multiple, 2) : "n/m"} />
              <R k="Top-10 customer concentration" v={`${d.computed_ratios.top10_concentration_pct}%`} />
            </tbody></table>
            <p className="note" style={{ marginTop: 6 }}>
              None of these appear on the statements above. All are computable from them.
            </p>
          </Card>

          <Card title="Go-to-market">
            <table className="cp-table"><tbody>
              <tr>
                <td className="k">Pricing</td>
                <td className="r" style={{ color: "var(--orange)", fontWeight: 600 }}>{d.gtm.pricing}</td>
              </tr>
              <tr>
                <td className="k">Segment</td>
                <td className="r" style={{ fontWeight: 600 }}>{d.gtm.segment}</td>
              </tr>
            </tbody></table>
            <p className="note" style={{ marginTop: 6 }}>{d.gtm.motion}</p>
          </Card>

          <Card title="Revenue retention by cohort">
            <CohortChart cohorts={d.cohorts} companyId={profile.id} />
          </Card>

          <Card title="Departmental spend">
            <div className="spendbar">
              <div style={{ width: `${d.dept_spend.rnd}%`, background: "var(--seq-1)" }} />
              <div style={{ width: `${d.dept_spend.sales_marketing}%`, background: "var(--seq-2)" }} />
              <div style={{ width: `${d.dept_spend.customer_success}%`, background: "var(--seq-3)" }} />
              <div style={{ width: `${d.dept_spend.general_admin}%`, background: "var(--seq-4)" }} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, fontSize: 12 }}>
              <Legend color="var(--seq-1)" label="R&amp;D" value={d.dept_spend.rnd} />
              <Legend color="var(--seq-2)" label="Sales &amp; marketing" value={d.dept_spend.sales_marketing} />
              <Legend color="var(--seq-3)" label="Customer success" value={d.dept_spend.customer_success} />
              <Legend color="var(--seq-4)" label="G&amp;A" value={d.dept_spend.general_admin} />
            </div>
            <p className="note" style={{ marginTop: 8 }}>
              Share of {money(d.dept_spend.annual_opex_usd)} annual operating expense.
            </p>
          </Card>

          <Card title="Capitalisation" last>
            <table className="cp-table"><tbody>
              <R k="Founders" v={`${d.cap_table.founders}%`} />
              <R k="Employee option pool" v={`${d.cap_table.option_pool}%`} />
              <R k={`Seed · ${d.funding.seed_investor}`} v={`${d.cap_table.seed}%`} />
              <R k={`Series A · ${d.funding.series_a_investor}`} v={`${d.cap_table.series_a}%`} />
              {d.funding.has_series_b && (
                <R k={`Series B · ${d.funding.series_b_investor}`} v={`${d.cap_table.series_b}%`} />
              )}
            </tbody></table>
          </Card>
        </div>

        {/* ---------------- right column ---------------- */}
        <div>
          <Card title="Founding team">
            <p style={{ marginTop: 4 }}><strong>{d.founders.ceo_name}</strong> · CEO</p>
            <p className="note">{d.founders.ceo_background}</p>
            {d.founders.cto_name && (
              <>
                <p style={{ marginTop: 10 }}><strong>{d.founders.cto_name}</strong> · CTO</p>
                <p className="note">{d.founders.cto_background}</p>
              </>
            )}
          </Card>

          <div className="card pad" style={{ marginBottom: 14, borderLeft: "3px solid var(--orange)" }}>
            <div className="eyebrow" style={{ marginBottom: 6 }}>Founder interview</div>
            {interview === null ? (
              <button onClick={onOpenInterview}>Read the interview transcript</button>
            ) : (
              <>
                <p style={{ lineHeight: 1.65 }}>&ldquo;{interview}&rdquo;</p>
                <p className="note" style={{ marginTop: 6 }}>
                  — {d.founders.ceo_name}, interviewed {d.report_year}
                </p>
              </>
            )}
          </div>

          <div className="card pad" style={{ marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 6 }}>Board minutes</div>
            {minutes === null ? (
              <button onClick={onOpenMinutes}>Open the minute book</button>
            ) : (
              <>
                {d.flavour_minutes.map((m) => (
                  <div key={m.label} style={{ marginTop: 10 }}>
                    <div className="note mono" style={{ marginBottom: 2 }}>{m.label}</div>
                    <p style={{ fontSize: 13 }}>{m.text}</p>
                  </div>
                ))}
                <div style={{ marginTop: 10 }}>
                  <div className="note mono" style={{ marginBottom: 2 }}>Q4 {d.report_year}</div>
                  <p style={{ fontSize: 13 }}>{minutes}</p>
                </div>
              </>
            )}
          </div>

          {minutes !== null && interview !== null && (
            <div className="flag-bar">
              <span style={{ fontSize: 12.5, width: "100%" }}>
                Do the minutes and the interview disagree about a variable?
              </span>
              <select value={flagVar} onChange={(e) => setFlagVar(e.target.value)}>
                <option value="">Select a variable…</option>
                {(config?.variables ?? []).map((v) => (
                  <option key={v.key} value={v.key}>{v.label}</option>
                ))}
              </select>
              <button onClick={onFlag} disabled={!flagVar}>Flag contradiction</button>
              {flagResult && (
                <span style={{ fontSize: 12, color: flagResult.correct ? "var(--green)" : "var(--neg)" }}>
                  {flagResult.correct ? "Confirmed" : "Not a contradiction"}
                </span>
              )}
              {flagResult?.resolution && (
                <p className="note" style={{ width: "100%", marginTop: 4, lineHeight: 1.6 }}>
                  {flagResult.resolution}
                </p>
              )}
            </div>
          )}

          <Card title="Press coverage" style={{ marginTop: 14 }}>
            {d.press.length ? (
              d.press.map((p, i) => (
                <div key={i} style={{ marginTop: i ? 10 : 4 }}>
                  <p style={{ fontSize: 13 }}>{p.headline}</p>
                  <div className="note mono" style={{ marginTop: 2 }}>{p.publication} · {p.year}</div>
                </div>
              ))
            ) : (
              <p className="note">No significant press coverage on file.</p>
            )}
          </Card>

          <Card title="Employee reviews">
            {d.reviews.map((r) => (
              <div key={r.department} style={{ marginTop: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <strong style={{ fontSize: 13 }}>{r.department}</strong>
                  <StarRating n={r.rating} />
                </div>
                <p className="note" style={{ marginTop: 2 }}>{r.quote}</p>
              </div>
            ))}
          </Card>

          <Card title="Market position">
            <div style={{ marginBottom: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                <strong>{profile.name} (this company)</strong>
                <span className="mono">{d.market.your_share_pct}%</span>
              </div>
              <div className="sharebar">
                <div style={{ width: `${d.market.your_share_pct}%`, background: "var(--orange)" }} />
              </div>
            </div>
            {d.market.competitors.map((c) => (
              <div key={c.name} style={{ marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: "rgb(var(--ink-rgb) / 0.5)" }}>{c.name}</span>
                  <span className="mono">{c.share_pct}%</span>
                </div>
                <div className="sharebar">
                  <div style={{ width: `${c.share_pct}%`, background: "rgb(var(--ink-rgb) / 0.25)" }} />
                </div>
              </div>
            ))}
            <p className="note" style={{ marginTop: 4 }}>
              Estimated share of {d.market.segment.toLowerCase()} {profile.sector} spend in the{" "}
              {profile.city} region. Remaining {d.market.other_pct}% is long-tail.
            </p>
          </Card>

          <Card title="Product releases">
            {d.releases.map((r, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between", padding: "6px 0",
                borderBottom: "1px solid rgb(var(--ink-rgb) / 0.05)", fontSize: 13,
              }}>
                <span>{r.title}</span>
                <span className="note mono">Q{r.quarter} {r.year}</span>
              </div>
            ))}
          </Card>

          <Card title="Customer interviews" last>
            {d.customer_interviews.map((iv, i) => (
              <div key={i} style={{ marginTop: i ? 10 : 4 }}>
                <p style={{ lineHeight: 1.6, fontSize: 13 }}>&ldquo;{iv.quote}&rdquo;</p>
                <p className="note" style={{ marginTop: 4 }}>{iv.role}</p>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
const COMPARE_ROWS: { label: string; get: (p: CompanyProfile) => string; raw: (p: CompanyProfile) => unknown }[] = [
  { label: "Sector", get: (p) => p.sector, raw: (p) => p.sector },
  { label: "HQ", get: (p) => p.city, raw: (p) => p.city },
  { label: "Founded", get: (p) => String(p.founded_year), raw: (p) => p.founded_year },
  { label: "ARR", get: (p) => money(p.arr_usd), raw: (p) => Math.round(p.arr_usd) },
  { label: "M6 retention", get: (p) => pct(p.month6_retention), raw: (p) => Math.round(p.month6_retention * 100) },
  { label: "Headcount", get: (p) => String(p.headcount), raw: (p) => p.headcount },
  { label: "LTV/CAC", get: (p) => mult(p.ltv_cac_ratio, 2), raw: (p) => p.ltv_cac_ratio.toFixed(2) },
  { label: "Customers", get: (p) => p.deep.customers.toLocaleString("en-IN"), raw: (p) => p.deep.customers },
  { label: "ARPU (monthly)", get: (p) => money(p.deep.arpu_monthly_usd), raw: (p) => Math.round(p.deep.arpu_monthly_usd) },
  { label: "CAC", get: (p) => money(p.deep.cac_usd), raw: (p) => Math.round(p.deep.cac_usd) },
  { label: "LTV", get: (p) => money(p.deep.ltv_usd), raw: (p) => Math.round(p.deep.ltv_usd) },
  { label: "CAC payback", get: (p) => months(p.cac_payback_months), raw: (p) => p.cac_payback_months.toFixed(1) },
  { label: "Monthly logo churn", get: (p) => pct(p.monthly_churn, 2), raw: (p) => p.monthly_churn.toFixed(4) },
  { label: "Gross margin", get: (p) => pct(p.gross_margin), raw: (p) => Math.round(p.gross_margin * 100) },
  { label: "Net revenue retention", get: (p) => pct(p.net_revenue_retention), raw: (p) => Math.round(p.net_revenue_retention * 100) },
  { label: "Annual net burn", get: (p) => money(p.annual_net_burn_usd), raw: (p) => Math.round(p.annual_net_burn_usd) },
  { label: "Burn multiple", get: (p) => p.deep.computed_ratios.burn_multiple != null ? mult(p.deep.computed_ratios.burn_multiple, 2) : "n/m", raw: (p) => p.deep.computed_ratios.burn_multiple },
  { label: "Runway", get: (p) => months(p.runway_months), raw: (p) => Math.round(p.runway_months) },
  { label: "Total raised", get: (p) => money(p.deep.funding.total_raised_usd), raw: (p) => Math.round(p.deep.funding.total_raised_usd) },
  { label: "Pricing", get: (p) => p.deep.gtm.pricing, raw: (p) => p.deep.gtm.pricing },
  { label: "Segment", get: (p) => p.deep.gtm.segment, raw: (p) => p.deep.gtm.segment },
];

function CompareView({ a, b, onClear }: { a: CompanyProfile; b: CompanyProfile; onClear: () => void }) {
  const { config } = useStore();
  return (
    <>
      <div className="cp-col-head">
        <div className="cp-title" style={{ fontSize: 19 }}>Comparing two companies</div>
        <button onClick={onClear} style={{ marginRight: 90 }}>
          <IconClose size={12} /> Back to profile
        </button>
      </div>

      <div className="cp-cols">
        <div>
          <div style={{ fontFamily: "var(--font-heading), sans-serif", fontWeight: 700, fontSize: 16 }}>{a.name}</div>
          <div className="cp-sub">{a.sector} · {a.city}</div>
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-heading), sans-serif", fontWeight: 700, fontSize: 16 }}>{b.name}</div>
          <div className="cp-sub">{b.sector} · {b.city}</div>
        </div>
      </div>

      <div className="card pad" style={{ marginTop: 16 }}>
        <table className="cp-table">
          <thead>
            <tr><th /><th className="r">{a.name}</th><th className="r">{b.name}</th></tr>
          </thead>
          <tbody>
            {COMPARE_ROWS.map((row) => {
              const diff = row.raw(a) !== row.raw(b);
              return (
                <tr key={row.label} className={diff ? "cp-rowdiff" : ""}>
                  <td className="k">{row.label}</td>
                  <td className="r mono">{row.get(a)}</td>
                  <td className="r mono">{row.get(b)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="eyebrow" style={{ marginTop: 16 }}>Attributes</div>
      <div className="card pad">
        <table className="cp-table">
          <thead>
            <tr><th /><th className="r">{a.name}</th><th className="r">{b.name}</th></tr>
          </thead>
          <tbody>
            {(config?.variables ?? []).map((v) => {
              const av = a.flag_map[v.key], bv = b.flag_map[v.key];
              return (
                <tr key={v.key} className={av !== bv ? "cp-rowdiff" : ""}>
                  <td className="k">{v.label}</td>
                  <td className="r">{av ? <IconCheck size={13} style={{ color: "var(--green)" }} title="yes" /> : <IconDash size={13} style={{ color: "var(--ink-5)" }} title="no" />}</td>
                  <td className="r">{bv ? <IconCheck size={13} style={{ color: "var(--green)" }} title="yes" /> : <IconDash size={13} style={{ color: "var(--ink-5)" }} title="no" />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="note" style={{ marginTop: 10 }}>
        Highlighted rows are where the two companies differ. Both of these companies
        are in the portfolio history, so both were backed — a difference here is not
        by itself a difference that mattered.
      </p>
    </>
  );
}

// ---------------------------------------------------------------------------
function CohortChart({ cohorts, companyId }: { cohorts: number[][]; companyId: number }) {
  const draw = useMemo(
    () => (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      const pad = 24, minV = 55, maxV = 190;
      const x0 = pad + 10, x1 = w - 8, y0 = 10, y1 = h - pad;
      const yFor = (v: number) => y1 - ((v - minV) / (maxV - minV)) * (y1 - y0);
      const xFor = (i: number) => x0 + (i / 12) * (x1 - x0);

      /* Every colour here goes through the token helpers. This function used to
         hand the canvas strings like "rgb(var(--ink-rgb) / 0.25)" -- CSS that a
         canvas context cannot parse. An unparseable colour is not an error: the
         context keeps whatever it had, which at the start of a draw is default
         black. So the guideline, both labels and three of the four cohort lines
         were being painted black on a near-black ground and were invisible. Only
         the fourth line, which already used a resolved token, ever showed. */
      ctx.strokeStyle = COLORS.GRID;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x0, yFor(100)); ctx.lineTo(x1, yFor(100)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COLORS.MUTED;
      ctx.font = `500 9px ${MONO}`;
      ctx.textAlign = "left";
      ctx.fillText("100%", x0, yFor(100) - 4);

      // Dimmest to brightest, so recency reads off the ramp in either theme.
      const colors = seqRamp();
      cohorts.forEach((curve, ci) => {
        ctx.strokeStyle = colors[ci % colors.length];
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        curve.forEach((v, i) => {
          const x = xFor(i), y = yFor(v);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
      });

      ctx.fillStyle = COLORS.MUTED;
      ctx.textAlign = "center";
      ctx.fillText(
        "Months since acquisition — four quarterly cohorts, brightest is most recent",
        w / 2, h - 4,
      );
    },
    [cohorts],
  );

  return (
    <ChartCanvas
      chartId="research.crossplot"
      height={190}
      draw={draw}
      ariaLabel={`Revenue retention by cohort for company ${companyId}`}
    />
  );
}

// ---------------------------------------------------------------------------
function Stat({ k, v }: { k: string; v: string }) {
  return <div className="stat"><div className="k">{k}</div><div className="v" style={{ fontSize: 18 }}>{v}</div></div>;
}

function R({ k, v, bold, neg }: { k: string; v: string; bold?: boolean; neg?: boolean }) {
  return (
    <tr>
      <td className="k" style={bold ? { color: "var(--navy)", fontWeight: 600 } : undefined}>{k}</td>
      <td className="r mono" style={{ fontWeight: bold ? 600 : 400, color: neg ? "var(--neg)" : undefined }}>{v}</td>
    </tr>
  );
}

function Card({
  title, children, last, style,
}: { title: string; children: React.ReactNode; last?: boolean; style?: React.CSSProperties }) {
  return (
    <div className="card pad" style={{ marginBottom: last ? 0 : 14, ...style }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div>
      <span className="swatch" style={{ background: color }} />
      <span dangerouslySetInnerHTML={{ __html: label }} />
      <span className="mono" style={{ float: "right" }}>{value}%</span>
    </div>
  );
}
