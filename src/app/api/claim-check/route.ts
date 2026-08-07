import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BASE_URL = (process.env.QVERIS_API_BASE_URL || "https://qveris.ai/api/v1").replace(/\/$/, "");
const MAX_CREDITS = Number(process.env.CLAIM_CHECKER_MAX_CREDITS || "8");
const rateLog = new Map<string, number[]>();

type RecordValue = Record<string, unknown>;
type SourceResult = {
  name: string;
  provider: string;
  toolId: string;
  expectedCredits: number;
  latencyMs: number;
  success: boolean;
  payload?: unknown;
  error?: string;
};

const companies: Record<string, string> = {
  apple: "AAPL", nvidia: "NVDA", microsoft: "MSFT", alphabet: "GOOGL",
  google: "GOOGL", amazon: "AMZN", meta: "META", tesla: "TSLA",
  netflix: "NFLX", amd: "AMD", adobe: "ADBE", paypal: "PYPL",
};
const ignoredSymbols = new Set([
  "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "EPS", "FCF",
  "CEO", "CFO", "USD", "API", "AI", "TTM", "YOY", "SEC", "NYSE", "NASDAQ",
]);

function record(value: unknown): RecordValue | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : null;
}

function limited(request: NextRequest) {
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "local";
  const now = Date.now();
  const recent = (rateLog.get(ip) || []).filter((stamp) => now - stamp < 10 * 60 * 1000);
  if (recent.length >= 5) return true;
  recent.push(now);
  rateLog.set(ip, recent);
  return false;
}

function tickerFrom(claim: string) {
  const tag = claim.match(/\$([A-Z]{1,5})\b/);
  if (tag) return tag[1];
  const lower = claim.toLowerCase();
  for (const [company, ticker] of Object.entries(companies)) {
    if (lower.includes(company)) return ticker;
  }
  return (claim.match(/\b[A-Z]{2,5}\b/g) || []).find((item) => !ignoredSymbols.has(item)) || "";
}

function claimType(claim: string) {
  const value = claim.toLowerCase();
  if (/eps|earnings|revenue|guidance|财报|每股收益|营收|业绩/.test(value)) return "earnings";
  if (/market cap|p\/e|pe ratio|fcf|free cash flow|valuation|市值|估值|自由现金流/.test(value)) return "valuation";
  if (/10-k|10-q|8-k|filing|sec filing|公告|监管文件/.test(value)) return "filing";
  if (/headline|news|report|报道|新闻|消息/.test(value)) return "news";
  if (/price|trading|rose|fell|gain|drop|up |down |%|股价|上涨|下跌|涨幅|跌幅/.test(value)) return "price";
  return "general";
}

function queryFor(type: string, ticker: string, claim: string) {
  const symbol = ticker || "the company in this claim";
  const queries: Record<string, string> = {
    price: `Current US stock quote for ${symbol} with latest price percentage change volume and timestamp`,
    earnings: `Latest earnings for ${symbol} with actual EPS estimated EPS revenue and report date`,
    valuation: `Current valuation for ${symbol} including market cap free cash flow and valuation ratios`,
    filing: `Latest SEC filings for ${symbol} with form date title and source URL`,
    news: `Latest financial news for ${symbol} with headline publication time source and sentiment`,
    general: `Financial evidence to verify this market claim about ${symbol}: ${claim.slice(0, 180)}`,
  };
  return queries[type];
}

function expectedCredits(tool: RecordValue) {
  const billing = record(tool.billing_rule);
  const price = record(billing?.price);
  for (const value of [billing?.amount_credits, billing?.amount, price?.amount_credits, tool.cost]) {
    const number = Number(value);
    if (Number.isFinite(number) && number >= 0) return number;
  }
  const match = String(tool.expected_cost || "").match(/[\d.]+/);
  return match ? Number(match[0]) : 0;
}

async function qveris(path: string, payload: RecordValue, query = "") {
  const key = process.env.QVERIS_API_KEY;
  if (!key) throw new Error("QVERIS_API_KEY is not configured on the server.");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45_000);
  try {
    const response = await fetch(`${BASE_URL}${path}${query}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: controller.signal,
    });
    const text = await response.text();
    let data: unknown;
    try { data = JSON.parse(text); } catch { data = { message: text.slice(0, 500) }; }
    if (!response.ok) {
      const details = record(data);
      throw new Error(String(details?.message || details?.error || `QVeris HTTP ${response.status}`));
    }
    return record(data) || {};
  } finally {
    clearTimeout(timeout);
  }
}

function parametersFor(tool: RecordValue, ticker: string, claim: string) {
  const values: RecordValue = {};
  for (const raw of Array.isArray(tool.params) ? tool.params : []) {
    const param = record(raw);
    if (!param) continue;
    const name = String(param.name || "");
    const key = name.toLowerCase();
    if (!name) continue;
    if (["symbol", "ticker", "stock_symbol", "stock"].includes(key)) values[name] = ticker;
    else if (["query", "q", "keyword", "search"].includes(key)) values[name] = claim;
    else if (["limit", "count", "size", "top"].includes(key)) values[name] = 10;
    else if (["market", "country", "region", "exchange"].includes(key)) values[name] = "US";
    else if (key === "function") values[name] = "GLOBAL_QUOTE";
    else if (param.required === true) {
      const type = String(param.type || "").toLowerCase();
      values[name] = /number|integer/.test(type) ? 10 : ticker || claim;
    }
  }
  return values;
}

function flatten(value: unknown, path = "", rows: Array<{ path: string; value: string | number | boolean }> = []) {
  if (Array.isArray(value)) {
    value.slice(0, 20).forEach((child, index) => flatten(child, `${path}[${index}]`, rows));
  } else if (value && typeof value === "object") {
    Object.entries(value as RecordValue).slice(0, 80).forEach(([key, child]) => flatten(child, path ? `${path}.${key}` : key, rows));
  } else if (["string", "number", "boolean"].includes(typeof value) && String(value).length <= 220) {
    rows.push({ path, value: value as string | number | boolean });
  }
  return rows;
}

function evidenceFrom(results: SourceResult[], type: string) {
  const patterns: Record<string, RegExp> = {
    price: /price|close|change|percent|volume|timestamp|date/i,
    earnings: /eps|estimate|actual|surprise|revenue|date/i,
    valuation: /market.?cap|free.?cash|fcf|pe|ratio|yield|revenue/i,
    filing: /filing|form|date|title|url|accession/i,
    news: /headline|title|published|source|sentiment|url/i,
    general: /price|value|date|title|change|revenue|eps|market/i,
  };
  const evidence: Array<{ label: string; value: string; source: string }> = [];
  const seen = new Set<string>();
  for (const result of results.filter((item) => item.success)) {
    for (const row of flatten(result.payload).filter((item) => patterns[type].test(item.path))) {
      const unique = `${row.path}:${row.value}`;
      if (!row.path || seen.has(unique) || String(row.value).trim() === "") continue;
      seen.add(unique);
      const key = (row.path.split(".").pop() || "Evidence").replace(/\[\d+\]/g, "");
      const label = key.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
      let value = String(row.value);
      if (typeof row.value === "number") {
        value = /percent|change|yield|margin/i.test(row.path)
          ? `${row.value.toFixed(2)}%`
          : row.value.toLocaleString("en-US", { maximumFractionDigits: 2 });
      }
      evidence.push({ label, value, source: result.provider });
      if (evidence.length >= 8) return evidence;
    }
  }
  return evidence;
}

function numbersIn(text: string) {
  return [...text.matchAll(/(?:\$\s*)?(-?\d[\d,]*(?:\.\d+)?)\s*(%|[KMBT])?/gi)].map((match) => {
    const suffix = (match[2] || "").toUpperCase();
    const multiplier = ({ K: 1e3, M: 1e6, B: 1e9, T: 1e12 } as Record<string, number>)[suffix] || 1;
    return { value: Number(match[1].replace(/,/g, "")) * multiplier, percent: suffix === "%" };
  }).filter((item) => Number.isFinite(item.value));
}

function verdict(claim: string, evidence: Array<{ value: string }>, sources: number) {
  if (!evidence.length) return { status: "needsContext", label: "Needs context", confidence: 22, note: "No structured evidence was returned for this claim." };
  const claimed = numbersIn(claim);
  const observed = evidence.flatMap((item) => numbersIn(item.value));
  if (!claimed.length || !observed.length) return {
    status: "evidenceFound", label: "Evidence found", confidence: sources > 1 ? 72 : 58,
    note: "Relevant live evidence was found, but the wording needs human interpretation.",
  };
  let difference = Number.POSITIVE_INFINITY;
  for (const left of claimed) for (const right of observed) {
    if (left.percent === right.percent) difference = Math.min(difference, Math.abs(left.value - right.value) / Math.max(Math.abs(left.value), 1));
  }
  if (difference <= .05) return { status: "supported", label: "Supported", confidence: sources > 1 ? 88 : 76, note: "The claim's key number is consistent with the returned market evidence." };
  if (Number.isFinite(difference) && difference >= .2) return { status: "contradicted", label: "Contradicted", confidence: sources > 1 ? 84 : 69, note: "The claim's key number differs materially from the returned market evidence." };
  return { status: "needsContext", label: "Needs context", confidence: 55, note: "The evidence is close, but not strong enough for a clean verdict." };
}

export async function POST(request: NextRequest) {
  if (limited(request)) return NextResponse.json({ error: "Rate limit reached. Try again in a few minutes." }, { status: 429 });
  let body: RecordValue;
  try { body = record(await request.json()) || {}; } catch { return NextResponse.json({ error: "Invalid request body." }, { status: 400 }); }
  const claim = String(body.claim || "").trim();
  if (claim.length < 12 || claim.length > 600) return NextResponse.json({ error: "Enter a claim between 12 and 600 characters." }, { status: 400 });
  const ticker = tickerFrom(claim);
  const type = claimType(claim);
  if (!ticker && type !== "general") return NextResponse.json({ error: "Add a ticker such as $NVDA so the evidence search is precise." }, { status: 400 });

  const sessionId = `claim-checker-${crypto.randomUUID()}`;
  const searchQuery = queryFor(type, ticker, claim);
  try {
    const search = await qveris("/search", { query: searchQuery, limit: 8, session_id: sessionId });
    const searchId = String(search.search_id || "");
    const tools = (Array.isArray(search.results) ? search.results : [])
      .map(record).filter((tool): tool is RecordValue => Boolean(tool?.tool_id))
      .map((tool) => ({ tool, cost: expectedCredits(tool) }))
      .filter(({ cost }) => cost <= MAX_CREDITS).sort((a, b) => a.cost - b.cost).slice(0, 2);
    if (!tools.length) throw new Error("No affordable QVeris evidence capability matched this claim.");

    const results: SourceResult[] = [];
    for (const { tool, cost } of tools) {
      const started = Date.now();
      const toolId = String(tool.tool_id);
      try {
        const execution = await qveris("/tools/execute", {
          search_id: searchId, session_id: sessionId,
          parameters: parametersFor(tool, ticker, claim), max_response_size: 24000,
        }, `?tool_id=${encodeURIComponent(toolId)}`);
        if (execution.success === false) throw new Error(String(execution.error_message || "Execution failed"));
        results.push({ name: String(tool.name || "QVeris capability"), provider: String(tool.provider_name || tool.provider || "QVeris provider"), toolId, expectedCredits: cost, latencyMs: Date.now() - started, success: true, payload: execution.result });
      } catch (error) {
        results.push({ name: String(tool.name || "QVeris capability"), provider: String(tool.provider_name || tool.provider || "QVeris provider"), toolId, expectedCredits: cost, latencyMs: Date.now() - started, success: false, error: error instanceof Error ? error.message : "Execution failed" });
      }
    }
    const evidence = evidenceFrom(results, type);
    const sourceCount = results.filter((item) => item.success).length;
    return NextResponse.json({
      claim, ticker: ticker || "Not detected", claimType: type,
      verdict: verdict(claim, evidence, sourceCount), evidence,
      sources: results.map(({ payload: _payload, ...source }) => source),
      checkedAt: new Date().toISOString(),
      disclaimer: "Automated evidence check, not investment advice. Review source context before relying on the result.",
    });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "The evidence check failed." }, { status: 502 });
  }
}
