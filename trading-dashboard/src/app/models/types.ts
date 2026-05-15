// Shared TypeScript interfaces matching the Flask API response shapes.

export interface PriceRecord {
  date: string;
  Open: number;
  High: number;
  Low: number;
  Close: number;
  Volume: number;
  RSI: number | null;     // null for the first ~14 warm-up rows
  SMA_20: number | null;  // null for the first ~20 warm-up rows
  SMA_50: number | null;  // null for the first ~50 warm-up rows
  Signal: 'BUY' | 'SELL' | 'HOLD';
  ML_Signal?: 'BUY' | 'SELL' | 'HOLD';  // present only from /ml-signals endpoint
}

export interface PricesResponse {
  asset: string;
  name: string;
  count: number;
  data: PriceRecord[];
}

export interface TradeRecord {
  Date: string;
  Asset: string;
  Signal: 'BUY' | 'SELL' | 'HOLD';
  Close: number;
  RSI: number;
  SMA_20: number;
}

export interface TradesResponse {
  count: number;
  trades: TradeRecord[];
}

export interface PaperTradeRecord {
  Asset: string;
  'Entry Date': string;
  'Entry Price': number;
  'Exit Date': string;
  'Exit Price': number;
  'PnL $': number;
  'PnL %': number;
  Result: 'WIN' | 'LOSS';
}

export interface PaperTradesResponse {
  count: number;
  trades: PaperTradeRecord[];
}
