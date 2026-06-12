import { render, screen } from '@testing-library/react'
import AgentCard from '../components/AgentCard'

describe('AgentCard', () => {
  it('renders label and status', () => {
    render(<AgentCard label="Market Scout" status="pending" />)
    expect(screen.getByText('Market Scout')).toBeInTheDocument()
  })

  it('renders detail when provided', () => {
    render(<AgentCard label="Market Scout" status="complete" detail="3 signals" />)
    expect(screen.getByText('3 signals')).toBeInTheDocument()
  })

  it('renders degradation warning inline when warning prop set', () => {
    render(<AgentCard label="Market Scout" status="complete" warning="timeout_tavily" />)
    expect(screen.getByText(/⚠ Partial data — timeout_tavily/)).toBeInTheDocument()
  })

  it('renders no warning element when warning prop absent', () => {
    render(<AgentCard label="Market Scout" status="complete" />)
    expect(screen.queryByText(/⚠ Partial data/)).not.toBeInTheDocument()
  })
})
