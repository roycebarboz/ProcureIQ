import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import RiskGauge from '../components/RiskGauge'
import PolicyHitList from '../components/PolicyHitList'
import MarketSignalList from '../components/MarketSignalList'

interface PolicyHit {
  chunk_text: string
  score: number
  source_doc: string
  risk_category: string
}

interface MarketSignal {
  source: string
  content: string
  retrieved_at: string
  confidence: number
}

interface AssessmentResult {
  request_id: string
  vendor_name: string
  risk_score: number
  confidence: number
  recommendation: 'Approve' | 'Escalate' | 'Reject' | 'Pending'
  risk_brief: string
  policy_hits: PolicyHit[]
  market_data: MarketSignal[]
  contract_flags: string[]
  errors: Array<{ node: string; reason: string; fallback_used: boolean }>
  partial_output: boolean
}

const BADGE = {
  Approve: 'bg-green-100 text-green-800',
  Escalate: 'bg-amber-100 text-amber-800',
  Reject:   'bg-red-100 text-red-800',
  Pending:  'bg-gray-100 text-gray-700',
}

export default function RiskBrief() {
  const { requestId } = useParams<{ requestId: string }>()
  const [result, setResult] = useState<AssessmentResult | null>(null)

  useEffect(() => {
    if (!requestId) return
    fetch(`/assess/${requestId}/result`)
      .then(r => r.json())
      .then(setResult)
  }, [requestId])

  if (!result) {
    return (
      <main className="min-h-screen flex items-center justify-center text-gray-400">
        Loading…
      </main>
    )
  }

  const confidencePct = Math.round(result.confidence * 100)
  const badgeClass = BADGE[result.recommendation] ?? BADGE.Pending

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto space-y-8">

        {result.partial_output && (
          <div role="alert" className="bg-amber-50 border border-amber-300 rounded-md px-4 py-3 text-sm text-amber-800">
            ⚠ This assessment is based on partial data — one or more agents degraded during processing.
          </div>
        )}

        <header>
          <h1 className="text-2xl font-bold text-gray-900">{result.vendor_name}</h1>
          <p className="text-sm text-gray-500 mt-1">Request ID: {result.request_id}</p>
        </header>

        <div className="bg-white border border-gray-200 rounded-xl p-6 flex flex-wrap gap-8 items-center">
          <RiskGauge score={result.risk_score} />

          <div className="space-y-3">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Recommendation</p>
              <span className={`inline-block mt-1 px-3 py-1 rounded-full text-sm font-semibold ${badgeClass}`}>
                {result.recommendation}
              </span>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Confidence</p>
              <p className="text-lg font-bold text-gray-800">{confidencePct}% confidence</p>
            </div>
          </div>
        </div>

        <section className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Risk narrative</h2>
          <p className="text-gray-800 text-sm leading-relaxed whitespace-pre-wrap">{result.risk_brief}</p>
        </section>

        <section className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <PolicyHitList hits={result.policy_hits} />
          <hr className="border-gray-100" />
          <MarketSignalList signals={result.market_data} />
        </section>

      </div>
    </main>
  )
}
