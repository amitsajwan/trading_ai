import React, { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Send, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { RootState } from '../../store'
import { executeTrade } from '../../store/slices/tradingSlice'
import { fetchOptionsChain } from '../../store/slices/marketDataSlice'

type InstrumentType = 'SPOT' | 'FUTURES' | 'OPTIONS' | 'STRATEGY'

export const TradeExecutionWidget: React.FC = () => {
  const dispatch = useDispatch()
  const { error, loading } = useSelector((state: RootState) => state.trading)
  const { optionsChain } = useSelector((state: RootState) => state.marketData)
  
  const [formData, setFormData] = useState({
    instrumentType: 'OPTIONS' as InstrumentType,  // Default to Options (you deal with options)
    instrument: 'BANKNIFTY',  // Will be Options with nearest expiry
    side: 'BUY' as 'BUY' | 'SELL',
    quantity: 1,
    price: 0, // 0 = market order
    orderType: 'MARKET' as 'MARKET' | 'LIMIT',
    stopLoss: 0,
    takeProfit: 0,
    // Options-specific fields
    strike: 0,
    expiry: '',
    optionType: 'CE' as 'CE' | 'PE',
    // Strategy fields
    strategyType: 'IRON_CONDOR' as 'IRON_CONDOR' | 'BULL_SPREAD' | 'BEAR_SPREAD' | 'STRADDLE' | 'STRANGLE',
  })
  const [submitted, setSubmitted] = useState(false)
  const [currentIndicators, setCurrentIndicators] = useState<any>(null)
  const [signalValidation, setSignalValidation] = useState<{
    isValid: boolean
    warnings: string[]
    recommendations: string[]
  }>({ isValid: true, warnings: [], recommendations: [] })

  // Load options chain when instrument or instrumentType changes
  useEffect(() => {
    if (formData.instrumentType === 'OPTIONS' || formData.instrumentType === 'STRATEGY') {
      dispatch(fetchOptionsChain(formData.instrument) as any)
    }
  }, [formData.instrument, formData.instrumentType, dispatch])

  // Extract available expiries and strikes from options chain
  const availableExpiries = optionsChain?.expiry ? [optionsChain.expiry] : []
  const availableStrikes = optionsChain?.strikes?.map(s => s.strike) || []
  const futuresPrice = optionsChain?.futures_price || 0

  // Auto-select nearest strike to futures price when options chain loads
  useEffect(() => {
    if (formData.instrumentType === 'OPTIONS' && availableStrikes.length > 0 && futuresPrice > 0 && formData.strike === 0) {
      // Find strike closest to futures price
      const nearestStrike = availableStrikes.reduce((prev, curr) => {
        return Math.abs(curr - futuresPrice) < Math.abs(prev - futuresPrice) ? curr : prev
      })
      setFormData({ ...formData, strike: nearestStrike })
    }
  }, [availableStrikes, futuresPrice, formData.instrumentType])

  // Auto-select first expiry if available
  useEffect(() => {
    if (formData.instrumentType === 'OPTIONS' && availableExpiries.length > 0 && !formData.expiry) {
      setFormData({ ...formData, expiry: availableExpiries[0] })
    }
  }, [availableExpiries, formData.instrumentType])

  // Fetch current indicators for signal validation
  useEffect(() => {
    const fetchIndicators = async () => {
      try {
        // Use the dev-server proxied path so Vite will forward the request to the Market Data API
        // Previous direct call to /api/v1/... hit the dev server and returned index.html (HTML), causing JSON parse errors.
    const response = await fetch('/api/market-data/technical/BANKNIFTY')
        if (response.ok) {
          const contentType = response.headers.get('content-type') || ''
          if (contentType.includes('text/html')) {
            // Helpful debug message: hitting the dev server root instead of API (likely missing proxy or wrong path)
            console.error('Indicators fetch returned HTML. The request likely hit the dev server instead of the API. Check Vite proxy or use the proxied /api/market-data/technical/* path.')
            return
          }

          const data = await response.json()
          setCurrentIndicators(data.indicators)
          validateTradeSignal(data.indicators)
        }
      } catch (error) {
        console.error('Failed to fetch indicators:', error)
      }
    }

    fetchIndicators()
    // Refresh indicators every 30 seconds
    const interval = setInterval(fetchIndicators, 30000)
    return () => clearInterval(interval)
  }, [])

  // Validate trade against current market signals
  const validateTradeSignal = (indicators: any) => {
    const warnings: string[] = []
    const recommendations: string[] = []

    if (!indicators) return

    const rsi = indicators.rsi_14
    const macd = indicators.macd_value
    const macdSignal = indicators.macd_signal
    const adx = indicators.adx_14

    // RSI validation (you mentioned RSI > 30)
    if (rsi !== null && rsi !== undefined) {
      if (rsi < 30) {
        warnings.push(`RSI is ${rsi.toFixed(1)} (< 30) - Oversold condition, but BUY signal may be risky`)
      } else if (rsi > 70) {
        warnings.push(`RSI is ${rsi.toFixed(1)} (> 70) - Overbought condition`)
      } else {
        recommendations.push(`RSI at ${rsi.toFixed(1)} - Neutral to bullish zone`)
      }
    }

    // MACD validation
    if (macd !== null && macdSignal !== null) {
      if (macd > macdSignal) {
        recommendations.push('MACD above signal line - Bullish momentum')
      } else {
        warnings.push('MACD below signal line - Bearish momentum')
      }
    }

    // ADX for trend strength
    if (adx !== null) {
      if (adx > 25) {
        recommendations.push(`Strong trend (ADX: ${adx.toFixed(1)})`)
      } else {
        recommendations.push('ADX below 25 - Weak/no trend')
      }
    }

    setSignalValidation({
      isValid: warnings.length === 0,
      warnings,
      recommendations
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(false)

    // Check signal validation before proceeding
    if (!signalValidation.isValid && !confirm('Warning: Current market conditions may not be favorable for this trade. Proceed anyway?')) {
      return
    }

    try {
      const tradePayload: any = {
        instrument: formData.instrument,
        side: formData.side,
        quantity: formData.quantity,
        price: formData.orderType === 'LIMIT' ? formData.price : undefined,
        order_type: formData.orderType,
        stop_loss: formData.stopLoss > 0 ? formData.stopLoss : undefined,
        take_profit: formData.takeProfit > 0 ? formData.takeProfit : undefined,
      }

      // Add Options-specific fields if trading Options
      if (formData.instrumentType === 'OPTIONS') {
        tradePayload.strike_price = formData.strike
        tradePayload.expiry_date = formData.expiry
        tradePayload.option_type = formData.optionType
        tradePayload.instrument_type = 'OPTIONS'
        // Build trading symbol: e.g., "BANKNIFTY25JAN59500CE"
        // This would be done on backend, but include for reference
      } else if (formData.instrumentType === 'FUTURES') {
        tradePayload.instrument_type = 'FUTURES'
        // Futures symbol: e.g., "BANKNIFTY24JANFUT"
      } else if (formData.instrumentType === 'STRATEGY') {
        tradePayload.instrument_type = 'STRATEGY'
        tradePayload.strategy_type = formData.strategyType
        // Strategy legs would be constructed on backend
      } else {
        tradePayload.instrument_type = 'SPOT'
      }

      await dispatch(executeTrade(tradePayload) as any)

      setSubmitted(true)
      setTimeout(() => setSubmitted(false), 3000)

      // Reset form (keep instrument type and basic fields)
      setFormData({
        ...formData,
        quantity: 1,
        price: 0,
        stopLoss: 0,
        takeProfit: 0,
      })
    } catch (err) {
      console.error('Trade execution failed:', err)
    }
  }

  // Get current LTP for selected strike (if Options)
  const getCurrentLTP = () => {
    if (formData.instrumentType === 'OPTIONS' && formData.strike > 0 && optionsChain?.strikes) {
      const strikeData = optionsChain.strikes.find(s => s.strike === formData.strike)
      if (strikeData) {
        return formData.optionType === 'CE' ? strikeData.ce_ltp : strikeData.pe_ltp
      }
    }
    return null
  }

  const currentLTP = getCurrentLTP()

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Send className="w-5 h-5 mr-2 text-primary-500" />
          Trade Execution
        </h3>
      </div>

      {submitted && (
        <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
          <span className="text-sm text-green-800 dark:text-green-300">Trade order submitted successfully!</span>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
          <span className="text-sm text-red-800 dark:text-red-300">{error}</span>
        </div>
      )}

      {/* Signal Validation */}
      {currentIndicators && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <h4 className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-2">Market Signal Analysis</h4>
          
          {signalValidation.warnings.length > 0 && (
            <div className="mb-2">
              <p className="text-xs text-red-600 dark:text-red-400 font-medium">Warnings:</p>
              <ul className="text-xs text-red-600 dark:text-red-400 ml-4">
                {signalValidation.warnings.map((warning, idx) => (
                  <li key={idx}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}
          
          {signalValidation.recommendations.length > 0 && (
            <div>
              <p className="text-xs text-green-600 dark:text-green-400 font-medium">Recommendations:</p>
              <ul className="text-xs text-green-600 dark:text-green-400 ml-4">
                {signalValidation.recommendations.map((rec, idx) => (
                  <li key={idx}>• {rec}</li>
                ))}
              </ul>
            </div>
          )}
          
          <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
            Current: RSI {currentIndicators.rsi_14?.toFixed(1) || 'N/A'} | 
            MACD {currentIndicators.macd_value?.toFixed(2) || 'N/A'} | 
            ADX {currentIndicators.adx_14?.toFixed(1) || 'N/A'}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Instrument Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Instrument Type
          </label>
          <select
            value={formData.instrumentType}
            onChange={(e) => setFormData({ ...formData, instrumentType: e.target.value as InstrumentType, strike: 0, expiry: '' })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="OPTIONS">Options (Recommended - You deal with options)</option>
            <option value="STRATEGY">Strategy (Iron Condor, Spreads, etc.)</option>
          </select>
        </div>

        {/* Instrument */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Underlying Instrument
          </label>
          <input
            type="text"
            value={formData.instrument}
            onChange={(e) => setFormData({ ...formData, instrument: e.target.value.toUpperCase() })}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            placeholder="BANKNIFTY"
            required
          />
        </div>

        {/* Options-specific fields */}
        {formData.instrumentType === 'OPTIONS' && (
          <>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Strike
                </label>
                <select
                  value={formData.strike}
                  onChange={(e) => setFormData({ ...formData, strike: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                >
                  <option value="">Select Strike</option>
                  {availableStrikes.map(strike => (
                    <option key={strike} value={strike}>{strike}</option>
                  ))}
                </select>
                {futuresPrice > 0 && (
                  <p className="text-xs text-gray-500 mt-1">Futures: ₹{futuresPrice.toFixed(2)}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Option Type
                </label>
                <select
                  value={formData.optionType}
                  onChange={(e) => setFormData({ ...formData, optionType: e.target.value as 'CE' | 'PE' })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                >
                  <option value="CE">Call (CE)</option>
                  <option value="PE">Put (PE)</option>
                </select>
                {currentLTP && (
                  <p className="text-xs text-gray-500 mt-1">LTP: ₹{currentLTP.toFixed(2)}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Expiry
                </label>
                <select
                  value={formData.expiry}
                  onChange={(e) => setFormData({ ...formData, expiry: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                >
                  <option value="">Select Expiry</option>
                  {availableExpiries.map(expiry => (
                    <option key={expiry} value={expiry}>{new Date(expiry).toLocaleDateString()}</option>
                  ))}
                </select>
              </div>
            </div>
            {formData.strike > 0 && currentLTP && (
              <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-sm text-blue-800 dark:text-blue-300">
                Selected: {formData.instrument} {formData.strike} {formData.optionType} - Current LTP: ₹{currentLTP.toFixed(2)}
              </div>
            )}
          </>
        )}

        {/* Strategy-specific fields */}
        {formData.instrumentType === 'STRATEGY' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Strategy Type
            </label>
            <select
              value={formData.strategyType}
              onChange={(e) => setFormData({ ...formData, strategyType: e.target.value as any })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="IRON_CONDOR">Iron Condor</option>
              <option value="BULL_SPREAD">Bull Spread</option>
              <option value="BEAR_SPREAD">Bear Spread</option>
              <option value="STRADDLE">Straddle</option>
              <option value="STRANGLE">Strangle</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              Strategy legs will be constructed automatically based on current market conditions
            </p>
          </div>
        )}

        {/* Side and Quantity */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Side
            </label>
            <select
              value={formData.side}
              onChange={(e) => setFormData({ ...formData, side: e.target.value as 'BUY' | 'SELL' })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Quantity (Lots)
            </label>
            <input
              type="number"
              min="1"
              value={formData.quantity}
              onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 1 })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {formData.instrumentType === 'OPTIONS' ? 'Lots (1 lot = multiple contracts)' : 'Units'}
            </p>
          </div>
        </div>

        {/* Order Type and Price */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Order Type
            </label>
            <select
              value={formData.orderType}
              onChange={(e) => setFormData({ ...formData, orderType: e.target.value as 'MARKET' | 'LIMIT' })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="MARKET">Market</option>
              <option value="LIMIT">Limit</option>
            </select>
          </div>

          {formData.orderType === 'LIMIT' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Limit Price (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.price || ''}
                onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder={currentLTP ? currentLTP.toFixed(2) : "0.00"}
                required={formData.orderType === 'LIMIT'}
              />
              {currentLTP && (
                <p className="text-xs text-gray-500 mt-1">Current LTP: ₹{currentLTP.toFixed(2)}</p>
              )}
            </div>
          )}
        </div>

        {/* Stop Loss and Take Profit */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Stop Loss (₹)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={formData.stopLoss || ''}
              onChange={(e) => setFormData({ ...formData, stopLoss: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Optional"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Take Profit (₹)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={formData.takeProfit || ''}
              onChange={(e) => setFormData({ ...formData, takeProfit: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Optional"
            />
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading.portfolio}
          className={`w-full py-2 px-4 rounded-lg font-semibold text-white transition-colors flex items-center justify-center ${
            formData.side === 'BUY'
              ? 'bg-green-600 hover:bg-green-700 disabled:bg-green-400'
              : 'bg-red-600 hover:bg-red-700 disabled:bg-red-400'
          }`}
        >
          {loading.portfolio ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Executing...
            </>
          ) : (
            <>
              <Send className="w-4 h-4 mr-2" />
              {formData.side} {formData.instrumentType === 'OPTIONS' 
                ? `${formData.instrument} ${formData.strike}${formData.optionType}`
                : formData.instrumentType === 'STRATEGY'
                ? `${formData.strategyType.replace('_', ' ')}`
                : formData.instrument}
            </>
          )}
        </button>
      </form>
    </div>
  )
}
