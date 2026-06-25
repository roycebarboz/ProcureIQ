import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiUrl } from '../lib/api'

interface RecentAssessment {
  request_id: string
  vendor_name: string
  recommendation: string
  confidence: number
  timestamp: string
}

interface DashboardData {
  node_latency: Record<string, number>
  partial_rate: number
  recommendation_dist: { Approve: number; Escalate: number; Reject: number; Pending: number }
  recent_assessments: RecentAssessment[]
}

const REC_COLORS: Record<string, string> = {
  Approve: 'bg-green-500',
  Escalate: 'bg-amber-500',
  Reject:   'bg-red-500',
  Pending:  'bg-gray-400',
}

const REC_BADGE: Record<string, string> = {
  Approve: 'bg-green-100 text-green-800',
  Escalate: 'bg-amber-100 text-amber-800',
  Reject:   'bg-red-100 text-red-800',
  Pending:  'bg-gray-100 text-gray-700',
}

function formatNodeName(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatTimestamp(iso: string): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)

  useEffect(() => {
    fetch(apiUrl('/dashboard')).then(r => r.json()).then(setData)
  }, [])

  if (!data) {
    return (
      <main className="min-h-screen flex items-center justify-center text-gray-400">
        Loading…
      </main>
    )
  }

  const { node_latency, partial_rate, recommendation_dist, recent_assessments } = data
  const latencyEntries = Object.entries(node_latency)
  const maxLatency = Math.max(...latencyEntries.map(([, v]) => v), 1)
  const totalRec = Object.values(recommendation_dist).reduce((s, n) => s + n, 0)

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-5xl mx-auto space-y-8">

        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <Link to="/" className="text-sm text-blue-600 hover:underline">← New assessment</Link>
        </header>

        {/* Row 1: Node Latency + Partial Rate */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

          {/* Node Latency */}
          <section className="md:col-span-2 bg-white border border-gray-200 rounded-xl p-6">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Node Latency</h2>
            {latencyEntries.length === 0 ? (
              <p className="text-sm text-gray-400">No data yet</p>
            ) : (
              <div className="space-y-3">
                {latencyEntries.map(([node, duration]) => (
                  <div key={node}>
                    <div className="flex justify-between text-xs text-gray-600 mb-1">
                      <span>{formatNodeName(node)}</span>
                      <span>{duration} ms</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className="bg-blue-500 h-3 rounded-full"
                        style={{ width: `${(duration / maxLatency) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Partial Rate */}
          <section className="bg-white border border-gray-200 rounded-xl p-6 flex flex-col items-center justify-center text-center">
            <h2 className="text-sm font-semibold text-gray-700 mb-2">Partial Assessment Rate</h2>
            <p className="text-5xl font-bold text-amber-500">{partial_rate}%</p>
            <p className="text-xs text-gray-400 mt-2">assessments with degraded data</p>
          </section>

        </div>

        {/* Row 2: Recommendation Distribution */}
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recommendation Distribution</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {(Object.entries(recommendation_dist) as [string, number][]).map(([rec, count]) => {
              const barPct = totalRec > 0 ? Math.round((count / totalRec) * 100) : 0
              return (
                <div key={rec} className="flex flex-col items-center space-y-2">
                  <div className="w-full bg-gray-100 rounded-lg overflow-hidden h-24 flex items-end">
                    <div
                      className={`w-full ${REC_COLORS[rec] ?? 'bg-gray-400'} transition-all`}
                      style={{ height: `${Math.max(barPct, 4)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-gray-700">{rec}</span>
                  <span
                    data-testid={`dist-count-${rec}`}
                    className={`text-lg font-bold px-2 py-0.5 rounded ${REC_BADGE[rec] ?? ''}`}
                  >
                    {count}
                  </span>
                </div>
              )
            })}
          </div>
        </section>

        {/* Row 3: Recent Assessments */}
        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent Assessments</h2>
          {recent_assessments.length === 0 ? (
            <p className="text-sm text-gray-400">No assessments yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
                    <th className="text-left py-2 pr-4">Vendor</th>
                    <th className="text-left py-2 pr-4">Recommendation</th>
                    <th className="text-left py-2 pr-4">Confidence</th>
                    <th className="text-left py-2">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {recent_assessments.map(a => (
                    <tr key={a.request_id} className="hover:bg-gray-50">
                      <td className="py-2 pr-4 font-medium text-blue-600">
                        <Link to={`/brief/${a.request_id}`}>{a.vendor_name}</Link>
                      </td>
                      <td className="py-2 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${REC_BADGE[a.recommendation] ?? ''}`}>
                          {a.recommendation}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-gray-700">
                        {Math.round(a.confidence * 100)}%
                      </td>
                      <td className="py-2 text-gray-400">{formatTimestamp(a.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

      </div>
    </main>
  )
}
