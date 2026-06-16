import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { DailySummary } from '../types'

function fmt(n: number) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(n)
}

interface Props { data: DailySummary[] }

export default function VolumeChart({ data }: Props) {
  const pts = data.map(d => ({
    date: d.collect_date.slice(5),
    call: d.total_call_volume,
    put: d.total_put_volume,
  }))

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={pts} margin={{ top: 10, right: 16, bottom: 4, left: 40 }} barSize={14}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={fmt} tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg3)', border: '1px solid var(--border2)', borderRadius: 6, fontSize: 11 }}
          labelStyle={{ color: 'var(--muted2)' }}
          formatter={(v: number) => [fmt(v)]}
        />
        <Legend iconType="rect" iconSize={8} wrapperStyle={{ fontSize: 10, color: '#9ca3af' }} />
        <Bar dataKey="call" name="Call" stackId="a" fill="rgba(0,196,140,0.7)" radius={[0, 0, 2, 2]} />
        <Bar dataKey="put"  name="Put"  stackId="a" fill="rgba(255,77,109,0.7)"  radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
