import type {
  WatchlistItem, DailySummary, ExpirySummary,
  ChainSnapshot, MoneynessData, UnusualActivity, Sentiment,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json()
}

export const api = {
  watchlist: () =>
    get<WatchlistItem[]>('/watchlist'),

  sentiment: (symbol: string, date?: string) =>
    get<Sentiment>(`/sentiment/${symbol}${date ? `?date=${date}` : ''}`),

  summary: (symbol: string, start: string, end: string) =>
    get<DailySummary[]>(`/summary/${symbol}?start=${start}&end=${end}`),

  expiry: (symbol: string, date?: string) =>
    get<ExpirySummary[]>(`/expiry/${symbol}${date ? `?date=${date}` : ''}`),

  chain: (symbol: string, date?: string) =>
    get<ChainSnapshot[]>(`/chain/${symbol}${date ? `?date=${date}` : ''}`),

  moneyness: (symbol: string, date?: string) =>
    get<MoneynessData>(`/moneyness/${symbol}${date ? `?date=${date}` : ''}`),

  unusual: (symbol?: string, days = 14) =>
    get<UnusualActivity[]>(`/unusual?days=${days}${symbol ? `&symbol=${symbol}` : ''}`),
}
