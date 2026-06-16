import type { ChainSnapshot } from '../types'

function fmt(n: number) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(n)
}

interface Props { data: ChainSnapshot[]; expiry?: string }

export default function ButterflyChart({ data, expiry }: Props) {
  const filtered = expiry ? data.filter(d => d.expiry === expiry) : data

  const byStrike = new Map<number, { call: number; put: number }>()
  filtered.forEach(d => {
    if (!byStrike.has(d.strike)) byStrike.set(d.strike, { call: 0, put: 0 })
    const s = byStrike.get(d.strike)!
    if (d.side === 'call') s.call += d.open_interest
    else s.put += d.open_interest
  })

  const pts = [...byStrike.entries()]
    .sort(([a], [b]) => a - b)
    .map(([strike, v]) => ({ strike, ...v }))

  if (!pts.length) return <div className="empty">No data</div>

  const maxOI = Math.max(...pts.map(p => Math.max(p.call, p.put)), 1)
  const W = 800, H = 240
  const pad = { t: 16, b: 28, l: 200, r: 200 }
  const iW = W - pad.l - pad.r
  const iH = H - pad.t - pad.b
  const rowH = iH / pts.length
  const bH = rowH * 0.65
  const mid = W / 2

  let svg = ''
  svg += `<line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${H - pad.b}" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>`
  svg += `<line x1="${W - pad.r}" y1="${pad.t}" x2="${W - pad.r}" y2="${H - pad.b}" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>`
  svg += `<line x1="${mid}" y1="${pad.t}" x2="${mid}" y2="${H - pad.b}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`

  pts.forEach((p, i) => {
    const y = pad.t + i * rowH + (rowH - bH) / 2
    svg += `<text x="${mid}" y="${y + bH / 2 + 4}" fill="var(--text)" font-size="11" font-weight="600" text-anchor="middle" font-family="JetBrains Mono">$${p.strike}</text>`
    const cW = p.call / maxOI * (iW / 2 - 30)
    svg += `<rect x="${mid + 14}" y="${y}" width="${cW}" height="${bH}" fill="rgba(0,196,140,0.75)" rx="2"/>`
    svg += `<text x="${mid + 14 + cW + 5}" y="${y + bH / 2 + 4}" fill="#00c48c" font-size="10" font-family="JetBrains Mono">${fmt(p.call)}</text>`
    const pW = p.put / maxOI * (iW / 2 - 30)
    svg += `<rect x="${mid - 14 - pW}" y="${y}" width="${pW}" height="${bH}" fill="rgba(255,77,109,0.75)" rx="2"/>`
    svg += `<text x="${mid - 14 - pW - 5}" y="${y + bH / 2 + 4}" fill="#ff4d6d" font-size="10" text-anchor="end" font-family="JetBrains Mono">${fmt(p.put)}</text>`
  })

  svg += `<text x="${mid - 80}" y="${H - 4}" fill="#6b7280" font-size="10" text-anchor="middle" font-family="JetBrains Mono">← Put OI</text>`
  svg += `<text x="${mid + 80}" y="${H - 4}" fill="#6b7280" font-size="10" text-anchor="middle" font-family="JetBrains Mono">Call OI →</text>`

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} dangerouslySetInnerHTML={{ __html: svg }} />
  )
}
