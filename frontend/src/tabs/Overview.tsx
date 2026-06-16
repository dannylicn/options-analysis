import { useEffect, useState } from 'react'
import { api } from '../api'
import type { DailySummary, ExpirySummary, MoneynessData } from '../types'
import PCRatioChart from '../charts/PCRatioChart'
import IVSkewChart from '../charts/IVSkewChart'
import VolumeChart from '../charts/VolumeChart'
import MoneynessChart from '../charts/MoneynessChart'

function Card({ title, badge, children }: { title: string; badge?: string; children: React.ReactNode }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px' }}>
      <div style={{
        fontFamily: 'var(--font-head)', fontSize: 12, fontWeight: 700,
        letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--muted2)',
        marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {title}
        {badge && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 400, padding: '2px 8px', borderRadius: 20, background: 'var(--bg3)', color: 'var(--muted2)' }}>{badge}</span>}
      </div>
      {children}
    </div>
  )
}

interface Props { symbol: string; start: string; end: string }

export default function Overview({ symbol, start, end }: Props) {
  const [summary, setSummary] = useState<DailySummary[]>([])
  const [expiry, setExpiry] = useState<ExpirySummary[]>([])
  const [moneyness, setMoneyness] = useState<MoneynessData>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.summary(symbol, start, end),
      api.expiry(symbol, end),
      api.moneyness(symbol, end),
    ]).then(([s, e, m]) => {
      setSummary(s)
      setExpiry(e)
      setMoneyness(m)
    }).finally(() => setLoading(false))
  }, [symbol, start, end])

  if (loading) return <div className="loading">Loading…</div>

  const badge = summary.length > 0
    ? `${summary[0].collect_date.slice(5)} – ${summary[summary.length - 1].collect_date.slice(5)}`
    : undefined

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <Card title="P/C Ratio — Daily OI" badge={badge}>
          {summary.length ? <PCRatioChart data={summary} /> : <div className="empty">No data</div>}
        </Card>
        <Card title="IV Skew — Call vs Put" badge="Avg by Expiry">
          {expiry.length ? <IVSkewChart data={expiry} /> : <div className="empty">No data</div>}
        </Card>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <Card title="Daily Volume" badge="Call / Put">
          {summary.length ? <VolumeChart data={summary} /> : <div className="empty">No data</div>}
        </Card>
        <Card title="OI Breakdown by Moneyness">
          <MoneynessChart data={moneyness} />
        </Card>
      </div>
    </div>
  )
}
