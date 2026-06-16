import { XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Area, AreaChart, ResponsiveContainer } from 'recharts'
import type { ExpirySummary } from '../types'

interface Props { data: ExpirySummary[] }

export default function ExpiryRatioChart({ data }: Props) {
  const pts = data.map(d => ({
    exp: d.expiry.slice(5),
    ratio: d.oi_pc_ratio,
  }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={pts} margin={{ top: 16, right: 20, bottom: 4, left: 50 }}>
        <defs>
          <linearGradient id="ratioGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4d9fff" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#4d9fff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="exp" tick={{ fill: '#9ca3af', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 'auto']} ticks={[0, 1, 2, 3]}
          tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg3)', border: '1px solid var(--border2)', borderRadius: 6, fontSize: 11 }}
          labelStyle={{ color: 'var(--muted2)' }}
          formatter={(v: number) => [v?.toFixed(2), 'P/C OI Ratio']}
        />
        <ReferenceLine y={1} stroke="rgba(77,159,255,0.4)" strokeDasharray="4 3" label={{ value: '1.0', fill: 'rgba(77,159,255,0.6)', fontSize: 9, position: 'right' }} />
        <Area type="monotone" dataKey="ratio" stroke="#4d9fff" strokeWidth={2.5} fill="url(#ratioGrad)"
          dot={({ cx, cy, payload }) => {
            const v = payload.ratio ?? 0
            const fill = v < 1 ? '#00c48c' : v > 2 ? '#ff4d6d' : '#f5c542'
            return <circle key={cx} cx={cx} cy={cy} r={4} fill={fill} stroke="var(--bg2)" strokeWidth={1.5} />
          }}
          connectNulls
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
