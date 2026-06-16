import type { MoneynessData } from '../types'

function fmt(n: number) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return String(n)
}

function Bar({ label, val, total, color }: { label: string; val: number; total: number; color: string }) {
  const pct = total > 0 ? (val / total * 100).toFixed(1) : '0.0'
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--muted2)' }}>{label}</span>
        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
          {fmt(val)} <span style={{ color }}>{pct}%</span>
        </span>
      </div>
      <div style={{ background: 'var(--bg3)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.4s ease' }} />
      </div>
    </div>
  )
}

interface Props { data: MoneynessData }

export default function MoneynessChart({ data }: Props) {
  const call = data.call ?? { itm: 0, atm: 0, otm: 0 }
  const put  = data.put  ?? { itm: 0, atm: 0, otm: 0 }
  const totalCall = call.itm + call.atm + call.otm
  const totalPut  = put.itm + put.atm + put.otm

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>PUTS</div>
        <Bar label="OTM Puts (new bearish bets)"  val={put.otm}  total={totalPut}  color="#ff4d6d" />
        <Bar label="ATM Puts (near money)"         val={put.atm}  total={totalPut}  color="#f5c542" />
        <Bar label="ITM Puts (legacy positions)"   val={put.itm}  total={totalPut}  color="rgba(255,77,109,0.3)" />
      </div>
      <div>
        <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>CALLS</div>
        <Bar label="OTM Calls (new bullish bets)"  val={call.otm} total={totalCall} color="#00c48c" />
        <Bar label="ATM Calls (near money)"         val={call.atm} total={totalCall} color="#4d9fff" />
        <Bar label="ITM Calls (already profitable)" val={call.itm} total={totalCall} color="rgba(0,196,140,0.3)" />
      </div>
    </div>
  )
}
