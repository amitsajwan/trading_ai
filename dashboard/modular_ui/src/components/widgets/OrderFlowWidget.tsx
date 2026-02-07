import React, { useState, useEffect, useMemo } from 'react'
import { RefreshCw, TrendingUp, TrendingDown, AlertCircle, Activity, BarChart3 } from 'lucide-react'
import { useSelector } from 'react-redux'
import { RootState } from '../../store'
import { useMarketDepth, MarketDepthData } from '../../hooks/data/useMarketDepth'

interface OrderFlowWidgetProps {
  instrument?: string
}

export const OrderFlowWidget: React.FC<OrderFlowWidgetProps> = ({
  instrument = 'BANKNIFTY'
}) => {
  const { data: depthData, loading, error, refresh } = useMarketDepth({ instrument })
  const { currentTick, orderFlow } = useSelector((state: RootState) => state.marketData)

  const handleRefresh = () => {
    refresh()
  }

  // Helper to render order book depth
  const renderDepthLevel = (
    price: number,
    quantity: number,
    isBid: boolean,
    maxQuantity: number
  ) => {
    const percentage = maxQuantity > 0 ? (quantity / maxQuantity) * 100 : 0
    const colorClass = isBid ? 'bg-green-500' : 'bg-red-500'

    return (
      <div key={price} className="flex items-center mb-1">
        <div className="w-20 text-xs text-gray-600 dark:text-gray-400 text-right mr-2">
          {price.toFixed(2)}
        </div>
        <div className="flex-1 relative h-6 bg-gray-100 dark:bg-gray-700 rounded">
          <div
            className={`absolute ${isBid ? 'right-0' : 'left-0'} top-0 h-full ${colorClass} rounded`}
            style={{ width: `${percentage}%` }}
          ></div>
          <div className="absolute inset-0 flex items-center justify-center text-xs font-semibold text-gray-900 dark:text-white">
            {(quantity / 1000).toFixed(1)}K
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  if (loading && !depthData) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Loading market depth data...</p>
          <p className="text-xs mt-2">Fetching real-time order book</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error && !depthData) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Error loading market depth</p>
          <p className="text-xs mt-2 text-red-500">{error?.message || 'Unknown error'}</p>
          <button
            onClick={handleRefresh}
            className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Use real market depth data
  const bids = depthData?.buy || []
  const asks = depthData?.sell || []
  const currentPrice = currentTick?.last_price || 0

  // Calculate totals from real depth data
  const totalBuyVolume = bids.reduce((sum, level) => sum + level.quantity, 0)
  const totalSellVolume = asks.reduce((sum, level) => sum + level.quantity, 0)
  const imbalance = totalBuyVolume > 0 && totalSellVolume > 0 ? (totalBuyVolume - totalSellVolume) / (totalBuyVolume + totalSellVolume) : 0

  // Calculate spread (difference between best bid and best ask)
  const bestBid = bids.length > 0 ? Math.max(...bids.map(b => b.price)) : 0
  const bestAsk = asks.length > 0 ? Math.min(...asks.map(a => a.price)) : 0
  const spread = bestBid > 0 && bestAsk > 0 ? bestAsk - bestBid : 0

  // Calculate max quantity for visualization
  const maxQuantity = Math.max(
    ...bids.map(b => b.quantity),
    ...asks.map(a => a.quantity),
    1
  )

  // Check if we have valid depth data
  if (!depthData || (bids.length === 0 && asks.length === 0)) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Market depth data not available</p>
          <p className="text-xs mt-2">No order book data received from exchange</p>
          <button
            onClick={handleRefresh}
            className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <Activity className="w-5 h-5 mr-2 text-primary-500" />
            Order Flow - Real Market Depth
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Live order book for {instrument}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 text-xs text-green-600 dark:text-green-400">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span>Live</span>
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Current Price and Volume Summary */}
      {currentPrice > 0 && (
        <div className="mb-4 p-3 bg-primary-50 dark:bg-primary-900/20 rounded-lg">
          <div className="text-center">
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Current Price</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              ₹{currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
        </div>
      )}

      {/* Volume Analysis and Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
          <div className="flex items-center mb-1">
            <TrendingUp className="w-4 h-4 text-green-600 mr-1" />
            <p className="text-xs font-semibold text-green-700 dark:text-green-400">Bid Depth</p>
          </div>
          <p className="text-lg font-bold text-green-600 dark:text-green-400">
            {totalBuyVolume > 1000000 ? `${(totalBuyVolume / 1000000).toFixed(2)}M` : totalBuyVolume.toLocaleString('en-IN')}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">{bids.length} levels</p>
        </div>
        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
          <div className="flex items-center mb-1">
            <TrendingDown className="w-4 h-4 text-red-600 mr-1" />
            <p className="text-xs font-semibold text-red-700 dark:text-red-400">Ask Depth</p>
          </div>
          <p className="text-lg font-bold text-red-600 dark:text-red-400">
            {totalSellVolume > 1000000 ? `${(totalSellVolume / 1000000).toFixed(2)}M` : totalSellVolume.toLocaleString('en-IN')}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">{asks.length} levels</p>
        </div>
        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
          <p className="text-xs font-semibold text-blue-700 dark:text-blue-400 mb-1">Order Imbalance</p>
          <p className={`text-lg font-bold ${imbalance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {imbalance >= 0 ? '+' : ''}{(imbalance * 100).toFixed(1)}%
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">
            {imbalance >= 0 ? 'Buy pressure' : 'Sell pressure'}
          </p>
        </div>
        <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
          <p className="text-xs font-semibold text-purple-700 dark:text-purple-400 mb-1">Bid-Ask Spread</p>
          <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
            ₹{spread.toFixed(2)}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">
            {bestBid.toFixed(2)} - {bestAsk.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Market Depth Visualization */}
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Order Book Depth</h4>
          <div className="grid grid-cols-2 gap-4">
            {/* Asks (Sell Side) - Right side */}
            <div>
              <p className="text-xs text-red-600 dark:text-red-400 font-semibold mb-2 flex items-center">
                <TrendingDown className="w-3 h-3 mr-1" />
                Sell Orders (Asks) - {asks.length} levels
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {asks.slice(0, 10).map((ask, index: number) =>
                  renderDepthLevel(ask.price, ask.quantity, false, maxQuantity)
                )}
              </div>
            </div>

            {/* Bids (Buy Side) - Left side */}
            <div>
              <p className="text-xs text-green-600 dark:text-green-400 font-semibold mb-2 flex items-center">
                <TrendingUp className="w-3 h-3 mr-1" />
                Buy Orders (Bids) - {bids.length} levels
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {bids.slice(0, 10).map((bid, index: number) =>
                  renderDepthLevel(bid.price, bid.quantity, true, maxQuantity)
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Data freshness indicator */}
        <div className="text-xs text-gray-500 dark:text-gray-400 text-right pt-2 border-t border-gray-200 dark:border-gray-600">
          Last updated: {depthData?.timestamp ? new Date(depthData.timestamp).toLocaleTimeString() : 'Unknown'}
        </div>
      </div>
    </div>
  )
}
