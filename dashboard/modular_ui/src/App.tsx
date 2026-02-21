import { Routes, Route } from 'react-router-dom'
import { DashboardLayout } from './components/layout/DashboardLayout'
import { DashboardPage } from './pages/DashboardPage'
import { MarketDataPage } from './pages/MarketDataPage'
import { TradingPage } from './pages/TradingPage'
import { SignalsPage } from './pages/SignalsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { NewsPage } from './pages/NewsPage'
import { SettingsPage } from './pages/SettingsPage'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { LatestRunPage } from './pages/LatestRunPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { WebSocketProvider } from './hooks/useWebSocket'
import { ThemeProvider } from './hooks/useTheme'

function App() {
  return (
    <ThemeProvider>
      <WebSocketProvider>
        <DashboardLayout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/market-data" element={<MarketDataPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <Route path="/signals" element={<SignalsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/news" element={<NewsPage />} />
            <Route path="/latest-run" element={<LatestRunPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/agents/:agentName" element={<AgentDetailPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </DashboardLayout>
      </WebSocketProvider>
    </ThemeProvider>
  )
}

export default App
