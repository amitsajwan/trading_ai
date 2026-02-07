import React from 'react'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import AgentDependencyGraph from '../AgentDependencyGraph'

const nodes = [ { id: 'A', label: 'A' }, { id: 'B', label: 'B' }, { id: 'C', label: 'C' } ]
const edges = [ { from: 'A', to: 'B', type: 'data_flow' }, { from: 'B', to: 'C', type: 'veto' } ]

test('renders graph SVG with nodes', () => {
  render(
    <BrowserRouter>
      <AgentDependencyGraph nodes={nodes} edges={edges} width={400} height={300} />
    </BrowserRouter>
  )

  const svg = screen.getByRole('img', { name: /agent dependency graph/i })
  expect(svg).toBeTruthy()

  // Check that node labels are present (text elements)
  const texts = svg.querySelectorAll('text')
  const labels = Array.from(texts).map(t => t.textContent)
  expect(labels).toEqual(expect.arrayContaining(['A', 'B', 'C']))
})
