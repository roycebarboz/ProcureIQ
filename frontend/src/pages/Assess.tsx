import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import RiskDonut from '../components/RiskDonut'
import { apiUrl } from '../lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

type CardStatus = 'pending' | 'loading' | 'complete'

interface CardState {
  status: CardStatus
  detail?: string
  warning?: string
}

interface Cards {
  scout: CardState
  librarian: CardState
  synthesizer: CardState
}

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

interface Brief {
  request_id: string
  vendor_name?: string
  risk_score: number
  confidence: number
  recommendation: 'Approve' | 'Escalate' | 'Reject' | 'Pending'
  risk_brief: string
  policy_hits?: PolicyHit[]
  market_data?: MarketSignal[]
  partial_output?: boolean
}

interface RecentVendor {
  request_id: string
  vendor_name: string
  recommendation: string
  confidence: number
}

const INITIAL_CARDS: Cards = {
  scout: { status: 'pending' },
  librarian: { status: 'pending' },
  synthesizer: { status: 'pending' },
}

// Per-agent model + telemetry shown in the pipeline (illustrative metadata).
const AGENT_META = {
  scout: { name: 'Market Scout', model: 'GPT-4o', time: '1.2s', tokens: 850 },
  librarian: { name: 'Policy Librarian', model: 'GPT-4o', time: '0.8s', tokens: 420 },
  synthesizer: { name: 'Risk Synthesizer', model: 'GPT-4o', time: '2.1s', tokens: 1200 },
}

const DECISION_BADGE: Record<string, string> = {
  Approve: 'bg-emerald-500 text-white',
  Escalate: 'bg-amber-500 text-white',
  Reject: 'bg-red-500 text-white',
  Pending: 'bg-gray-300 text-gray-700',
}

// ── Icons ─────────────────────────────────────────────────────────────────────

const NetworkIcon = (p: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" className={p.className}>
    <circle cx="5" cy="6" r="2" /><circle cx="5" cy="18" r="2" /><circle cx="19" cy="12" r="2" />
    <path d="M7 6.7 17 11M7 17.3 17 13" />
  </svg>
)

const SignalIcon = (p: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" className={p.className}>
    <path d="M2 12a10 10 0 0 1 10-10M5 12a7 7 0 0 1 7-7" /><circle cx="6" cy="18" r="1.5" />
  </svg>
)

const PolicyIcon = (p: { className?: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round" className={p.className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6M9 13l2 2 4-4" />
  </svg>
)

const Chevron = (p: { open: boolean }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round"
    className={`w-4 h-4 transition-transform ${p.open ? 'rotate-180' : ''}`}>
    <path d="m6 9 6 6 6-6" />
  </svg>
)

// ── Pipeline card ─────────────────────────────────────────────────────────────

function PipelineCard({
  meta, state, kind, active,
}: {
  meta: { name: string; model: string; time: string; tokens: number }
  state: CardState
  kind: 'scout' | 'librarian' | 'synthesizer'
  active: boolean
}) {
  const dotColor =
    state.status === 'complete' ? 'bg-emerald-500'
      : state.status === 'loading' ? 'bg-emerald-500'
        : 'bg-gray-300'

  return (
    <div className="relative pl-8">
      {/* timeline dot */}
      <span className={`absolute left-0 top-5 w-3 h-3 rounded-full ${dotColor}`} />
      <div
        className={`rounded-xl border bg-white p-5 ${
          active ? 'border-gray-900 shadow-md' : 'border-gray-200'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{meta.name}</h3>
            <span className="rounded bg-gray-900 px-2 py-0.5 text-[11px] font-medium text-white">
              {meta.model}
            </span>
          </div>
          <span className="whitespace-nowrap text-xs text-gray-500">
            {meta.time} &nbsp;|&nbsp; {meta.tokens} tokens
          </span>
        </div>

        {/* detail chip */}
        {state.detail && (
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
            {kind === 'librarian'
              ? <PolicyIcon className="w-3.5 h-3.5" />
              : <SignalIcon className="w-3.5 h-3.5" />}
            {state.detail}
          </div>
        )}

        {/* synthesizer progress bar */}
        {kind === 'synthesizer' && state.status === 'loading' && (
          <div className="mt-3 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-200">
              <div className="h-full w-2/3 animate-pulse rounded-full bg-gray-900" />
            </div>
            <span className="text-[11px] font-medium tracking-wide text-gray-500">
              SYNTHESIZING…
            </span>
          </div>
        )}

        {/* degradation warning */}
        {state.warning && (
          <div className="mt-3 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-600">
            ⚠ Partial data — {state.warning}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Collapsible brief section ─────────────────────────────────────────────────

function Collapsible({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-t border-gray-100 pt-3">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between text-sm font-semibold tracking-wide text-gray-700 hover:text-gray-900"
      >
        <span>{title} ({count})</span>
        <Chevron open={open} />
      </button>
      {open && <div className="mt-3 space-y-2">{children}</div>}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Assess() {
  const [vendorName, setVendorName] = useState('')
  const [category, setCategory] = useState('Software')
  const [spendAmount, setSpendAmount] = useState('')
  const [running, setRunning] = useState(false)
  const [started, setStarted] = useState(false)
  const [cards, setCards] = useState<Cards>(INITIAL_CARDS)
  const [brief, setBrief] = useState<Brief | null>(null)
  const [requestId, setRequestId] = useState('')
  const [recent, setRecent] = useState<RecentVendor[]>([])

  useEffect(() => {
    fetch(apiUrl('/dashboard'))
      .then(r => r.json())
      .then(d => setRecent((d.recent_assessments ?? []).slice(0, 4)))
      .catch(() => {})
  }, [])

  function resetForm() {
    setVendorName('')
    setCategory('Software')
    setSpendAmount('')
    setStarted(false)
    setRunning(false)
    setCards(INITIAL_CARDS)
    setBrief(null)
    setRequestId('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setRunning(true)
    setStarted(true)
    setBrief(null)
    setCards({
      scout: { status: 'loading' },
      librarian: { status: 'pending' },
      synthesizer: { status: 'pending' },
    })

    const res = await fetch(apiUrl('/assess'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vendor_name: vendorName,
        category,
        spend_amount: spendAmount ? parseFloat(spendAmount) : null,
      }),
    })
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''
    let reqId = ''
    let assessmentComplete = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const rawLine of lines) {
        const line = rawLine.trim()
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          const data = JSON.parse(line.slice(5).trim())
          reqId = data.request_id
          setRequestId(reqId)

          if (currentEvent === 'scout_complete') {
            const scoutError = (data.errors as Array<{ node: string; reason: string }> | undefined)
              ?.find(e => e.node === 'market_scout')
            setCards(c => ({
              ...c,
              scout: {
                status: 'complete',
                detail: `${data.market_data?.length ?? 0} Signals Found`,
                warning: scoutError?.reason,
              },
              librarian: { status: 'loading' },
            }))
          } else if (currentEvent === 'librarian_complete') {
            const libError = (data.errors as Array<{ node: string; reason: string }> | undefined)
              ?.find(e => e.node === 'policy_librarian')
            setCards(c => ({
              ...c,
              librarian: {
                status: 'complete',
                detail: `${data.policy_hits?.length ?? 0} Policy Hits`,
                warning: libError?.reason,
              },
              synthesizer: { status: 'loading' },
            }))
          } else if (currentEvent === 'assessment_complete') {
            assessmentComplete = true
            setCards(c => ({
              ...c,
              synthesizer: {
                status: 'complete',
                detail: `${data.recommendation} · score ${data.risk_score}`,
              },
            }))
            setBrief({ vendor_name: vendorName, ...data })
            loadFullBrief(reqId, vendorName)
          }
          currentEvent = ''
        } else if (line === '' && currentEvent) {
          currentEvent = ''
        }
      }
    }

    if (!assessmentComplete && reqId) {
      await loadFullBrief(reqId, vendorName)
    }

    setRunning(false)
  }

  async function loadFullBrief(id: string, vendor: string) {
    const result = await fetch(apiUrl(`/assess/${id}/result`))
    if (result.ok) {
      const data = await result.json()
      setBrief({ vendor_name: vendor, ...data })
      setCards(c => ({
        ...c,
        synthesizer: {
          ...c.synthesizer,
          status: 'complete',
          detail: c.synthesizer.detail ?? `${data.recommendation} · score ${data.risk_score}`,
        },
      }))
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-8 py-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">ProcureIQ</h1>
          <p className="text-[11px] font-medium tracking-wider text-gray-500">
            VENDOR RISK &amp; PROCUREMENT INTELLIGENCE
          </p>
        </div>
        <div className="flex items-center gap-6">
          <Link to="/dashboard" className="text-sm font-medium text-blue-600 hover:underline">
            Repository
          </Link>
          <button
            type="button"
            onClick={resetForm}
            className="flex items-center gap-2 rounded-md bg-gray-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-gray-800"
          >
            <span className="text-lg leading-none">+</span> NEW ASSESSMENT
          </button>
        </div>
      </header>

      {/* Main grid */}
      <main className="flex-1 px-8 py-8">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 lg:grid-cols-[340px_1fr_380px]">

          {/* ── Left: Vendor Intake ── */}
          <div className="space-y-6">
            <section className="rounded-xl border border-gray-200 bg-white p-6">
              <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold">
                <NetworkIcon className="h-5 w-5 text-gray-700" /> Vendor Intake
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="vendor-name" className="mb-1.5 block text-xs font-semibold tracking-wide text-gray-500">
                    VENDOR NAME
                  </label>
                  <input
                    id="vendor-name"
                    required
                    value={vendorName}
                    onChange={e => setVendorName(e.target.value)}
                    placeholder="e.g. Databricks Inc."
                    className="w-full rounded-md border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>
                <div>
                  <label htmlFor="category" className="mb-1.5 block text-xs font-semibold tracking-wide text-gray-500">
                    CATEGORY
                  </label>
                  <select
                    id="category"
                    value={category}
                    onChange={e => setCategory(e.target.value)}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  >
                    <option value="Software">Software</option>
                    <option value="IT Services">IT Services</option>
                    <option value="Professional Services">Professional Services</option>
                    <option value="Hardware">Hardware</option>
                    <option value="Facilities">Facilities</option>
                    <option value="Logistics">Logistics</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="spend-amount" className="mb-1.5 block text-xs font-semibold tracking-wide text-gray-500">
                    SPEND AMOUNT ($)
                  </label>
                  <input
                    id="spend-amount"
                    type="number"
                    value={spendAmount}
                    onChange={e => setSpendAmount(e.target.value)}
                    placeholder="0.00"
                    className="w-full rounded-md border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>
                <button
                  type="submit"
                  disabled={running}
                  className="w-full rounded-md bg-gray-900 py-3 text-sm font-semibold tracking-wide text-white hover:bg-gray-800 disabled:opacity-50"
                >
                  {running ? 'ASSESSING…' : 'ASSESS VENDOR'}
                </button>
              </form>
            </section>

            {/* Recent vendors */}
            <div>
              <h3 className="mb-3 px-1 text-xs font-semibold tracking-wider text-gray-500">RECENT VENDORS</h3>
              <div className="space-y-3">
                {recent.length === 0 ? (
                  <p className="px-1 text-sm text-gray-400">No recent vendors</p>
                ) : recent.map(v => (
                  <Link
                    key={v.request_id}
                    to={`/brief/${v.request_id}`}
                    className="block rounded-xl border border-gray-200 bg-white p-4 hover:border-gray-300"
                  >
                    <p className="font-semibold text-gray-900">{v.vendor_name}</p>
                    <p className="text-xs text-gray-500">
                      {v.recommendation} · {Math.round(v.confidence * 100)}% confidence
                    </p>
                  </Link>
                ))}
              </div>
            </div>
          </div>

          {/* ── Middle: Intelligence Pipeline ── */}
          <section className="rounded-xl border border-gray-200 bg-white p-6">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-lg font-semibold">
                <NetworkIcon className="h-5 w-5 text-gray-700" /> Intelligence Pipeline
              </h2>
              {started && (
                <span className="rounded bg-gray-100 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-gray-600">
                  STREAMING ACTIVE
                </span>
              )}
            </div>

            {!started ? (
              <p className="py-16 text-center text-sm text-gray-400">
                Submit a vendor to start the intelligence pipeline.
              </p>
            ) : (
              <div className="relative space-y-5">
                {/* connecting line */}
                <span className="absolute left-1.5 top-4 bottom-4 w-px bg-gray-200" />
                <PipelineCard meta={AGENT_META.scout} state={cards.scout} kind="scout"
                  active={cards.scout.status === 'loading'} />
                <PipelineCard meta={AGENT_META.librarian} state={cards.librarian} kind="librarian"
                  active={cards.librarian.status === 'loading'} />
                <PipelineCard meta={AGENT_META.synthesizer} state={cards.synthesizer} kind="synthesizer"
                  active={cards.synthesizer.status === 'loading'} />
              </div>
            )}
          </section>

          {/* ── Right: Risk Assessment Brief ── */}
          <section className="rounded-xl border border-gray-200 bg-white p-6">
            <h2 className="mb-5 text-xs font-semibold tracking-wider text-gray-500">RISK ASSESSMENT BRIEF</h2>

            {!brief ? (
              <p className="py-16 text-center text-sm text-gray-400">
                The brief appears once synthesis completes.
              </p>
            ) : (
              <div className="space-y-5">
                {brief.partial_output && (
                  <div role="alert" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    ⚠ Based on partial data — one or more agents degraded.
                  </div>
                )}

                <div className="flex justify-center">
                  <RiskDonut score={brief.risk_score} />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-gray-200 p-4 text-center">
                    <p className="text-[11px] font-semibold tracking-wide text-gray-500">CONFIDENCE</p>
                    <p className="mt-1 text-lg font-bold">{brief.confidence.toFixed(2)}</p>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                      <div className="h-full rounded-full bg-blue-600"
                        style={{ width: `${Math.round(brief.confidence * 100)}%` }} />
                    </div>
                  </div>
                  <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 p-4 text-center">
                    <p className="text-[11px] font-semibold tracking-wide text-gray-500">DECISION</p>
                    <span className={`mt-2 rounded px-3 py-1 text-xs font-bold ${DECISION_BADGE[brief.recommendation] ?? DECISION_BADGE.Pending}`}>
                      {brief.recommendation.toUpperCase()}
                    </span>
                  </div>
                </div>

                <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                  {brief.risk_brief}
                </p>

                <Collapsible title="MARKET SIGNALS" count={brief.market_data?.length ?? 0}>
                  {(brief.market_data ?? []).map((s, i) => (
                    <div key={i} className="rounded-md border border-gray-100 p-3 text-sm">
                      <p className="text-gray-800">{s.content}</p>
                      <div className="mt-1 flex gap-3 text-xs text-gray-500">
                        <span>{s.source}</span>
                        <span>confidence {(s.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  ))}
                </Collapsible>

                <Collapsible title="POLICY HITS" count={brief.policy_hits?.length ?? 0}>
                  {(brief.policy_hits ?? []).map((h, i) => (
                    <div key={i} className="rounded-md border border-gray-100 p-3 text-sm">
                      <p className="text-gray-800">{h.chunk_text}</p>
                      <div className="mt-1 flex gap-3 text-xs text-gray-500">
                        <span>{h.source_doc}</span>
                        <span>{h.risk_category}</span>
                        <span>score {h.score.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </Collapsible>
              </div>
            )}
          </section>

        </div>
      </main>

      {/* Footer */}
      <footer className="flex items-center justify-between border-t border-gray-200 bg-white px-8 py-3 text-xs text-gray-500">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
          <span className="font-semibold text-gray-700">ProcureIQ Intelligence Systems</span>
          <span>Request ID: {requestId || '—'}</span>
          <span>Tokens: {brief ? '4,102' : '—'}</span>
          <span>Latency: {brief ? '1.2s' : '—'}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          <span className="font-medium tracking-wide text-gray-600">SYSTEM HEALTHY</span>
        </div>
      </footer>
    </div>
  )
}
