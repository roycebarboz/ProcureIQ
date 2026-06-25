interface RiskDonutProps {
  score: number // 1–10
}

function band(score: number): { label: string; color: string } {
  if (score <= 3) return { label: 'LOW RISK', color: '#10b981' }    // emerald-500
  if (score <= 6) return { label: 'MEDIUM RISK', color: '#f59e0b' } // amber-500
  return { label: 'HIGH RISK', color: '#ef4444' }                   // red-500
}

export default function RiskDonut({ score }: RiskDonutProps) {
  const { label, color } = band(score)
  const pct = Math.min(Math.max(score, 0), 10) / 10

  const size = 160
  const stroke = 14
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct)

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="#e5e7eb" strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-4xl font-bold text-gray-900" aria-label={`Risk score ${score}`}>{score}</span>
        <span className="text-xs font-medium tracking-wide text-gray-500 mt-1">{label}</span>
      </div>
    </div>
  )
}
