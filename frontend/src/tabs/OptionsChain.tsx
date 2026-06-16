import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ChainSnapshot } from '../types'
import OIHeatmap from '../charts/OIHeatmap'
import ButterflyChart from '../charts/ButterflyChart'

function Card({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px', marginBottom: 16 }}>
      <div style={{
        fontFamily: 'var(--font-head)', fontSize: 12, fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase', color: 'var(--muted2)', marginBottom: 16,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {title}
        {badge && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 400, padding: '2px 8px', borderRadius: 20, background: 'var(--bg3)', color: 'var(--muted2)' }}>{badge}</span>}
      </div>
      {children}
    </div>
  )
}

interface Props { symbol: string; date: string }

export default function OptionsChain({ symbol, date }: Props) {
  const [chain, setChain] = useState<ChainSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedExpiry, setSelectedExpiry] = useState<string>('')

  useEffect(() => {
    setLoading(true)
    api.chain(symbol, date)
      .then(data => {
        setChain(data)
        const expiries = [...new Set(data.map(d => d.expiry))].sort()
        setSelectedExpiry(expiries[0] ?? '')
      })
      .finally(() => setLoading(false))
  }, [symbol, date])

  if (loading) return <div className="loading">Loading…</div>

  const expiries = [...new Set(chain.map(d => d.expiry))].sort()

  return (
    <div>
      <Card title="OI Heatmap — Strike × Expiry" badge="Darker = Higher OI">
        {chain.length ? <OIHeatmap data={chain} /> : <div className="empty">No data</div>}
      </Card>
      <Card
        title="OI by Strike — Call vs Put"
        badge={selectedExpiry ? selectedExpiry.slice(5) : undefined}
      >
        <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {expiries.map(e => (
            <button key={e} onClick={() => setSelectedExpiry(e)} style={{
              padding: '4px 10px', borderRadius: 4, fontSize: 11, cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              background: selectedExpiry === e ? 'rgba(77,159,255,0.15)' : 'var(--bg3)',
              border: `1px solid ${selectedExpiry === e ? 'rgba(77,159,255,0.5)' : 'var(--border2)'}`,
              color: selectedExpiry === e ? 'var(--blue)' : 'var(--muted2)',
            }}>{e.slice(5)}</button>
          ))}
        </div>
        {chain.length
          ? <ButterflyChart data={chain} expiry={selectedExpiry} />
          : <div className="empty">No data</div>}
      </Card>
    </div>
  )
}
