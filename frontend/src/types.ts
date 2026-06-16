export interface WatchlistItem {
  symbol: string
  name: string
  stock_price: number | null
  stock_change_pct: number | null
  last_date: string | null
}

export interface DailySummary {
  collect_date: string
  stock_price: number | null
  stock_change_pct: number | null
  total_call_oi: number
  total_put_oi: number
  oi_pc_ratio: number | null
  total_call_volume: number
  total_put_volume: number
  vol_pc_ratio: number | null
  avg_call_iv: number | null
  avg_put_iv: number | null
  max_call_oi_strike: number | null
  max_put_oi_strike: number | null
}

export interface ExpirySummary {
  expiry: string
  call_oi: number
  put_oi: number
  oi_pc_ratio: number | null
  call_volume: number
  put_volume: number
  vol_pc_ratio: number | null
  avg_call_iv: number | null
  avg_put_iv: number | null
  days_to_expiry: number
}

export interface ChainSnapshot {
  expiry: string
  side: 'call' | 'put'
  strike: number
  open_interest: number
  volume: number
  iv_pct: number | null
  in_the_money: boolean
  last_price: number | null
  bid: number | null
  ask: number | null
}

export interface MoneynessData {
  call?: { itm: number; atm: number; otm: number }
  put?: { itm: number; atm: number; otm: number }
}

export interface UnusualActivity {
  detect_date: string
  symbol: string
  alert_type: string
  side: string | null
  strike: number | null
  expiry: string | null
  current_value: number | null
  previous_value: number | null
  change_pct: number | null
  description: string | null
}

export interface SentimentCard {
  label: string
  val: string
  cls: 'red' | 'green' | 'yellow'
}

export interface Sentiment {
  pressure: SentimentCard | null
  flow: SentimentCard | null
  legacy: SentimentCard | null
}
