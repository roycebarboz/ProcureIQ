interface RiskGaugeProps {
  score: number // 1–10
}

const SEGMENT_COLOURS = [
  'bg-green-400',   // 1
  'bg-green-400',   // 2
  'bg-green-500',   // 3
  'bg-yellow-400',  // 4
  'bg-yellow-500',  // 5
  'bg-orange-400',  // 6
  'bg-orange-500',  // 7
  'bg-red-400',     // 8
  'bg-red-500',     // 9
  'bg-red-700',     // 10
]

export default function RiskGauge({ score }: RiskGaugeProps) {
  const idx = Math.min(Math.max(Math.round(score) - 1, 0), 9)
  const colour = SEGMENT_COLOURS[idx]

  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`w-20 h-20 rounded-full flex items-center justify-center text-3xl font-bold text-white ${colour}`}
        aria-label={`Risk score ${score}`}
      >
        {score}
      </div>
      <div className="flex gap-0.5 mt-1">
        {SEGMENT_COLOURS.map((c, i) => (
          <div
            key={i}
            className={`h-2 w-4 rounded-sm ${c} ${i === idx ? 'ring-2 ring-gray-700' : 'opacity-40'}`}
          />
        ))}
      </div>
      <p className="text-xs text-gray-500">Risk score / 10</p>
    </div>
  )
}
