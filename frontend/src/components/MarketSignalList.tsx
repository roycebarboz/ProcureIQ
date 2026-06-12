import { useState } from 'react'

interface MarketSignal {
  source: string
  content: string
  retrieved_at: string
  confidence: number
}

interface MarketSignalListProps {
  signals: MarketSignal[]
}

export default function MarketSignalList({ signals }: MarketSignalListProps) {
  const [open, setOpen] = useState(false)

  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900"
      >
        <span>{open ? '▾' : '▸'}</span>
        Market signals ({signals.length})
      </button>

      {open && (
        <ul className="mt-2 space-y-3">
          {signals.map((s, i) => (
            <li key={i} className="border border-gray-100 rounded-md p-3 text-sm bg-white">
              <p className="text-gray-800">{s.content}</p>
              <div className="flex gap-3 mt-1 text-xs text-gray-500">
                <span>{s.source}</span>
                <span>confidence {(s.confidence * 100).toFixed(0)}%</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
