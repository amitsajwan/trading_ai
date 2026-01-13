import React, { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Shield, AlertTriangle, TrendingDown, TrendingUp, Save, RefreshCw, Thermometer, Activity } from 'lucide-react'
import { RootState } from '../../store'
import { 
  useGetPortfolioHeatSummaryQuery,
  useGetHeatUtilizationQuery,
  useGetApprovalStatsQuery
} from '../../api/dashboardApi'

interface RiskSettings {
  maxPositionSize: number
  maxDailyLoss: number
  stopLossPercent: number
  takeProfitPercent: number
  enableAutoStopLoss: boolean
  enableAutoTakeProfit: boolean
}

export const RiskManagementWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { portfolio } = useSelector((state: RootState) => state.trading)
  
  // Layer 8: Portfolio Heat and Approval Stats
  const { data: heatSummary, isLoading: heatLoading, error: heatError } = useGetPortfolioHeatSummaryQuery()
  const { data: heatUtilization, isLoading: utilLoading } = useGetHeatUtilizationQuery()
  const { data: approvalStats, isLoading: statsLoading } = useGetApprovalStatsQuery()
  
  const [settings, setSettings] = useState<RiskSettings>({
    maxPositionSize: 10000,
    maxDailyLoss: 5000,
    stopLossPercent: 2.0,
    takeProfitPercent: 3.0,
    enableAutoStopLoss: true,
    enableAutoTakeProfit: true,
  })
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Load saved settings from localStorage or API
    const savedSettings = localStorage.getItem('riskSettings')
    if (savedSettings) {
      try {
        setSettings(JSON.parse(savedSettings))
      } catch (e) {
        console.error('Failed to load risk settings:', e)
      }
    }
  }, [])

  const handleSave = async () => {
    setLoading(true)
    try {
      // Save to localStorage
      localStorage.setItem('riskSettings', JSON.stringify(settings))
      
      // Optionally save to backend
      // await axios.post('/api/trading/risk-settings', settings)
      
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save risk settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const calculateRiskMetrics = () => {
    if (!portfolio) return null

    const totalValue = portfolio.total_value || 0
    const cashBalance = portfolio.cash_balance || 0
    const dayPnl = portfolio.day_pnl || 0
    const positionsValue = totalValue - cashBalance
    const marginUsed = portfolio.margin_used || 0

    // Calculate risk ratios
    const positionSizePercent = totalValue > 0 ? (positionsValue / totalValue) * 100 : 0
    const dailyLossPercent = totalValue > 0 ? (Math.abs(Math.min(dayPnl, 0)) / totalValue) * 100 : 0
    const marginUtilization = (portfolio.margin_available || 0) > 0 
      ? (marginUsed / (marginUsed + (portfolio.margin_available || 0))) * 100 
      : 0

    return {
      totalValue,
      cashBalance,
      positionsValue,
      dayPnl,
      marginUsed,
      positionSizePercent,
      dailyLossPercent,
      marginUtilization,
      isRiskHigh: dailyLossPercent > (settings.maxDailyLoss / totalValue * 100) || marginUtilization > 80,
    }
  }

  const metrics = calculateRiskMetrics()

  return (
    <div 
      data-testid="widget-risk-management"
      className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Shield className="w-5 h-5 mr-2 text-primary-500" />
          Risk Management
        </h3>
        {saved && (
          <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
            <Save className="w-3 h-3" />
            Saved
          </span>
        )}
      </div>

      {/* Layer 8: Portfolio Heat Metrics */}
      {heatSummary && (
        <div className="mb-6 space-y-3">
          <div className={`p-3 rounded-lg border ${
            (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) > 0.8 || heatSummary.daily_loss_pct > 0.04
              ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' 
              : (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) > 0.5
              ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
              : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
          }`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Thermometer className="w-5 h-5 text-primary-500" />
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  Portfolio Heat
                </span>
              </div>
              <span className={`text-xs font-semibold px-2 py-1 rounded ${
                (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) > 0.8
                  ? 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-300'
                  : (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) > 0.5
                  ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-300'
                  : 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-300'
              }`}>
                {((heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) * 100).toFixed(1)}% Used
              </span>
            </div>
            
            {/* Heat Progress Bar */}
            <div className="mb-3">
              <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
                <span>Used: {(heatSummary.total_portfolio_heat * 100).toFixed(2)}%</span>
                <span>Available: {(heatSummary.available_heat * 100).toFixed(2)}%</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) > 0.8
                      ? 'bg-red-500'
                      : (heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) > 0.5
                      ? 'bg-yellow-500'
                      : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min((heatSummary.total_portfolio_heat / heatSummary.max_portfolio_heat) * 100, 100)}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-gray-600 dark:text-gray-400">Daily P&L:</span>
                <span className={`ml-1 font-semibold ${heatSummary.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {heatSummary.daily_pnl >= 0 ? '+' : ''}₹{heatSummary.daily_pnl.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Daily Loss:</span>
                <span className={`ml-1 font-semibold ${heatSummary.daily_loss_pct > 0.03 ? 'text-red-600' : 'text-gray-600'}`}>
                  {(heatSummary.daily_loss_pct * 100).toFixed(2)}%
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Max Loss:</span>
                <span className="ml-1 font-semibold">₹{heatSummary.total_max_loss.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Positions:</span>
                <span className="ml-1 font-semibold">{heatSummary.active_positions}</span>
              </div>
            </div>
          </div>

          {/* Approval Stats */}
          {approvalStats && (
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-primary-500" />
                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  Approval Stats (Last {approvalStats.total_reviews} reviews)
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Approved:</span>
                  <span className="ml-1 font-semibold text-green-600">
                    {approvalStats.approved} ({(approvalStats.approval_rate * 100).toFixed(0)}%)
                  </span>
                </div>
                <div>
                  <span className="text-gray-600 dark:text-gray-400">Rejected:</span>
                  <span className="ml-1 font-semibold text-red-600">
                    {approvalStats.rejected} ({(approvalStats.rejection_rate * 100).toFixed(0)}%)
                  </span>
                </div>
                {approvalStats.reduced !== undefined && (
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">Reduced:</span>
                    <span className="ml-1 font-semibold text-yellow-600">
                      {approvalStats.reduced} ({((approvalStats.reduction_rate || 0) * 100).toFixed(0)}%)
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fallback to legacy metrics if heat summary not available */}
      {!heatSummary && metrics && (
        <div className="mb-6 space-y-3">
          <div className={`p-3 rounded-lg border ${
            metrics.isRiskHigh 
              ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' 
              : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              {metrics.isRiskHigh ? (
                <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400" />
              ) : (
                <Shield className="w-4 h-4 text-green-600 dark:text-green-400" />
              )}
              <span className={`text-sm font-semibold ${
                metrics.isRiskHigh ? 'text-red-800 dark:text-red-300' : 'text-green-800 dark:text-green-300'
              }`}>
                {metrics.isRiskHigh ? 'Risk Level: HIGH' : 'Risk Level: NORMAL'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-gray-600 dark:text-gray-400">Day P&L:</span>
                <span className={`ml-1 font-semibold ${metrics.dayPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {metrics.dayPnl >= 0 ? '+' : ''}₹{metrics.dayPnl.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-gray-600 dark:text-gray-400">Margin Used:</span>
                <span className="ml-1 font-semibold">{metrics.marginUtilization.toFixed(1)}%</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Portfolio Value</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">
                ₹{metrics.totalValue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Cash Balance</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">
                ₹{metrics.cashBalance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Risk Settings */}
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Max Position Size (₹)
          </label>
          <input
            type="number"
            min="0"
            step="100"
            value={settings.maxPositionSize}
            onChange={(e) => setSettings({ ...settings, maxPositionSize: parseFloat(e.target.value) || 0 })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Max Daily Loss (₹)
          </label>
          <input
            type="number"
            min="0"
            step="100"
            value={settings.maxDailyLoss}
            onChange={(e) => setSettings({ ...settings, maxDailyLoss: parseFloat(e.target.value) || 0 })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Stop Loss (%)
            </label>
            <div className="relative">
              <TrendingDown className="absolute left-3 top-2.5 w-4 h-4 text-red-500" />
              <input
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={settings.stopLossPercent}
                onChange={(e) => setSettings({ ...settings, stopLossPercent: parseFloat(e.target.value) || 0 })}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Take Profit (%)
            </label>
            <div className="relative">
              <TrendingUp className="absolute left-3 top-2.5 w-4 h-4 text-green-500" />
              <input
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={settings.takeProfitPercent}
                onChange={(e) => setSettings({ ...settings, takeProfitPercent: parseFloat(e.target.value) || 0 })}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enableAutoStopLoss}
              onChange={(e) => setSettings({ ...settings, enableAutoStopLoss: e.target.checked })}
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">Enable Auto Stop Loss</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enableAutoTakeProfit}
              onChange={(e) => setSettings({ ...settings, enableAutoTakeProfit: e.target.checked })}
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">Enable Auto Take Profit</span>
          </label>
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          className="w-full py-2 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-primary-400 text-white rounded-lg font-semibold transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save Settings
            </>
          )}
        </button>
      </div>
    </div>
  )
}
