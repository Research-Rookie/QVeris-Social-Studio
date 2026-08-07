"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import styles from "./claim-checker.module.css";

type CheckResult = {
  ticker: string;
  claimType: string;
  verdict: { status: string; label: string; confidence: number; note: string };
  evidence: Array<{ label: string; value: string; source: string }>;
  sources: Array<{ name: string; provider: string; toolId: string; expectedCredits: number; latencyMs: number; success: boolean }>;
  checkedAt: string;
  disclaimer: string;
};

const examples = [
  "$NVDA is trading above $150 today.",
  "$AAPL reported EPS of $1.40 in its latest earnings release.",
  "$PYPL has a free cash flow yield above 10%.",
];

export default function FinancialClaimChecker() {
  const [claim, setClaim] = useState(examples[0]);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const response = await fetch("/api/claim-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The claim check failed.");
      setResult(data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The claim check failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <nav className={styles.nav}>
        <Link className={styles.brand} href="/">
          <img src="/logo-color.avif" alt="" />
          <span>QVeris <b>Claim Lab</b></span>
        </Link>
        <div className={styles.navRight}>
          <span className={styles.live}><i />Live QVeris evidence</span>
          <Link className={styles.backLink} href="/">Social Studio</Link>
        </div>
      </nav>

      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>FINANCIAL CLAIM CHECKER</p>
          <h1>Don&apos;t trust the headline.<br /><em>Trace the evidence.</em></h1>
          <p className={styles.lede}>Paste a market claim, ticker take, or financial headline. QVeris discovers the right data capabilities, checks live evidence, and shows what holds up.</p>
          <div className={styles.proofRow}>
            <span><b>01</b> Parse the claim</span><span><b>02</b> Route to data</span><span><b>03</b> Explain the verdict</span>
          </div>
        </div>
        <div className={styles.signalArt} aria-hidden="true">
          <div className={styles.signalCard}><span>CLAIM</span><b>“$NVDA is above $150”</b></div>
          <div className={styles.signalLine}><i /><i /><i /></div>
          <div className={styles.signalStamp}>CHECKED<br /><small>via QVeris</small></div>
        </div>
      </section>

      <section className={styles.workbench}>
        <form className={styles.claimPanel} onSubmit={submit}>
          <PanelHead step="01" title="Enter a financial claim" suffix={`${claim.length}/600`} />
          <textarea value={claim} onChange={(event) => setClaim(event.target.value.slice(0, 600))} placeholder="Example: $NVDA is trading above $150 today." aria-label="Financial claim" />
          <div className={styles.examples}>
            <span>Try an example</span>
            {examples.map((example) => <button key={example} type="button" onClick={() => setClaim(example)}>{example.split(" ").slice(0, 5).join(" ")}...</button>)}
          </div>
          <button className={styles.checkButton} type="submit" disabled={loading || claim.trim().length < 12}>
            <span>{loading ? "Tracing live evidence" : "Check this claim"}</span><i>{loading ? "···" : "→"}</i>
          </button>
          {error ? <p className={styles.error} role="alert">{error}</p> : null}
        </form>

        <section className={styles.resultPanel} aria-live="polite">
          <PanelHead step="02" title="Evidence report" suffix={result ? new Date(result.checkedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""} />
          {!result && !loading ? <EmptyResult /> : null}
          {loading ? <LoadingState /> : null}
          {result ? <Report result={result} /> : null}
        </section>
      </section>

      <section className={styles.howItWorks}>
        <div><p className={styles.eyebrow}>WHY QVERIS</p><h2>One claim. The right financial data route.</h2></div>
        <div className={styles.featureGrid}>
          <article><span>DISCOVER</span><h3>Capability matching</h3><p>QVeris finds finance APIs suited to the ticker, metric, and timeframe in the claim.</p></article>
          <article><span>VERIFY</span><h3>Structured evidence</h3><p>The checker extracts comparable facts instead of returning a loose search summary.</p></article>
          <article><span>EXPLAIN</span><h3>Visible uncertainty</h3><p>Ambiguous claims stay ambiguous. The result shows confidence, sources, and limitations.</p></article>
        </div>
      </section>

      <footer className={styles.footer}><span>Built with QVeris API</span><a href="https://qveris.ai/docs/rest-api" target="_blank" rel="noreferrer">API documentation ↗</a></footer>
    </main>
  );
}

function PanelHead({ step, title, suffix }: { step: string; title: string; suffix: string }) {
  return <div className={styles.panelHead}><div><span className={styles.step}>{step}</span><h2>{title}</h2></div>{suffix ? <span className={styles.suffix}>{suffix}</span> : null}</div>;
}

function EmptyResult() {
  return <div className={styles.emptyResult}><div className={styles.emptyIcon}>?</div><h3>Your verdict will appear here</h3><p>We show the data route, provider, evidence fields, and uncertainty. No black-box “trust us” answer.</p></div>;
}

function LoadingState() {
  return <div className={styles.loadingState}><div className={styles.loader}><i /><i /><i /></div><h3>QVeris is routing your claim</h3><p>Discovering suitable market-data tools and collecting structured evidence.</p></div>;
}

function Report({ result }: { result: CheckResult }) {
  return <div className={styles.report}>
    <div className={`${styles.verdict} ${styles[result.verdict.status] || ""}`}>
      <div><span>VERDICT</span><strong>{result.verdict.label}</strong><p>{result.verdict.note}</p></div>
      <div className={styles.confidence}><b>{result.verdict.confidence}</b><span>% confidence</span></div>
    </div>
    <div className={styles.reportMeta}><span>Ticker <b>{result.ticker}</b></span><span>Claim type <b>{result.claimType}</b></span><span>Sources <b>{result.sources.filter((source) => source.success).length}</b></span></div>
    <div className={styles.evidenceList}>
      <h3>Evidence trail</h3>
      {result.evidence.length ? result.evidence.map((item, index) => <article key={`${item.label}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><small>{item.label}</small><strong>{item.value}</strong></div><em>{item.source}</em></article>) : <p className={styles.noEvidence}>No structured fields were returned. Review the data route below.</p>}
    </div>
    <details className={styles.sources}><summary>View QVeris data route</summary>{result.sources.map((source) => <div key={source.toolId}><span className={source.success ? styles.sourceOk : styles.sourceFail} /><p><b>{source.name}</b><small>{source.provider} · {source.latencyMs} ms · {source.expectedCredits} credits</small></p></div>)}</details>
    <p className={styles.disclaimer}>{result.disclaimer}</p>
  </div>;
}
