import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { ExpirySummary } from '../types'

interface Props { data: ExpirySummary[] }

export default function IVSkewChart({ data }: Props) {
  const pts = data.map(d => ({
    exp: d.expiry.slice(5),
    callIV: d.avg_call_iv,
    putIV: d.avg_put_iv,
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={pts} margin={{ top: 16, right: 16, bottom: 4, left: 36 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="exp" tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 200]} ticks={[0, 50, 100, 150, 200]}
          tickFormatter={v => `${v}%`}
          tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg3)', border: '1px solid var(--border2)', borderRadius: 6, fontSize: 11 }}
          labelStyle={{ color: 'var(--muted2)' }}
          formatter={(v: number) => [`${v?.toFixed(1)}%`]}
        />
        <Legend iconType="rect" iconSize={8} wrapperStyle={{ fontSize: 10, color: '#9ca3af' }} />
        <Line type="monotone" dataKey="callIV" name="Call IV" stroke="#00c48c" strokeWidth={2} dot={{ fill: '#00c48c', r: 3 }} connectNulls />
        <Line type="monotone" dataKey="putIV"  name="Put IV"  stroke="#ff4d6d" strokeWidth={2} strokeDasharray="5 3" dot={{ fill: '#ff4d6d', r: 3 }} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  )
}
