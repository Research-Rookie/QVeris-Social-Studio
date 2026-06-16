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
  topSymbol: string;
  topChangePct: number;
};

const posts = postsData as Post[];

const categories = [
  { key: "market-pulse", label: "Market Pulse", count: posts.length },
  { key: "agent-rankings", label: "Agent Rankings", count: 0 },
  { key: "trend-disruptors", label: "Trend Disruptors", count: 0 },
  { key: "launch-alerts", label: "Launch Alerts", count: 0 },
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
  const [drafts, setDrafts] = useState<Record<string, string>>(
    Object.fromEntries(posts.map((post) => [post.id, post.tweet])),
  );

  const visiblePosts = useMemo(() => {
    if (activeCategory !== "market-pulse") return [];
    return statusFilter === "all"
      ? posts
      : posts.filter((post) => post.status === statusFilter);
  }, [activeCategory, statusFilter]);

  const publishedCount = posts.filter((post) => post.status === "published").length;
  const readyCount = posts.filter((post) => post.status === "ready").length;
  const latestDate = posts[0]?.date;

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
            const isEditing = editingId === post.id;
            const tweet = drafts[post.id] ?? post.tweet;

            return (
              <article className="postCard" key={post.id}>
                <div className="cardImage">
                  <img src={post.image} alt={`${post.title} for ${post.date}`} />
                  <span className={`status ${post.status}`}>{post.status}</span>
                </div>

                <div className="cardBody">
                  <div className="cardHeading">
                    <div>
                      <span className="contentType">{post.contentType}</span>
                      <h2>{post.title}</h2>
                    </div>
                    <time dateTime={post.date}>{formatDate(post.date)}</time>
                  </div>

                  {isEditing ? (
                    <textarea
                      className="tweetEditor"
                      value={tweet}
                      maxLength={280}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [post.id]: event.target.value,
                        }))
                      }
                    />
                  ) : (
                    <div className="tweetBox">
                      {tweet.split("\n").map((line, index) => (
                        <p key={`${post.id}-${index}`}>{line || "\u00a0"}</p>
                      ))}
                    </div>
                  )}

                  <div className="cardMeta">
                    <span>
                      Leader <b>${post.topSymbol}</b>
                    </span>
                    <span>
                      Move <b>{post.topChangePct.toFixed(2)}%</b>
                    </span>
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
                    <button type="button" onClick={() => copyTweet(post)}>
                      {copiedId === post.id ? "Copied" : "Copy tweet"}
                    </button>
                    <a href={post.image} download>
                      Download image
                    </a>
                    <button
                      type="button"
                      onClick={() => setEditingId(isEditing ? null : post.id)}
                    >
                      {isEditing ? "Done" : "Edit locally"}
                    </button>
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
    </main>
  );
}
