import type { WatchlistItem, Sentiment, SentimentCard } from '../types'

interface Props {
  item?: WatchlistItem
  sentiment: Sentiment | null
}

function SCard({ card }: { card: SentimentCard | null }) {
  if (!card) return <div className="loading" style={{ flex: 1 }} />
  const colors: Record<string, string> = { red: '#ff4d6d', green: '#00c48c', yellow: '#f5c542' }
  const bgs: Record<string, string> = {
    red: 'rgba(255,77,109,0.06)', green: 'rgba(0,196,140,0.06)', yellow: 'rgba(245,197,66,0.06)',
  }
  const borders: Record<string, string> = {
    red: 'rgba(255,77,109,0.3)', green: 'rgba(0,196,140,0.3)', yellow: 'rgba(245,197,66,0.3)',
  }
  return (
    <div style={{
      flex: 1, background: bgs[card.cls], border: `1px solid ${borders[card.cls]}`,
      borderRadius: 8, padding: '10px 14px',
    }}>
      <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 5 }}>
        {card.cls === 'red' && card.label.includes('空') ? 'Pressure Sentiment'
          : card.label.includes('多') || card.label.includes('Normal') ? 'Flow Sentiment'
          : 'Legacy Flag'}
      </div>
      <div style={{ fontFamily: 'var(--font-head)', fontSize: 14, fontWeight: 700, color: colors[card.cls] }}>
        {card.label}
      </div>
      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3 }}>{card.val}</div>
    </div>
  )
}

export default function Header({ item, sentiment }: Props) {
  const up = (item?.stock_change_pct ?? 0) >= 0

  return (
    <div style={{
      background: 'var(--bg2)', borderBottom: '1px solid var(--border)',
      padding: '14px 24px', display: 'flex', alignItems: 'center', gap: 24, flexShrink: 0,
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 100 }}>
        <div style={{ fontFamily: 'var(--font-head)', fontSize: 22, fontWeight: 800, letterSpacing: '0.04em' }}>
          {item?.symbol ?? '—'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>{item?.name ?? ''}</div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.02em' }}>
          {item?.stock_price != null ? `$${item.stock_price.toFixed(2)}` : '—'}
        </div>
        <div style={{ fontSize: 12, fontWeight: 500, color: up ? 'var(--green)' : 'var(--red)' }}>
          {item?.stock_change_pct != null
            ? `${up ? '▲' : '▼'} ${Math.abs(item.stock_change_pct).toFixed(2)}% today`
            : ''}
        </div>
      </div>

      <div style={{ width: 1, height: 40, background: 'var(--border2)', flexShrink: 0 }} />

      <div style={{ display: 'flex', gap: 10, flex: 1 }}>
        <SCard card={sentiment?.pressure ?? null} />
        <SCard card={sentiment?.flow ?? null} />
        <SCard card={sentiment?.legacy ?? null} />
      </div>
    </div>
  )
}
