import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ExpirySummary } from '../types'
import ExpiryBarChart from '../charts/ExpiryBarChart'
import ExpiryRatioChart from '../charts/ExpiryRatioChart'

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

export default function ExpiryAnalysis({ symbol, date }: Props) {
  const [data, setData] = useState<ExpirySummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.expiry(symbol, date).then(setData).finally(() => setLoading(false))
  }, [symbol, date])

  if (loading) return <div className="loading">Loading…</div>

  return (
    <div>
      <Card title="Call vs Put OI by Expiry" badge="All Expirations">
        {data.length ? <ExpiryBarChart data={data} /> : <div className="empty">No data</div>}
      </Card>
      <Card title="P/C OI Ratio by Expiry" badge="Below 1 = Call Heavy">
        {data.length ? <ExpiryRatioChart data={data} /> : <div className="empty">No data</div>}
      </Card>
    </div>
  )
}
