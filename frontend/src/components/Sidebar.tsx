import type { WatchlistItem } from '../types'

interface Props {
  watchlist: WatchlistItem[]
  symbol: string
  start: string
  end: string
  onSymbol: (s: string) => void
  onStart: (s: string) => void
  onEnd: (s: string) => void
}

export default function Sidebar({ watchlist, symbol, start, end, onSymbol, onStart, onEnd }: Props) {
  return (
    <aside style={{
      width: 200, minWidth: 200,
      background: 'var(--bg2)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      padding: '20px 0', gap: 4,
    }}>
      <div style={{
        fontFamily: 'var(--font-head)', fontSize: 16, fontWeight: 800,
        letterSpacing: '0.08em', padding: '0 18px 20px',
        borderBottom: '1px solid var(--border)', marginBottom: 8, color: 'var(--text)',
      }}>
        OPTIONS<span style={{ color: 'var(--blue)' }}>.</span>FLOW
      </div>

      <div style={{
        fontSize: 10, fontWeight: 600, letterSpacing: '0.14em',
        color: 'var(--muted)', padding: '12px 18px 6px', textTransform: 'uppercase',
      }}>Watchlist</div>

      {watchlist.map(item => {
        const active = item.symbol === symbol
        const up = (item.stock_change_pct ?? 0) >= 0
        return (
          <button key={item.symbol} onClick={() => onSymbol(item.symbol)} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '9px 18px', cursor: 'pointer',
            border: 'none', borderLeft: `2px solid ${active ? 'var(--blue)' : 'transparent'}`,
            background: active ? 'rgba(77,159,255,0.08)' : 'none',
            color: active ? 'var(--blue)' : 'var(--muted2)',
            fontFamily: 'var(--font-mono)', fontSize: 13, width: '100%', textAlign: 'left',
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
              background: active ? 'var(--blue)' : 'var(--muted)',
              boxShadow: active ? '0 0 6px var(--blue)' : 'none',
            }} />
            <span>
              <div style={{ fontWeight: 600 }}>{item.symbol}</div>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>{item.name}</div>
              {item.stock_price != null && (
                <div style={{ fontSize: 10, color: up ? 'var(--green)' : 'var(--red)', marginTop: 1 }}>
                  ${item.stock_price.toFixed(2)} {up ? '▲' : '▼'} {Math.abs(item.stock_change_pct ?? 0).toFixed(2)}%
                </div>
              )}
            </span>
          </button>
        )
      })}

      <div style={{ marginTop: 'auto', padding: '16px 18px 0', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
          Date Range
        </div>
        {[['From', start, onStart], ['To', end, onEnd]].map(([label, val, cb]) => (
          <input
            key={label as string}
            type="date"
            value={val as string}
            onChange={e => (cb as (s: string) => void)(e.target.value)}
            style={{
              width: '100%', background: 'var(--bg3)',
              border: '1px solid var(--border2)', borderRadius: 4,
              color: 'var(--text)', fontFamily: 'var(--font-mono)',
              fontSize: 11, padding: '7px 10px', outline: 'none', marginBottom: 6,
            }}
          />
        ))}
      </div>
    </aside>
  )
}
