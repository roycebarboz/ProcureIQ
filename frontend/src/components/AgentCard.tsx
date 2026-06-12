export type AgentCardStatus = 'pending' | 'loading' | 'complete'

interface AgentCardProps {
  label: string
  status: AgentCardStatus
  detail?: string
  warning?: string
}

export default function AgentCard({ label, status, detail, warning }: AgentCardProps) {
  const icon =
    status === 'pending' ? '○' : status === 'loading' ? '◌' : '●'
  const statusClass =
    status === 'pending'
      ? 'text-gray-400'
      : status === 'loading'
        ? 'text-yellow-500 animate-pulse'
        : 'text-green-500'

  return (
    <div className="border border-gray-200 rounded-lg p-4 flex items-start gap-3 bg-white shadow-sm">
      <span className={`text-xl mt-0.5 ${statusClass}`}>{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-800">{label}</p>
        {detail && <p className="text-sm text-gray-500 mt-1 truncate">{detail}</p>}
        {warning && (
          <p className="text-sm text-amber-600 mt-1">⚠ Partial data — {warning}</p>
        )}
      </div>
    </div>
  )
}
