import React, { useRef, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { select } from 'd3-selection'
import { zoom, ZoomBehavior } from 'd3-zoom'
import { drag } from 'd3-drag'
import { forceSimulation, forceLink, forceManyBody, forceCenter, SimulationNodeDatum, SimulationLinkDatum } from 'd3-force'

interface Node {
  id: string
  label: string
}
interface Edge {
  from: string
  to: string
  type?: string
}

interface Props {
  nodes: Node[]
  edges: Edge[]
  width?: number
  height?: number
}

type D3Node = Node & SimulationNodeDatum & { id: string }
type D3Link = SimulationLinkDatum<D3Node> & { source: string | D3Node; target: string | D3Node }

export const AgentDependencyGraph: React.FC<Props> = ({ nodes, edges, width = 600, height = 400 }) => {
  const navigate = useNavigate()
  const svgRef = useRef<SVGSVGElement | null>(null)
  const gRef = useRef<SVGGElement | null>(null)

  const [currentNodes, setCurrentNodes] = useState<D3Node[]>([])
  const [currentLinks, setCurrentLinks] = useState<D3Link[]>([])
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    // Convert nodes/edges into d3-friendly objects
    const dNodes: D3Node[] = nodes.map(n => ({ ...n }))

    // Filter edges to only include those where both source and target nodes exist
    const validEdges = edges.filter(e =>
      dNodes.some(n => n.id === e.from) && dNodes.some(n => n.id === e.to)
    )

    const dLinks: D3Link[] = validEdges.map(e => ({ source: e.from as any, target: e.to as any, type: e.type }))

    setCurrentNodes(dNodes)
    setCurrentLinks(dLinks)

    // Setup simulation only if we have nodes
    if (dNodes.length === 0) return

    const sim = forceSimulation<D3Node>(dNodes)
      .force('link', forceLink<D3Node, D3Link>(dLinks).id((d: any) => (d.id)))
      .force('charge', forceManyBody().strength(-180))
      .force('center', forceCenter(width / 2, height / 2))
      .alphaDecay(0.02)

    // Update positions on tick
    const onTick = () => {
      // Trigger re-render by updating state shallowly
      setCurrentNodes([...dNodes])
      setCurrentLinks([...dLinks])
    }
    sim.on('tick', onTick)

    // Allow some initial settling then reduce activity
    sim.alpha(0.9)

    return () => {
      sim.on('tick', null)
      sim.stop()
    }
  }, [nodes, edges, width, height])

  useEffect(() => {
    if (!svgRef.current || !gRef.current) return

    const svg = select(svgRef.current)
    const g = select(gRef.current)

    // Pan & zoom
    const z: ZoomBehavior<SVGSVGElement, unknown> = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString())
      })

    svg.call(z as any)

    // Set up dragging for nodes
    // Because nodes are re-created by React, we add drag handlers on the container level via selections
    const nodeSelection = g.selectAll<SVGGElement, D3Node>('g.node')
    nodeSelection.call(drag<SVGGElement, D3Node>()
      .on('start', (event: any, d: any) => {
        event.sourceEvent.stopPropagation()
        // pin the node during drag
        if ((d as any).fx === undefined) (d as any).fx = d.x
        if ((d as any).fy === undefined) (d as any).fy = d.y
      })
      .on('drag', (event: any, d: any) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event: any, d: any) => {
        // release pin
        d.fx = null
        d.fy = null
      })
    )

    return () => {
      svg.on('.zoom', null)
    }
  }, [currentNodes, currentLinks])

  const handleNodeClick = (id: string) => {
    setSelected(prev => prev === id ? null : id)
    navigate(`/agents/${encodeURIComponent(id)}`)
  }

  // Render edges and nodes with current positions
  return (
    <svg ref={svgRef} role="img" aria-label="Agent dependency graph" width={width} height={height} className="border rounded bg-white dark:bg-gray-800">
      <g ref={gRef}>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#999" />
          </marker>
        </defs>

        {/* edges */}
        {currentLinks.map((link, i) => {
          const s = link.source as D3Node
          const t = link.target as D3Node
          const x1 = s?.x ?? 0
          const y1 = s?.y ?? 0
          const x2 = t?.x ?? 0
          const y2 = t?.y ?? 0
          const highlighted = hovered === s?.id || hovered === t?.id || selected === s?.id || selected === t?.id
          return (
            <g key={`link-${i}`}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={highlighted ? '#1f6feb' : '#999'} strokeWidth={highlighted ? 2.5 : 1.2} markerEnd="url(#arrow)" />
              {link.type && <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} fontSize={10} fill="#666" textAnchor="middle">{link.type}</text>}
            </g>
          )
        })}

        {/* nodes */}
        {currentNodes.map((n) => {
          const x = n.x ?? 0
          const y = n.y ?? 0
          const highlighted = hovered === n.id || selected === n.id
          return (
            <g key={n.id} className={`node`} transform={`translate(${x}, ${y})`} style={{ cursor: 'pointer' }} onMouseEnter={() => setHovered(n.id)} onMouseLeave={() => setHovered(null)} onClick={() => handleNodeClick(n.id)}>
              <circle r={highlighted ? 14 : 11} fill={highlighted ? '#e6f0ff' : '#f7fafc'} stroke={highlighted ? '#1f6feb' : '#cbd5e1'} strokeWidth={highlighted ? 2 : 1} />
              <text x={0} y={4} fontSize={11} textAnchor="middle" fill={highlighted ? '#1f6feb' : '#111'}>{n.label}</text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}

export default AgentDependencyGraph
