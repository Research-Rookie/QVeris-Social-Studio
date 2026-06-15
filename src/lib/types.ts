export interface StockItem {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume_ratio: number;
  market_cap: number;
  score: number;
}

export interface RankingData {
  updated_at: string;
  date: string;
  top5: StockItem[];
}
