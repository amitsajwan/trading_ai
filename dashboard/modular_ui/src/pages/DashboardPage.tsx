import React, { useState, useEffect } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { CurrentSignalWidget } from '../components/widgets/CurrentSignalWidget'
import { MarketOverviewWidget } from '../components/widgets/MarketOverviewWidget'
import { TechnicalIndicatorsWidget } from '../components/widgets/TechnicalIndicatorsWidget'
import { ActivePositionsWidget } from '../components/widgets/ActivePositionsWidget'
import { RiskSummaryWidget } from '../components/widgets/RiskSummaryWidget'
import { QuickActionsWidget } from '../components/widgets/QuickActionsWidget'
import { AgentStatusWidget } from '../components/widgets/AgentStatusWidget'
import { ActiveSignalsWidget } from '../components/widgets/ActiveSignalsWidget'
import { AgentResponsesWidget } from '../components/widgets/AgentResponsesWidget'
import { OrchestratorDecisionsWidget } from '../components/widgets/OrchestratorDecisionsWidget'
import { TradeHistoryWidget } from '../components/widgets/TradeHistoryWidget'
import { KeyInsightsWidget } from '../components/widgets/KeyInsightsWidget'
import { AgentDetailModal } from '../components/widgets/AgentDetailModal'
import { WidgetShell } from '../components/widgets/WidgetShell'
import { fetchAgentStatuses, fetchOrchestratorDecisions, fetchSignals } from '../store/slices/tradingSlice'

type TabType = 'dashboard' | 'analytics' | 'signals'

export const DashboardPage: React.FC = () => {
  const dispatch = useDispatch()
  const [activeTab, setActiveTab] = useState<TabType>('dashboard')
  const [selectedAgent, setSelectedAgent] = useState<any>(null)
  const [agentModalOpen, setAgentModalOpen] = useState(false)
  const navigate = useNavigate()

  // Load data based on active tab - tab isolation for better debugging
  useEffect(() => {
    if (activeTab === 'dashboard') {
      // Dashboard tab: core trading data including signals
      dispatch(fetchAgentStatuses() as any)
      dispatch(fetchOrchestratorDecisions() as any)
      dispatch(fetchSignals() as any)
    } else if (activeTab === 'analytics') {
      // Analytics tab: agent details for analysis
      dispatch(fetchAgentStatuses() as any)
    } else if (activeTab === 'signals') {
      // Signals tab: full trading data
      dispatch(fetchAgentStatuses() as any)
      dispatch(fetchOrchestratorDecisions() as any)
      dispatch(fetchSignals() as any)
    }
  }, [dispatch, activeTab])

  const tabs: { id: TabType; label: string; description: string }[] = [
    { id: 'dashboard', label: 'Dashboard', description: 'Core trading view with signals & market data' },
    { id: 'analytics', label: 'Analytics', description: 'Technical analysis & risk management' },
    { id: 'signals', label: 'Signals', description: 'AI agent signals & trading decisions' }
  ]

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Trading Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Real-time monitoring of your AI trading system
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="px-3 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 rounded-full text-sm font-medium">
            Live Data Active
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-96">
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {tabs.find(t => t.id === 'dashboard')?.description}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {/* Current Signal - Primary Trading Focus */}
              <div className="xl:col-span-1">
                <WidgetShell id="current-signal" title="Current Signal">
                  <CurrentSignalWidget />
                </WidgetShell>
              </div>

              {/* Market Intelligence - AI Insights */}
              <div className="xl:col-span-1">
                <KeyInsightsWidget />
              </div>

              {/* Market Overview - Live Market Pulse */}
              <div className="xl:col-span-1">
                <WidgetShell id="market-overview" title="Market Overview">
                  <MarketOverviewWidget />
                </WidgetShell>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {tabs.find(t => t.id === 'analytics')?.description}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
              {/* Risk Summary */}
              <div className="xl:col-span-1">
                <WidgetShell id="risk-summary" title="Risk Summary">
                  <RiskSummaryWidget />
                </WidgetShell>
              </div>

              {/* Active Positions */}
              <div className="xl:col-span-1">
                <WidgetShell id="active-positions" title="Active Positions">
                  <ActivePositionsWidget />
                </WidgetShell>
              </div>

              {/* Quick Actions */}
              <div className="xl:col-span-1">
                <WidgetShell id="quick-actions" title="Quick Actions">
                  <QuickActionsWidget />
                </WidgetShell>
              </div>

              {/* Technical Indicators */}
              <div className="xl:col-span-1">
                <WidgetShell id="technical-indicators" title="Technical Indicators">
                  <TechnicalIndicatorsWidget />
                </WidgetShell>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'signals' && (
          <div className="space-y-6">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {tabs.find(t => t.id === 'signals')?.description}
            </div>

            {/* Agent Status Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <WidgetShell id="agent-status-signals" title="Agent Status">
                <AgentStatusWidget onAgentClick={(agent) => {
                  // Navigate to full agent detail page
                  if (agent?.name) {
                    navigate(`/agents/${encodeURIComponent(agent.name)}`)
                  } else {
                    setSelectedAgent(agent)
                    setAgentModalOpen(true)
                  }
                }} />
              </WidgetShell>

              <WidgetShell id="orchestrator-decisions" title="Orchestrator Decisions">
                <OrchestratorDecisionsWidget />
              </WidgetShell>
            </div>

            {/* Agent Responses and Active Signals */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <WidgetShell id="agent-responses" title="Agent Responses">
                <AgentResponsesWidget />
              </WidgetShell>

              <WidgetShell id="active-signals" title="Active Signals">
                <ActiveSignalsWidget />
              </WidgetShell>
            </div>

            {/* Trade History */}
            <div className="grid grid-cols-1 gap-6">
              <WidgetShell id="trade-history" title="Trade History">
                <TradeHistoryWidget />
              </WidgetShell>
            </div>
          </div>
        )}
      </div>

      {/* Agent Detail Modal */}
      <AgentDetailModal
        agent={selectedAgent}
        isOpen={agentModalOpen}
        onClose={() => {
          setAgentModalOpen(false)
          setSelectedAgent(null)
        }}
      />
    </div>
  )
}