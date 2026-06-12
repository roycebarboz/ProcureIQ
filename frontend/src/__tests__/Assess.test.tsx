import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Assess from '../pages/Assess'

function renderAssess() {
  return render(
    <MemoryRouter>
      <Assess />
    </MemoryRouter>,
  )
}

/** Build a ReadableStream that emits SSE text events then closes. */
function sseStream(...events: Array<{ event: string; data: object }>): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const { event, data } of events) {
        controller.enqueue(enc.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`))
      }
      controller.close()
    },
  })
}

async function submitForm(user: ReturnType<typeof userEvent.setup>, fetchBody: ReadableStream) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ body: fetchBody }))
  renderAssess()
  await user.type(screen.getByRole('textbox', { name: /vendor name/i }), 'Acme')
  await user.selectOptions(screen.getByRole('combobox', { name: /category/i }), 'IT Services')
  await user.click(screen.getByRole('button', { name: /run assessment/i }))
}

// ── Cycle 2: category dropdown ────────────────────────────────────────────────

describe('Assess form', () => {
  it('renders category as a <select> element', () => {
    renderAssess()
    expect(screen.getByRole('combobox', { name: /category/i })).toBeInTheDocument()
  })

  it('category dropdown has selectable options', async () => {
    renderAssess()
    const select = screen.getByRole('combobox', { name: /category/i })
    const options = Array.from((select as HTMLSelectElement).options).map(o => o.value)
    expect(options.length).toBeGreaterThan(1)
  })

  it('submits without spend amount', async () => {
    const user = userEvent.setup()
    const fetchSpy = vi.fn().mockResolvedValue({
      body: new ReadableStream({
        start(controller) { controller.close() },
      }),
    })
    vi.stubGlobal('fetch', fetchSpy)

    renderAssess()
    await user.type(screen.getByRole('textbox', { name: /vendor name/i }), 'Acme')
    await user.selectOptions(screen.getByRole('combobox', { name: /category/i }), 'IT Services')
    await user.click(screen.getByRole('button', { name: /run assessment/i }))

    expect(fetchSpy).toHaveBeenCalledWith(
      '/assess',
      expect.objectContaining({ method: 'POST' }),
    )
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body)
    expect(body.spend_amount).toBeNull()

    vi.unstubAllGlobals()
  })
})

// ── Cycle 5: SSE drop → GET retry ────────────────────────────────────────────

describe('Assess SSE retry', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('calls GET /assess/{requestId}/result when stream closes without assessment_complete', async () => {
    const user = userEvent.setup()

    const getFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        request_id: 'r-retry',
        risk_score: 42,
        recommendation: 'Escalate',
        risk_brief: 'test',
        confidence: 0.6,
      }),
    })

    // First call = POST /assess (SSE stream, closes without assessment_complete)
    // Second call = GET /assess/{id}/result
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({
        body: sseStream({
          event: 'scout_complete',
          data: { request_id: 'r-retry', market_data: [], contract_flags: [], errors: [], partial_output: false },
        }),
      })
      .mockImplementationOnce(getFetch),
    )

    renderAssess()
    await user.type(screen.getByRole('textbox', { name: /vendor name/i }), 'Acme')
    await user.selectOptions(screen.getByRole('combobox', { name: /category/i }), 'IT Services')
    await user.click(screen.getByRole('button', { name: /run assessment/i }))

    await waitFor(() =>
      expect(getFetch).toHaveBeenCalledWith('/assess/r-retry/result'),
    )
  })
})

// ── Cycle 3: scout degradation warning ───────────────────────────────────────

describe('Assess degradation warnings', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows ⚠ Partial data on Scout card when scout_complete carries errors', async () => {
    const user = userEvent.setup()
    await submitForm(
      user,
      sseStream({
        event: 'scout_complete',
        data: {
          request_id: 'r1',
          market_data: [],
          contract_flags: [],
          errors: [{ node: 'market_scout', reason: 'timeout_tavily', fallback_used: true }],
          partial_output: true,
        },
      }),
    )

    await waitFor(() =>
      expect(screen.getByText(/⚠ Partial data — timeout_tavily/)).toBeInTheDocument(),
    )
  })

  // ── Cycle 4: librarian degradation warning ────────────────────────────────

  it('shows ⚠ Partial data on Librarian card when librarian_complete carries errors', async () => {
    const user = userEvent.setup()
    await submitForm(
      user,
      sseStream(
        {
          event: 'scout_complete',
          data: { request_id: 'r2', market_data: [], contract_flags: [], errors: [], partial_output: false },
        },
        {
          event: 'librarian_complete',
          data: {
            request_id: 'r2',
            policy_hits: [],
            errors: [{ node: 'policy_librarian', reason: 'embed_timeout', fallback_used: true }],
            partial_output: true,
          },
        },
      ),
    )

    await waitFor(() =>
      expect(screen.getByText(/⚠ Partial data — embed_timeout/)).toBeInTheDocument(),
    )
  })
})
