import React, { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Shield, AlertTriangle, TrendingDown, TrendingUp, Save, RefreshCw } from 'lucide-react'
import { RootState } from '../../store'
import axios from 'axios'

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
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
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

      {/* Current Risk Metrics */}
      {metrics && (
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
