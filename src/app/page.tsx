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

function categoryKey(post: Post) {
  if (post.contentType === "FCF YIELD") return "fcf-yield";
  return "market-pulse";
}

const categories = [
  {
    key: "market-pulse",
    label: "Market Pulse",
    count: posts.filter((post) => categoryKey(post) === "market-pulse").length,
  },
  {
    key: "fcf-yield",
    label: "FCF Yield",
    count: posts.filter((post) => categoryKey(post) === "fcf-yield").length,
  },
  { key: "earnings", label: "Earnings", count: 0 },
  { key: "comparisons", label: "Comparisons", count: 0 },
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
  const [statusFilter, setStatusFilter] = useState<"all" | PostStatus>("all");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>(
    Object.fromEntries(posts.map((post) => [post.id, post.tweet])),
  );

  const visiblePosts = useMemo(() => {
    return posts.filter((post) => {
      if (categoryKey(post) !== activeCategory) return false;
      return statusFilter === "all" || post.status === statusFilter;
    });
  }, [activeCategory, statusFilter]);

  const publishedCount = posts.filter((post) => post.status === "published").length;
  const readyCount = posts.filter((post) => post.status === "ready").length;
  const latestDate = posts[0]?.date;
  const selectedPost = posts.find((post) => post.id === selectedPostId) ?? null;

  async function copyTweet(post: Post) {
    await navigator.clipboard.writeText(drafts[post.id] ?? post.tweet);
    setCopiedId(post.id);
    window.setTimeout(() => setCopiedId(null), 1500);
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
            Daily content archive
          </span>
          <span className="avatar">QV</span>
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">SOCIAL CONTENT OPERATIONS</p>
          <h1>QVeris Social Studio</h1>
          <p className="heroCopy">
            Daily market visuals and X drafts, archived automatically without
            overwriting previous posts.
          </p>
        </div>
        <div className="automationBadge">
          <span className="automationDot" />
          Daily pipeline active
        </div>
      </section>

      <section className="stats" aria-label="Archive summary">
        <article>
          <span>Total cards</span>
          <strong>{posts.length}</strong>
        </article>
        <article>
          <span>Ready</span>
          <strong>{readyCount}</strong>
        </article>
        <article>
          <span>Published</span>
          <strong>{publishedCount}</strong>
        </article>
        <article>
          <span>Latest card date</span>
          <strong className="dateMetric">
            {latestDate ? formatDate(latestDate) : "No data"}
          </strong>
        </article>
      </section>

      <nav className="categoryBar" aria-label="Content categories">
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
      </nav>

      <section className="toolbar">
        <div className="tabs">
          {(["all", "draft", "ready", "published"] as const).map((status) => (
            <button
              key={status}
              className={`tab ${statusFilter === status ? "active" : ""}`}
              type="button"
              onClick={() => setStatusFilter(status)}
            >
              {status === "all"
                ? "All"
                : status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
        <span className="updated">
          {latestDate ? `Archived through ${formatDate(latestDate)}` : "No updates yet"}
        </span>
      </section>

      {visiblePosts.length ? (
        <section className="cardsGrid">
          {visiblePosts.map((post) => {
            const tweet = drafts[post.id] ?? post.tweet;

            return (
              <article className="postCard" key={post.id}>
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
                      <span className="contentType">{post.contentType}</span>
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
                    <a href={post.image} download>
                      Download
                    </a>
                  </div>
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
                    ? ` · Market date ${formatDate(selectedPost.marketDate)}`
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
              </div>
            </div>
          </article>
        </div>
      ) : null}
    </main>
  );
}
