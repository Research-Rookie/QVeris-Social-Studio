"use client";

import { useState } from "react";

const categories = [
  { key: "agent-rankings", label: "Agent Rankings", count: 0 },
  { key: "trend-disruptors", label: "Trend Disruptors", count: 0 },
  { key: "launch-alerts", label: "Launch Alerts", count: 0 },
  { key: "outage-reports", label: "Outage Reports", count: 0 },
  { key: "market-pulse", label: "Market Pulse", count: 1 },
];

const marketTweet = `U.S. stock market movers for June 10, 2026 \u{1F4CA}

\u{1F7E2} Top gainer: CPOP +322.22%
\u{1F534} Top loser: MLACU -67.42%

Explore the Top 10 gainers and losers by price change.

Data: Alpha Vantage
For informational purposes only. Not investment advice.

#StockMarket #MarketData #Stocks`;

const postsByCategory: Record<string, { contentType: string; title: string; tweet: string; image: string }[]> = {
  "agent-rankings": [],
  "trend-disruptors": [],
  "launch-alerts": [],
  "outage-reports": [],
  "market-pulse": [
    {
      contentType: "MARKET DATA",
      title: "U.S. Stock Market Movers",
      tweet: marketTweet,
      image: "/market-movers-en.png?v=3",
    },
  ],
};

export default function Home() {
  const [activeCategory, setActiveCategory] = useState("market-pulse");
  const [tweet, setTweet] = useState(marketTweet);
  const [draft, setDraft] = useState(marketTweet);
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);

  const posts = postsByCategory[activeCategory] || [];
  const cat = categories.find((c) => c.key === activeCategory)!;

  function switchCategory(key: string) {
    setActiveCategory(key);
    const first = postsByCategory[key]?.[0];
    if (first) {
      setTweet(first.tweet);
      setDraft(first.tweet);
    }
    setEditing(false);
  }

  function startEditing() {
    setDraft(tweet);
    setEditing(true);
  }

  function saveDraft() {
    setTweet(draft);
    setEditing(false);
  }

  function cancelEditing() {
    setDraft(tweet);
    setEditing(false);
  }

  async function copyTweet() {
    await navigator.clipboard.writeText(tweet);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#">
          <img className="brandMark" src="/logo-color.avif" alt="QVeris" />
          <span>QVeris</span>
        </a>
        <div className="topbarRight">
          <span className="environment">
            <span className="liveDot" />
            Content workspace
          </span>
          <button className="avatar" aria-label="Account">
            QV
          </button>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">SOCIAL CONTENT OPERATIONS</p>
          <h1>QVeris Social Studio</h1>
          <p className="heroCopy">
            Review data visuals, polish post copy, and prepare every update for
            publishing from one place.
          </p>
        </div>
        <button className="primaryButton" type="button">
          + New post
        </button>
      </section>

      <nav className="categoryBar" aria-label="Content categories">
        {categories.map((c) => (
          <button
            key={c.key}
            className={`categoryChip ${c.key === activeCategory ? "active" : ""}`}
            type="button"
            onClick={() => switchCategory(c.key)}
          >
            <span className="categoryLabel">{c.label}</span>
            <span className="categoryCount">{c.count}</span>
          </button>
        ))}
      </nav>

      <section className="toolbar">
        <div className="tabs">
          <button className="tab active" type="button">
            All
          </button>
          <button className="tab" type="button">
            Drafts
          </button>
          <button className="tab" type="button">
            Ready
          </button>
          <button className="tab" type="button">
            Published
          </button>
        </div>
        <span className="updated">Last updated June 11, 2026</span>
      </section>

      {posts.length > 0 ? (
        posts.map((post, i) => (
          <article className="postCard" key={i}>
            <div className="visualPane">
              <div className="visualHeader">
                <div>
                  <span className="contentType">{post.contentType}</span>
                  <h2>{post.title}</h2>
                </div>
                <span className="status ready">
                  <span />
                  Ready
                </span>
              </div>

              <div className="imageFrame">
                <img src={post.image} alt={post.title} />
              </div>

              <div className="imageMeta">
                <span>1200 × 900 PNG</span>
                <a href={post.image} download>
                  Download image
                </a>
              </div>
            </div>

            <div className="copyPane">
              <div className="copyHeader">
                <div>
                  <span className="sectionLabel">X POST COPY</span>
                  <span className="characterCount">
                    {editing ? draft.length : tweet.length} / 280 characters
                  </span>
                </div>
                <button className="copyButton" type="button" onClick={copyTweet}>
                  {copied ? "Copied" : "Copy text"}
                </button>
              </div>

              {editing ? (
                <textarea
                  className="tweetEditor"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={10}
                />
              ) : (
                <div className="tweetBox">
                  {tweet.split("\n").map((line, idx) => (
                    <p key={`${line}-${idx}`}>{line || " "}</p>
                  ))}
                </div>
              )}

              <div className="details">
                <div>
                  <span>Data source</span>
                  <strong>Alpha Vantage</strong>
                </div>
                <div>
                  <span>Data date</span>
                  <strong>June 10, 2026</strong>
                </div>
                <div>
                  <span>Channel</span>
                  <strong>X / Twitter</strong>
                </div>
              </div>

              <div className="actions">
                {editing ? (
                  <>
                    <button className="secondaryButton" type="button" onClick={cancelEditing}>
                      Cancel
                    </button>
                    <button className="saveButton" type="button" onClick={saveDraft}>
                      Save draft
                    </button>
                  </>
                ) : (
                  <>
                    <button className="secondaryButton" type="button" onClick={startEditing}>
                      Edit draft
                    </button>
                    <button className="publishButton" type="button" disabled>
                      Connect X to publish
                    </button>
                  </>
                )}
              </div>
              <p className="publishNote">
                Publishing is disabled until an X developer account and API
                credentials are connected.
              </p>
            </div>
          </article>
        ))
      ) : (
        <div className="emptyState">
          <p className="emptyIcon">📭</p>
          <p className="emptyTitle">No posts yet</p>
          <p className="emptyDesc">
            Content for <strong>{cat.label}</strong> will appear here once a post
            is created.
          </p>
        </div>
      )}
    </main>
  );
}
