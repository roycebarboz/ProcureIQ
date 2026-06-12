import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AgentCard from '../components/AgentCard'
import type { AgentCardStatus } from '../components/AgentCard'

interface CardState {
  status: AgentCardStatus
  detail?: string
  warning?: string
}

interface Cards {
  scout: CardState
  librarian: CardState
  synthesizer: CardState
}

const INITIAL_CARDS: Cards = {
  scout: { status: 'pending' },
  librarian: { status: 'pending' },
  synthesizer: { status: 'pending' },
}

export default function Assess() {
  const navigate = useNavigate()
  const [vendorName, setVendorName] = useState('')
  const [category, setCategory] = useState('')
  const [spendAmount, setSpendAmount] = useState('')
  const [running, setRunning] = useState(false)
  const [started, setStarted] = useState(false)
  const [cards, setCards] = useState<Cards>(INITIAL_CARDS)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setRunning(true)
    setStarted(true)
    setCards({
      scout: { status: 'loading' },
      librarian: { status: 'pending' },
      synthesizer: { status: 'pending' },
    })

    const res = await fetch('/assess', {
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
    let requestId = ''
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
          requestId = data.request_id

          if (currentEvent === 'scout_complete') {
            const scoutError = (data.errors as Array<{node:string;reason:string}>|undefined)
              ?.find(e => e.node === 'market_scout')
            setCards(c => ({
              ...c,
              scout: {
                status: 'complete',
                detail: `${data.market_data?.length ?? 0} signals`,
                warning: scoutError?.reason,
              },
              librarian: { status: 'loading' },
            }))
          } else if (currentEvent === 'librarian_complete') {
            const libError = (data.errors as Array<{node:string;reason:string}>|undefined)
              ?.find(e => e.node === 'policy_librarian')
            setCards(c => ({
              ...c,
              librarian: {
                status: 'complete',
                detail: `${data.policy_hits?.length ?? 0} policy hits`,
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
            navigate(`/brief/${requestId}`)
          }
          currentEvent = ''
        } else if (line === '' && currentEvent) {
          currentEvent = ''
        }
      }
    }

    if (!assessmentComplete && requestId) {
      const result = await fetch(`/assess/${requestId}/result`)
      if (result.ok) {
        const data = await result.json()
        setCards(c => ({
          ...c,
          synthesizer: {
            status: 'complete',
            detail: `${data.recommendation} · score ${data.risk_score}`,
          },
        }))
        navigate(`/brief/${requestId}`)
      }
    }

    setRunning(false)
  }

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center py-16 px-4">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Vendor Risk Assessment</h1>

      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-4 mb-10">
        <div>
          <label htmlFor="vendor-name" className="block text-sm font-medium text-gray-700 mb-1">
            Vendor name
          </label>
          <input
            id="vendor-name"
            required
            value={vendorName}
            onChange={e => setVendorName(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Acme Corp"
          />
        </div>
        <div>
          <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            id="category"
            required
            value={category}
            onChange={e => setCategory(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="" disabled>Select category…</option>
            <option value="IT Services">IT Services</option>
            <option value="Professional Services">Professional Services</option>
            <option value="Hardware">Hardware</option>
            <option value="Software">Software</option>
            <option value="Facilities">Facilities</option>
            <option value="Logistics">Logistics</option>
            <option value="Other">Other</option>
          </select>
        </div>
        <div>
          <label htmlFor="spend-amount" className="block text-sm font-medium text-gray-700 mb-1">
            Spend amount (optional)
          </label>
          <input
            id="spend-amount"
            type="number"
            value={spendAmount}
            onChange={e => setSpendAmount(e.target.value)}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="50000"
          />
        </div>
        <button
          type="submit"
          disabled={running}
          className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {running ? 'Assessing…' : 'Run assessment'}
        </button>
      </form>

      {started && (
        <div className="w-full max-w-md space-y-3">
          <AgentCard label="Market Scout" status={cards.scout.status} detail={cards.scout.detail} warning={cards.scout.warning} />
          <AgentCard
            label="Policy Librarian"
            status={cards.librarian.status}
            detail={cards.librarian.detail}
            warning={cards.librarian.warning}
          />
          <AgentCard
            label="Risk Synthesizer"
            status={cards.synthesizer.status}
            detail={cards.synthesizer.detail}
          />
        </div>
      )}
    </main>
  )
}
