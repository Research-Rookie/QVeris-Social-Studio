"use client";

import { useMemo, useState } from "react";
import postsData from "../../data/posts.json";

type PostStatus = "draft" | "ready" | "published";

type Post = {
  id: string;
  date: string;
  runDate?: string;
  marketDate?: string;
  createdAt: string;
  contentType: string;
  title: string;
  status: PostStatus;
  tweet: string;
  image: string;
  dataSource: string;
  dataUpdatedAt: string;
  xPostId?: string | null;
  topSymbol?: string;
  topChangePct?: number;
  primaryLabel?: string;
  primaryValue?: string;
  secondaryLabel?: string;
  secondaryValue?: string;
};

const posts = postsData as Post[];

const columnDescriptions: Record<string, string> = {
  "market-pulse": "Daily liquid U.S. stock movers surfaced from market data.",
  "fcf-yield": "Free-cash-flow yield comparisons for valuation snapshots.",
  "polymarket-pulse": "Prediction-market attention, open interest, and hot themes.",
  "financial-news-signal": "Financial headlines distilled into tickers, themes, and tone.",
  "financial-data-api-watch": "QVeris API workflows showing what finance agents can retrieve.",
  "news-vs-price-reaction": "Compares headline tone with the stock's price reaction.",
  "market-narrative-shift": "Shows how a ticker's news themes, language, and sentiment changed.",
  "earnings-reality-check": "Tests an earnings surprise against the stock's next-session reaction.",
  "api-reliability-arena": "Ranks finance APIs using QVeris reliability, latency, and expected-cost signals.",
  "live-api-battle": "Runs the same market question through live APIs and compares response quality.",
};

function categoryKey(post: Post) {
  if (post.contentType === "MARKET PULSE") return "market-pulse";
  if (post.contentType === "FCF YIELD") return "fcf-yield";
  if (post.contentType === "POLYMARKET PULSE") return "polymarket-pulse";
  if (post.contentType === "PREDICTION MARKET RADAR") return "polymarket-pulse";
  if (post.contentType === "FINANCIAL NEWS SIGNAL") return "financial-news-signal";
  if (post.contentType === "FINANCIAL DATA API WATCH") return "financial-data-api-watch";
  if (post.contentType === "NEWS VS PRICE REACTION") return "news-vs-price-reaction";
  if (post.contentType === "MARKET NARRATIVE SHIFT") return "market-narrative-shift";
  if (post.contentType === "EARNINGS REALITY CHECK") return "earnings-reality-check";
  if (post.contentType === "API RELIABILITY ARENA") return "api-reliability-arena";
  if (post.contentType === "LIVE API BATTLE") return "live-api-battle";
  return null;
}

const activePosts = posts.filter((post) => categoryKey(post) !== null);

const categories = [
  {
    key: "market-pulse",
    label: "Market Pulse",
    count: activePosts.filter((post) => categoryKey(post) === "market-pulse").length,
  },
  {
    key: "fcf-yield",
    label: "FCF Yield",
    count: activePosts.filter((post) => categoryKey(post) === "fcf-yield").length,
  },
  {
    key: "polymarket-pulse",
    label: "Prediction Radar",
    count: activePosts.filter((post) => categoryKey(post) === "polymarket-pulse").length,
  },
  {
    key: "financial-news-signal",
    label: "News Signal",
    count: activePosts.filter((post) => categoryKey(post) === "financial-news-signal").length,
  },
  {
    key: "financial-data-api-watch",
    label: "API Watch",
    count: activePosts.filter((post) => categoryKey(post) === "financial-data-api-watch").length,
  },
  {
    key: "news-vs-price-reaction",
    label: "News vs Price",
    count: activePosts.filter((post) => categoryKey(post) === "news-vs-price-reaction").length,
  },
  {
    key: "market-narrative-shift",
    label: "Narrative Shift",
    count: activePosts.filter((post) => categoryKey(post) === "market-narrative-shift").length,
  },
  {
    key: "earnings-reality-check",
    label: "Earnings Check",
    count: activePosts.filter((post) => categoryKey(post) === "earnings-reality-check").length,
  },
  {
    key: "api-reliability-arena",
    label: "API Arena",
    count: activePosts.filter((post) => categoryKey(post) === "api-reliability-arena").length,
  },
  {
    key: "live-api-battle",
    label: "Live Battle",
    count: activePosts.filter((post) => categoryKey(post) === "live-api-battle").length,
  },
];

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

export default function Home() {
  const [activeCategory, setActiveCategory] = useState("market-pulse");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedPostId, setCopiedPostId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>(
    Object.fromEntries(activePosts.map((post) => [post.id, post.tweet])),
  );

  const visiblePosts = useMemo(() => {
    return activePosts.filter((post) => {
      if (categoryKey(post) !== activeCategory) return false;
      return true;
    });
  }, [activeCategory]);

  const publishedCount = activePosts.filter((post) => post.status === "published").length;
  const readyCount = activePosts.filter((post) => post.status === "ready").length;
  const latestDate = activePosts[0]?.date;
  const selectedPost = activePosts.find((post) => post.id === selectedPostId) ?? null;

  async function copyTweet(post: Post) {
    await navigator.clipboard.writeText(drafts[post.id] ?? post.tweet);
    setCopiedId(post.id);
    window.setTimeout(() => setCopiedId(null), 1500);
  }

  async function copyPostId(post: Post) {
    await navigator.clipboard.writeText(post.id);
    setCopiedPostId(post.id);
    window.setTimeout(() => setCopiedPostId(null), 1500);
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#">
          <img className="brandMark" src="/logo-color.avif" alt="QVeris" />
          <span className="brandCopy">
            <strong>QVeris Social Studio</strong>
            <em>market cards / tweet drafts / publishing queue</em>
          </span>
        </a>
        <div className="topbarCenter">
          QVeris-powered market cards, tweet drafts, and daily signal archive.
        </div>
        <div className="topbarRight">
          <a className="toolLaunch" href="/tools/financial-claim-checker">
            Claim Checker
          </a>
          <span className="environment">
            <span className="liveDot" />
            Daily archive
          </span>
          <span className="avatar">QV</span>
        </div>
      </header>

      <div className="appShell">
        <section className="trainingPanel" id="workflow">
          <div className="trainingCopy">
            <p className="eyebrow">AUTOMATED RESEARCH DESK</p>
            <strong>From QVeris data calls to publish-ready market cards</strong>
            <span>
              Each column turns raw financial data, news, valuation, and prediction-market
              signals into an image plus a short social post. New runs append to the
              archive instead of overwriting prior cards.
            </span>
          </div>
          <div className="trainingCounts" aria-label="Archive summary">
            <article>
              <strong>{posts.length}</strong>
              <span>Total cards</span>
            </article>
            <article>
              <strong>{categories.length}</strong>
              <span>Signal columns</span>
            </article>
            <article>
              <strong>{readyCount}</strong>
              <span>Ready drafts</span>
            </article>
          </div>
          <div className="automationBadge">
            <span className="automationDot" />
            {latestDate ? `Latest ${formatDate(latestDate)}` : "No data yet"}
          </div>
        </section>

        <section className="filterPanel" id="categories">
          <div className="searchRow">
            <div>
              <p className="eyebrow">QVERIS CONTENT LIBRARY</p>
              <h1>Social signal archive</h1>
              <p className="libraryIntro">
                Pick a signal column below. Each card opens into the generated image,
                tweet copy, publish ID, and download action.
              </p>
            </div>
            <div className="sortSegment" aria-label="Content categories">
              {categories.map((category) => (
                <button
                  key={category.key}
                  className={`categoryChip ${
                    category.key === activeCategory ? "active" : ""
                  }`}
                  type="button"
                  onClick={() => setActiveCategory(category.key)}
                >
                  <span>{category.label}</span>
                  <b>{category.count}</b>
                </button>
              ))}
            </div>
          </div>
          <div className="columnGuide">
            {categories.map((category) => (
              <button
                key={`${category.key}-guide`}
                className={`guideCard ${
                  category.key === activeCategory ? "active" : ""
                }`}
                type="button"
                onClick={() => setActiveCategory(category.key)}
              >
                <span>{category.label}</span>
                <strong>{category.count}</strong>
                <em>{columnDescriptions[category.key]}</em>
              </button>
            ))}
          </div>
        </section>

        <section className="resultHead" id="archive">
          <div>
            <strong>{visiblePosts.length} cards</strong>
            <span>
              {latestDate
                ? `Archived through ${formatDate(latestDate)}`
                : "No updates yet"}
            </span>
          </div>
          <span className="updated">Click a card to inspect image and tweet copy</span>
        </section>

      {visiblePosts.length ? (
        <section className="cardsGrid">
          {visiblePosts.map((post) => {
            const tweet = drafts[post.id] ?? post.tweet;

            return (
              <article className="postCard" key={post.id}>
                <div className="assetSource">
                  <span className="sourceMark">QV</span>
                  <span className="sourceCopy">
                    <strong>{post.contentType}</strong>
                    <em>{post.dataSource}</em>
                  </span>
                </div>
                <button
                  className="cardImage cardImageButton"
                  type="button"
                  onClick={() => setSelectedPostId(post.id)}
                >
                  <img src={post.image} alt={`${post.title} for ${post.date}`} />
                  <span className={`status ${post.status}`}>{post.status}</span>
                </button>

                <div className="cardBody">
                  <div className="cardHeading">
                    <div>
                      <h2>{post.title}</h2>
                    </div>
                    <time dateTime={post.date}>{formatDate(post.date)}</time>
                  </div>

                  <div className="cardMeta">
                    {post.primaryLabel && post.primaryValue ? (
                      <span>
                        {post.primaryLabel} <b>{post.primaryValue}</b>
                      </span>
                    ) : (
                      <span>
                        Leader <b>${post.topSymbol}</b>
                      </span>
                    )}
                    {post.secondaryLabel && post.secondaryValue ? (
                      <span>
                        {post.secondaryLabel} <b>{post.secondaryValue}</b>
                      </span>
                    ) : post.topChangePct !== undefined ? (
                      <span>
                        Move <b>{post.topChangePct.toFixed(2)}%</b>
                      </span>
                    ) : null}
                    <span>
                      Copy <b>{tweet.length}/280</b>
                    </span>
                    {post.marketDate ? (
                      <span>
                        Market date <b>{formatDate(post.marketDate)}</b>
                      </span>
                    ) : null}
                  </div>

                  <div className="cardActions">
                    <button type="button" onClick={() => setSelectedPostId(post.id)}>
                      Open
                    </button>
                    <button type="button" onClick={() => copyTweet(post)}>
                      {copiedId === post.id ? "Copied" : "Copy tweet"}
                    </button>
                    <button
                      type="button"
                      className="publishButton"
                      onClick={() => copyPostId(post)}
                    >
                      {copiedPostId === post.id ? "ID copied" : "Copy ID"}
                    </button>
                    <a href={post.image} download>
                      Download
                    </a>
                  </div>
                  <p className="publishMessage">
                    Use this ID in the GitHub Action: <b>{post.id}</b>
                  </p>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <div className="emptyState">
          <strong>No cards here yet</strong>
          <p>New content will appear after the daily automation runs.</p>
        </div>
      )}
      </div>

      {selectedPost ? (
        <div
          className="modalOverlay"
          role="dialog"
          aria-modal="true"
          aria-label={`${selectedPost.title} details`}
          onClick={() => setSelectedPostId(null)}
        >
          <article className="modalCard" onClick={(event) => event.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <span className="contentType">{selectedPost.contentType}</span>
                <h2>{selectedPost.title}</h2>
                <p>
                  {formatDate(selectedPost.date)}
                  {selectedPost.marketDate
                    ? ` - Market date ${formatDate(selectedPost.marketDate)}`
                    : ""}
                </p>
              </div>
              <button
                className="closeButton"
                type="button"
                onClick={() => setSelectedPostId(null)}
              >
                Close
              </button>
            </div>

            <div className="modalContent">
              <img
                className="modalImage"
                src={selectedPost.image}
                alt={`${selectedPost.title} for ${selectedPost.date}`}
              />

              <div className="modalSide">
                {editingId === selectedPost.id ? (
                  <textarea
                    className="tweetEditor"
                    value={drafts[selectedPost.id] ?? selectedPost.tweet}
                    maxLength={280}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [selectedPost.id]: event.target.value,
                      }))
                    }
                  />
                ) : (
                  <div className="tweetBox modalTweet">
                    {(drafts[selectedPost.id] ?? selectedPost.tweet)
                      .split("\n")
                      .map((line, index) => (
                        <p key={`${selectedPost.id}-${index}`}>{line || "\u00a0"}</p>
                      ))}
                  </div>
                )}

                <div className="cardMeta modalMeta">
                  {selectedPost.primaryLabel && selectedPost.primaryValue ? (
                    <span>
                      {selectedPost.primaryLabel} <b>{selectedPost.primaryValue}</b>
                    </span>
                  ) : (
                    <span>
                      Leader <b>${selectedPost.topSymbol}</b>
                    </span>
                  )}
                  {selectedPost.secondaryLabel && selectedPost.secondaryValue ? (
                    <span>
                      {selectedPost.secondaryLabel} <b>{selectedPost.secondaryValue}</b>
                    </span>
                  ) : selectedPost.topChangePct !== undefined ? (
                    <span>
                      Move <b>{selectedPost.topChangePct.toFixed(2)}%</b>
                    </span>
                  ) : null}
                  <span>
                    Copy{" "}
                    <b>
                      {(drafts[selectedPost.id] ?? selectedPost.tweet).length}/280
                    </b>
                  </span>
                </div>

                <div className="cardActions">
                  <button type="button" onClick={() => copyTweet(selectedPost)}>
                    {copiedId === selectedPost.id ? "Copied" : "Copy tweet"}
                  </button>
                  <button
                    type="button"
                    className="publishButton"
                    onClick={() => copyPostId(selectedPost)}
                  >
                    {copiedPostId === selectedPost.id ? "ID copied" : "Copy publish ID"}
                  </button>
                  <a href={selectedPost.image} download>
                    Download image
                  </a>
                  <button
                    type="button"
                    onClick={() =>
                      setEditingId(
                        editingId === selectedPost.id ? null : selectedPost.id,
                      )
                    }
                  >
                    {editingId === selectedPost.id ? "Done" : "Edit locally"}
                  </button>
                </div>
                <p className="publishMessage">
                  GitHub Action post_id: <b>{selectedPost.id}</b>
                </p>
              </div>
            </div>
          </article>
        </div>
      ) : null}
    </main>
  );
}
