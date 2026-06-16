import { useEffect, useState } from 'react'
import { api } from '../api'
import type { UnusualActivity } from '../types'

const TYPE_MAP: Record<string, [string, string]> = {
  volume_spike:     ['VOLUME', 'rgba(77,159,255,0.15)'],
  oi_spike:         ['OI',     'rgba(245,197,66,0.15)'],
  iv_spike:         ['IV',     'rgba(0,196,140,0.15)'],
  pc_ratio_extreme: ['P/C',    'rgba(255,77,109,0.15)'],
}
const TYPE_COLOR: Record<string, string> = {
  volume_spike: 'var(--blue)', oi_spike: 'var(--yellow)',
  iv_spike: 'var(--green)', pc_ratio_extreme: 'var(--red)',
}

function fmt(n: number | null) {
  if (n == null) return '—'
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(Math.round(n))
}

interface Props { symbol: string }

export default function UnusualActivityTab({ symbol }: Props) {
  const [data, setData] = useState<UnusualActivity[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(14)

  useEffect(() => {
    setLoading(true)
    api.unusual(symbol, days).then(setData).finally(() => setLoading(false))
  }, [symbol, days])

  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px' }}>
      <div style={{
        fontFamily: 'var(--font-head)', fontSize: 12, fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase', color: 'var(--muted2)', marginBottom: 16,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        Unusual Options Activity
        <div style={{ display: 'flex', gap: 6 }}>
          {[7, 14, 30].map(d => (
            <button key={d} onClick={() => setDays(d)} style={{
              padding: '3px 10px', borderRadius: 4, fontSize: 10, cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              background: days === d ? 'rgba(77,159,255,0.15)' : 'var(--bg3)',
              border: `1px solid ${days === d ? 'rgba(77,159,255,0.5)' : 'var(--border2)'}`,
              color: days === d ? 'var(--blue)' : 'var(--muted2)',
            }}>{d}d</button>
          ))}
        </div>
      </div>

      {loading
        ? <div className="loading">Loading…</div>
        : data.length === 0
          ? <div className="empty">No unusual activity in the last {days} days</div>
          : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Date', 'Type', 'Side', 'Strike', 'Expiry', 'Value', 'Prev', 'Δ%', 'Description'].map(h => (
                    <th key={h} style={{
                      fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase',
                      color: 'var(--muted)', fontWeight: 600, padding: '8px 12px',
                      textAlign: 'left', borderBottom: '1px solid var(--border)',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((r, i) => {
                  const [label, bg] = TYPE_MAP[r.alert_type] ?? ['?', 'var(--bg3)']
                  const clr = TYPE_COLOR[r.alert_type] ?? 'var(--text)'
                  const chgClr = (r.change_pct ?? 0) > 200 ? '#ff4d6d' : (r.change_pct ?? 0) > 50 ? '#f5c542' : '#00c48c'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 12px', color: 'var(--muted2)', fontSize: 12 }}>{r.detect_date}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', background: bg, color: clr }}>{label}</span>
                      </td>
                      <td style={{ padding: '10px 12px', fontWeight: 600, color: r.side === 'call' ? 'var(--green)' : 'var(--red)', fontSize: 12 }}>
                        {r.side?.toUpperCase() ?? '—'}
                      </td>
                      <td style={{ padding: '10px 12px', fontSize: 12 }}>{r.strike != null ? `$${r.strike.toFixed(1)}` : '—'}</td>
                      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--muted2)' }}>{r.expiry?.slice(5) ?? '—'}</td>
                      <td style={{ padding: '10px 12px', fontSize: 12 }}>{fmt(r.current_value)}</td>
                      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--muted)' }}>{fmt(r.previous_value)}</td>
                      <td style={{ padding: '10px 12px', fontSize: 12, fontWeight: 600, color: chgClr }}>
                        {r.change_pct != null ? `+${r.change_pct.toFixed(0)}%` : '—'}
                      </td>
                      <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--muted2)', maxWidth: 240 }}>{r.description ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
    </div>
  )
}
