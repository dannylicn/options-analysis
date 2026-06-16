import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import type { DailySummary } from '../types'

interface Props { data: DailySummary[] }

export default function PCRatioChart({ data }: Props) {
  const pts = data.map(d => ({
    date: d.collect_date.slice(5),
    value: d.oi_pc_ratio != null ? Math.min(d.oi_pc_ratio, 12) : null,
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={pts} margin={{ top: 16, right: 16, bottom: 4, left: 36 }}>
        <defs>
          <linearGradient id="pcGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ff4d6d" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#ff4d6d" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 12]} ticks={[0, 3, 6, 9, 12]} tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg3)', border: '1px solid var(--border2)', borderRadius: 6, fontSize: 11 }}
          labelStyle={{ color: 'var(--muted2)' }}
          itemStyle={{ color: '#ff4d6d' }}
          formatter={(v: number) => [v?.toFixed(2), 'P/C OI']}
        />
        <ReferenceLine y={1} stroke="rgba(77,159,255,0.4)" strokeDasharray="4 3" label={{ value: 'pc=1', fill: 'rgba(77,159,255,0.7)', fontSize: 9, position: 'right' }} />
        <Area type="monotone" dataKey="value" stroke="#ff4d6d" strokeWidth={2} fill="url(#pcGrad)" dot={{ fill: '#ff4d6d', r: 3 }} connectNulls />
      </AreaChart>
    </ResponsiveContainer>
  )
}
