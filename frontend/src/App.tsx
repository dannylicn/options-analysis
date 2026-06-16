import { useState, useEffect } from 'react'
import { api } from './api'
import type { WatchlistItem, Sentiment } from './types'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import Overview from './tabs/Overview'
import OptionsChain from './tabs/OptionsChain'
import ExpiryAnalysis from './tabs/ExpiryAnalysis'
import UnusualActivity from './tabs/UnusualActivity'

const TABS = ['Overview', 'Options Chain', 'Expiry Analysis', 'Unusual Activity'] as const
type Tab = typeof TABS[number]

function today() { return new Date().toISOString().slice(0, 10) }
function daysAgo(n: number) {
  const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10)
}

export default function App() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [symbol, setSymbol] = useState<string>('NIO')
  const [tab, setTab] = useState<Tab>('Overview')
  const [start, setStart] = useState(daysAgo(30))
  const [end, setEnd] = useState(today())
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)

  useEffect(() => {
    api.watchlist().then(w => {
      setWatchlist(w)
      if (w.length > 0) setSymbol(w[0].symbol)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    setSentiment(null)
    api.sentiment(symbol).then(setSentiment).catch(() => {})
  }, [symbol, end])

  const current = watchlist.find(w => w.symbol === symbol)

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        watchlist={watchlist}
        symbol={symbol}
        start={start}
        end={end}
        onSymbol={setSymbol}
        onStart={setStart}
        onEnd={setEnd}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header item={current} sentiment={sentiment} />
        <nav style={{
          display: 'flex', background: 'var(--bg2)',
          borderBottom: '1px solid var(--border)', padding: '0 24px', flexShrink: 0,
        }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '12px 18px',
              fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500,
              color: tab === t ? 'var(--blue)' : 'var(--muted)',
              background: 'none', border: 'none',
              borderBottom: tab === t ? '2px solid var(--blue)' : '2px solid transparent',
              cursor: 'pointer', whiteSpace: 'nowrap', letterSpacing: '0.04em',
            }}>{t}</button>
          ))}
        </nav>
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          {tab === 'Overview'          && <Overview symbol={symbol} start={start} end={end} />}
          {tab === 'Options Chain'     && <OptionsChain symbol={symbol} date={end} />}
          {tab === 'Expiry Analysis'   && <ExpiryAnalysis symbol={symbol} date={end} />}
          {tab === 'Unusual Activity'  && <UnusualActivity symbol={symbol} />}
        </div>
      </div>
    </div>
  )
}
