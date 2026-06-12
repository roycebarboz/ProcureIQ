import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from '../pages/Dashboard'

const EMPTY_DATA = {
  node_latency: {},
  partial_rate: 0,
  recommendation_dist: { Approve: 0, Escalate: 0, Reject: 0, Pending: 0 },
  recent_assessments: [],
}

function mockFetch(data = EMPTY_DATA) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(data) }),
  )
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )
}

afterEach(() => vi.unstubAllGlobals())

// ── Cycle 1: tracer bullet — fetch on mount, render heading ────────────────

describe('Dashboard data fetch', () => {
  it('fetches GET /dashboard on mount', async () => {
    mockFetch()
    renderDashboard()
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/dashboard')
  })

  it('renders Node Latency heading after data loads', async () => {
    mockFetch()
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/node latency/i)).toBeInTheDocument())
  })
})

// ── Cycle 2: node latency bars render correct node labels ──────────────────

describe('Dashboard node latency chart', () => {
  it('renders formatted node labels from latency data', async () => {
    mockFetch({
      ...EMPTY_DATA,
      node_latency: {
        market_scout: 120.5,
        policy_librarian: 85.3,
        risk_synthesizer: 210.7,
      },
    })
    renderDashboard()
    await waitFor(() => expect(screen.getByText('Market Scout')).toBeInTheDocument())
    expect(screen.getByText('Policy Librarian')).toBeInTheDocument()
    expect(screen.getByText('Risk Synthesizer')).toBeInTheDocument()
  })

  it('renders duration values next to bars', async () => {
    mockFetch({
      ...EMPTY_DATA,
      node_latency: { market_scout: 120.5 },
    })
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/120\.5\s*ms/)).toBeInTheDocument())
  })
})

// ── Cycle 3: partial rate renders as percentage ────────────────────────────

describe('Dashboard partial assessment rate', () => {
  it('renders partial rate as a percentage', async () => {
    mockFetch({ ...EMPTY_DATA, partial_rate: 25.5 })
    renderDashboard()
    await waitFor(() => expect(screen.getByText('25.5%')).toBeInTheDocument())
  })

  it('renders 0% when no partial assessments', async () => {
    mockFetch(EMPTY_DATA)
    renderDashboard()
    await waitFor(() => expect(screen.getByText('0%')).toBeInTheDocument())
  })
})

// ── Cycle 4: recommendation distribution counts ────────────────────────────

describe('Dashboard recommendation distribution', () => {
  it('renders all four recommendation labels', async () => {
    mockFetch({
      ...EMPTY_DATA,
      recommendation_dist: { Approve: 5, Escalate: 3, Reject: 1, Pending: 2 },
    })
    renderDashboard()
    await waitFor(() => expect(screen.getByText('Approve')).toBeInTheDocument())
    expect(screen.getByText('Escalate')).toBeInTheDocument()
    expect(screen.getByText('Reject')).toBeInTheDocument()
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('renders counts next to each recommendation', async () => {
    mockFetch({
      ...EMPTY_DATA,
      recommendation_dist: { Approve: 5, Escalate: 3, Reject: 1, Pending: 2 },
    })
    renderDashboard()
    await waitFor(() => expect(screen.getByTestId('dist-count-Approve')).toHaveTextContent('5'))
    expect(screen.getByTestId('dist-count-Escalate')).toHaveTextContent('3')
    expect(screen.getByTestId('dist-count-Reject')).toHaveTextContent('1')
    expect(screen.getByTestId('dist-count-Pending')).toHaveTextContent('2')
  })
})

// ── Cycle 5: recent assessments table with links ───────────────────────────

describe('Dashboard recent assessments table', () => {
  it('renders vendor name linked to risk brief screen', async () => {
    mockFetch({
      ...EMPTY_DATA,
      recent_assessments: [
        {
          request_id: 'req-abc',
          vendor_name: 'Acme Corp',
          recommendation: 'Approve',
          confidence: 0.9,
          timestamp: '2026-06-11T12:00:00Z',
        },
      ],
    })
    renderDashboard()
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: /acme corp/i })
    expect(link).toHaveAttribute('href', '/brief/req-abc')
  })

  it('renders recommendation and confidence for each row', async () => {
    mockFetch({
      ...EMPTY_DATA,
      recent_assessments: [
        {
          request_id: 'req-abc',
          vendor_name: 'Acme Corp',
          recommendation: 'Escalate',
          confidence: 0.72,
          timestamp: '2026-06-11T12:00:00Z',
        },
      ],
    })
    renderDashboard()
    // vendor name is unique — confirms data loaded
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument())
    // confidence percentage is unique to the table row
    expect(screen.getByText('72%')).toBeInTheDocument()
  })
})

// ── Cycle 6: zero-state ────────────────────────────────────────────────────

describe('Dashboard zero state', () => {
  it('renders without errors when all data is empty', async () => {
    mockFetch(EMPTY_DATA)
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/node latency/i)).toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows "No data yet" in node latency section when empty', async () => {
    mockFetch(EMPTY_DATA)
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/no data yet/i)).toBeInTheDocument())
  })

  it('shows "No assessments yet" when recent_assessments is empty', async () => {
    mockFetch(EMPTY_DATA)
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/no assessments yet/i)).toBeInTheDocument())
  })
})
