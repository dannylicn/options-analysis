import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { ExpirySummary } from '../types'

function fmt(n: number) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(n)
}

interface Props { data: ExpirySummary[] }

export default function ExpiryBarChart({ data }: Props) {
  const pts = data.map(d => ({
    exp: d.expiry.slice(5),
    call: d.call_oi,
    put: d.put_oi,
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={pts} margin={{ top: 16, right: 20, bottom: 4, left: 50 }} barSize={20}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="exp" tick={{ fill: '#9ca3af', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={fmt} tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg3)', border: '1px solid var(--border2)', borderRadius: 6, fontSize: 11 }}
          labelStyle={{ color: 'var(--muted2)' }}
          formatter={(v: number) => [fmt(v)]}
        />
        <Legend iconType="rect" iconSize={8} wrapperStyle={{ fontSize: 10, color: '#9ca3af' }} />
        <Bar dataKey="put"  name="Put OI"  stackId="a" fill="rgba(255,77,109,0.7)"  radius={[0, 0, 2, 2]} />
        <Bar dataKey="call" name="Call OI" stackId="a" fill="rgba(0,196,140,0.7)" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
