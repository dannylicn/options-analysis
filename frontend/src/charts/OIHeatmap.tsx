import type { ChainSnapshot } from '../types'

function fmt(n: number) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(n)
}

function heatColor(val: number, max: number, side: string) {
  const r = Math.min(val / max, 1)
  if (side === 'call') {
    return `rgba(0,${Math.round(30 + r * 170)},${Math.round(30 + r * 100)},${(0.15 + r * 0.75).toFixed(2)})`
  }
  return `rgba(${Math.round(50 + r * 200)},${Math.round(10 + r * 30)},${Math.round(30 + r * 50)},${(0.15 + r * 0.75).toFixed(2)})`
}

interface Props { data: ChainSnapshot[] }

export default function OIHeatmap({ data }: Props) {
  if (!data.length) return <div className="empty">No data</div>

  const expiries = [...new Set(data.map(d => d.expiry))].sort()
  const strikes = [...new Set(data.map(d => d.strike))].sort((a, b) => a - b)

  const map = new Map<string, ChainSnapshot>()
  data.forEach(d => map.set(`${d.strike}|${d.expiry}|${d.side}`, d))

  const maxOI = Math.max(...data.map(d => d.open_interest), 1)

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'separate', borderSpacing: 3, fontSize: 10, fontFamily: 'var(--font-mono)' }}>
        <thead>
          <tr>
            <th style={{ color: 'var(--muted)', fontWeight: 500, padding: '4px 8px', textAlign: 'right' }}>Strike</th>
            {expiries.map(e => (
              <th key={e} colSpan={2} style={{ color: 'var(--muted)', fontWeight: 500, padding: '4px 8px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                {e.slice(5)}
              </th>
            ))}
          </tr>
          <tr>
            <th />
            {expiries.map(e => (
              <>
                <th key={`${e}-c`} style={{ color: '#00c48c', fontSize: 9, padding: '2px 4px', textAlign: 'center' }}>C</th>
                <th key={`${e}-p`} style={{ color: '#ff4d6d', fontSize: 9, padding: '2px 4px', textAlign: 'center' }}>P</th>
              </>
            ))}
          </tr>
        </thead>
        <tbody>
          {strikes.map(strike => (
            <tr key={strike}>
              <td style={{ color: 'var(--muted)', textAlign: 'right', paddingRight: 10, fontWeight: 500 }}>
                ${strike.toFixed(1)}
              </td>
              {expiries.map(exp => {
                const call = map.get(`${strike}|${exp}|call`)
                const put  = map.get(`${strike}|${exp}|put`)
                return (
                  <>
                    <td key={`${strike}|${exp}|c`} title={`Call OI: ${call?.open_interest ?? 0}`} style={{
                      width: 48, height: 28, borderRadius: 3, textAlign: 'center', verticalAlign: 'middle', fontWeight: 600,
                      cursor: 'pointer',
                      background: call ? heatColor(call.open_interest, maxOI, 'call') : 'rgba(255,255,255,0.02)',
                      color: call ? 'rgba(0,196,140,0.9)' : 'rgba(255,255,255,0.15)',
                    }}>
                      {call ? fmt(call.open_interest) : '—'}
                    </td>
                    <td key={`${strike}|${exp}|p`} title={`Put OI: ${put?.open_interest ?? 0}`} style={{
                      width: 48, height: 28, borderRadius: 3, textAlign: 'center', verticalAlign: 'middle', fontWeight: 600,
                      cursor: 'pointer',
                      background: put ? heatColor(put.open_interest, maxOI, 'put') : 'rgba(255,255,255,0.02)',
                      color: put ? 'rgba(255,77,109,0.9)' : 'rgba(255,255,255,0.15)',
                    }}>
                      {put ? fmt(put.open_interest) : '—'}
                    </td>
                  </>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 12, display: 'flex', gap: 20, fontSize: 10, color: 'var(--muted)' }}>
        <span><span style={{ color: 'var(--green)' }}>■</span> Call OI</span>
        <span><span style={{ color: 'var(--red)' }}>■</span> Put OI</span>
        <span>Darker = Higher OI</span>
      </div>
    </div>
  )
}
