import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import RiskBrief from '../pages/RiskBrief'

const BASE_RESULT = {
  request_id: 'r-test',
  vendor_name: 'Acme Corp',
  risk_score: 7,
  confidence: 0.82,
  recommendation: 'Escalate' as const,
  risk_brief: 'Vendor shows elevated supply chain risk due to recent audits.',
  policy_hits: [
    { chunk_text: 'Vendors must maintain SOC2.', score: 0.91, source_doc: 'FAR Part 9', risk_category: 'compliance' },
  ],
  market_data: [
    { source: 'web_search', content: 'Acme flagged in news.', retrieved_at: '2026-06-11T00:00:00Z', confidence: 0.75 },
  ],
  contract_flags: [],
  errors: [],
  partial_output: false,
}

function mockFetch(result = BASE_RESULT) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(result) }),
  )
}

function renderBrief(requestId = 'r-test') {
  return render(
    <MemoryRouter initialEntries={[`/brief/${requestId}`]}>
      <Routes>
        <Route path="/brief/:requestId" element={<RiskBrief />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => vi.unstubAllGlobals())

// ── Cycle 1: tracer bullet — fetch on mount, render score + vendor ─────────────

describe('RiskBrief data fetch', () => {
  it('fetches GET /assess/{requestId}/result on mount and renders vendor name', async () => {
    mockFetch()
    renderBrief('r-test')
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument())
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/assess/r-test/result')
  })

  it('renders risk score', async () => {
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByText('7')).toBeInTheDocument())
  })
})

// ── Cycle 2: recommendation badge colours ─────────────────────────────────────

describe('RiskBrief recommendation badge', () => {
  it.each([
    ['Approve', 'green'],
    ['Escalate', 'amber'],
    ['Reject', 'red'],
    ['Pending', 'grey'],
  ] as const)('%s badge has %s colour class', async (recommendation, colour) => {
    mockFetch({ ...BASE_RESULT, recommendation })
    renderBrief()
    await waitFor(() => expect(screen.getByText(recommendation)).toBeInTheDocument())
    const badge = screen.getByText(recommendation)
    expect(badge.className).toMatch(colour === 'grey' ? /gray/ : new RegExp(colour))
  })
})

// ── Cycle 3: confidence display ───────────────────────────────────────────────

describe('RiskBrief confidence', () => {
  it('renders confidence as percentage', async () => {
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByText(/82%/)).toBeInTheDocument())
  })
})

// ── Cycle 4: risk narrative ───────────────────────────────────────────────────

describe('RiskBrief narrative', () => {
  it('renders risk_brief text', async () => {
    mockFetch()
    renderBrief()
    await waitFor(() =>
      expect(
        screen.getByText('Vendor shows elevated supply chain risk due to recent audits.'),
      ).toBeInTheDocument(),
    )
  })
})

// ── Cycle 5: policy hits expandable ──────────────────────────────────────────

describe('RiskBrief policy hits', () => {
  it('policy hit chunk_text hidden until expanded', async () => {
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByText(/policy hits/i)).toBeInTheDocument())
    expect(screen.queryByText('Vendors must maintain SOC2.')).not.toBeInTheDocument()
  })

  it('clicking policy hits toggle reveals chunk_text, source_doc, risk_category', async () => {
    const user = userEvent.setup()
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByRole('button', { name: /policy hits/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /policy hits/i }))
    expect(screen.getByText('Vendors must maintain SOC2.')).toBeInTheDocument()
    expect(screen.getByText('FAR Part 9')).toBeInTheDocument()
    expect(screen.getByText('compliance')).toBeInTheDocument()
  })

  it('clicking again collapses policy hits', async () => {
    const user = userEvent.setup()
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByRole('button', { name: /policy hits/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /policy hits/i }))
    await user.click(screen.getByRole('button', { name: /policy hits/i }))
    expect(screen.queryByText('Vendors must maintain SOC2.')).not.toBeInTheDocument()
  })
})

// ── Cycle 6: market signals expandable ───────────────────────────────────────

describe('RiskBrief market signals', () => {
  it('market signal content hidden until expanded', async () => {
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByText(/market signals/i)).toBeInTheDocument())
    expect(screen.queryByText('Acme flagged in news.')).not.toBeInTheDocument()
  })

  it('clicking market signals toggle reveals source and content', async () => {
    const user = userEvent.setup()
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByRole('button', { name: /market signals/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /market signals/i }))
    expect(screen.getByText('Acme flagged in news.')).toBeInTheDocument()
    expect(screen.getByText('web_search')).toBeInTheDocument()
  })
})

// ── Cycle 7: partial_output banner ────────────────────────────────────────────

describe('RiskBrief partial output banner', () => {
  it('no banner when partial_output is false', async () => {
    mockFetch()
    renderBrief()
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows visible banner when partial_output is true', async () => {
    mockFetch({ ...BASE_RESULT, partial_output: true })
    renderBrief()
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByRole('alert')).toHaveTextContent(/partial/i)
  })
})
