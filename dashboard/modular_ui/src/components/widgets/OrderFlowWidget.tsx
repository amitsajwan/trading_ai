import React, { useState, useEffect } from 'react'
import { RefreshCw, TrendingUp, TrendingDown, AlertCircle, Activity, BarChart3 } from 'lucide-react'
import { useSelector } from 'react-redux'
import { RootState } from '../../store'

interface OrderFlowWidgetProps {
  instrument?: string
}

export const OrderFlowWidget: React.FC<OrderFlowWidgetProps> = ({
  instrument = 'BANKNIFTY'
}) => {
  const [mockData, setMockData] = useState<any>(null)
  const { currentTick, orderFlow } = useSelector((state: RootState) => state.marketData)

  // Generate mock order flow data based on current tick
  useEffect(() => {
    if (currentTick) {
      // Generate mock order book around current price
      const basePrice = currentTick.last_price
      const mockBids = []
      const mockAsks = []
      let maxBidQty = 0
      let maxAskQty = 0

      // Generate bid side (buy orders)
      for (let i = 0; i < 10; i++) {
        const price = basePrice - (i * 5) - Math.random() * 10
        const quantity = Math.floor(Math.random() * 500) + 50
        mockBids.push({ price: Math.round(price * 100) / 100, quantity })
        maxBidQty = Math.max(maxBidQty, quantity)
      }

      // Generate ask side (sell orders)
      for (let i = 0; i < 10; i++) {
        const price = basePrice + (i * 5) + Math.random() * 10
        const quantity = Math.floor(Math.random() * 500) + 50
        mockAsks.push({ price: Math.round(price * 100) / 100, quantity })
        maxAskQty = Math.max(maxAskQty, quantity)
      }

      setMockData({
        bids: mockBids.sort((a, b) => b.price - a.price), // Sort bids descending
        asks: mockAsks.sort((a, b) => a.price - b.price), // Sort asks ascending
        maxBidQty,
        maxAskQty,
        lastUpdate: new Date().toISOString()
      })
    }
  }, [currentTick])

  const handleRefresh = () => {
    // Trigger data refresh by updating mock data
    if (currentTick) {
      const basePrice = currentTick.last_price
      const mockBids = []
      const mockAsks = []

      for (let i = 0; i < 10; i++) {
        const bidPrice = basePrice - (i * 5) - Math.random() * 10
        const askPrice = basePrice + (i * 5) + Math.random() * 10
        mockBids.push({ price: Math.round(bidPrice * 100) / 100, quantity: Math.floor(Math.random() * 500) + 50 })
        mockAsks.push({ price: Math.round(askPrice * 100) / 100, quantity: Math.floor(Math.random() * 500) + 50 })
      }

      setMockData({
        ...mockData,
        bids: mockBids.sort((a, b) => b.price - a.price),
        asks: mockAsks.sort((a, b) => a.price - b.price),
        lastUpdate: new Date().toISOString()
      })
    }
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

  if (!mockData) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Generating order flow data...</p>
          <p className="text-xs mt-2">Waiting for market data</p>
        </div>
      </div>
    )
  }

  // Use mock data
  const bids = mockData.bids || []
  const asks = mockData.asks || []
  const currentPrice = currentTick?.last_price || 0
  const totalBuyVolume = orderFlow?.total_buy_volume || orderFlow?.buy_volume || orderFlow?.total_depth_bid || 0
  const totalSellVolume = orderFlow?.total_sell_volume || orderFlow?.sell_volume || orderFlow?.total_depth_ask || 0
  const imbalance = orderFlow?.imbalance || 0
  const spread = orderFlow?.spread || 0

  // Extract bids/asks from depth_ladder if available
  const depthLadder = orderFlow?.depth_ladder || []
  const bidsFromLadder = depthLadder.map((level: any) => ({ price: level.bid_price, quantity: level.bid_qty })).filter((b: any) => b.price && b.quantity)
  const asksFromLadder = depthLadder.map((level: any) => ({ price: level.ask_price, quantity: level.ask_qty })).filter((a: any) => a.price && a.quantity)

  const allBids = bidsFromLadder.length > 0 ? bidsFromLadder : bids
  const allAsks = asksFromLadder.length > 0 ? asksFromLadder : asks

  const maxQuantity = Math.max(
    ...allBids.map((b: any) => b.quantity || b.qty || 0),
    ...allAsks.map((a: any) => a.quantity || a.qty || 0),
    1
  )

  if (!orderFlow || (!orderFlow.available && allBids.length === 0 && allAsks.length === 0 && Object.keys(depth).length === 0)) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>Order flow data not available</p>
          <p className="text-xs mt-2">This feature requires market depth data from the exchange</p>
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
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
          <Activity className="w-5 h-5 mr-2 text-primary-500" />
          Order Flow
        </h3>
        <button
          onClick={handleRefresh}
          disabled={loading.orderFlow}
          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading.orderFlow ? 'animate-spin' : ''}`} />
        </button>
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
        {(totalBuyVolume > 0 || totalSellVolume > 0) && (
          <>
            <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
              <div className="flex items-center mb-1">
                <TrendingUp className="w-4 h-4 text-green-600 mr-1" />
                <p className="text-xs font-semibold text-green-700 dark:text-green-400">Bid Depth</p>
              </div>
              <p className="text-lg font-bold text-green-600 dark:text-green-400">
                {totalBuyVolume > 1000000 ? `${(totalBuyVolume / 1000000).toFixed(2)}M` : totalBuyVolume.toLocaleString('en-IN')}
              </p>
            </div>
            <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
              <div className="flex items-center mb-1">
                <TrendingDown className="w-4 h-4 text-red-600 mr-1" />
                <p className="text-xs font-semibold text-red-700 dark:text-red-400">Ask Depth</p>
              </div>
              <p className="text-lg font-bold text-red-600 dark:text-red-400">
                {totalSellVolume > 1000000 ? `${(totalSellVolume / 1000000).toFixed(2)}M` : totalSellVolume.toLocaleString('en-IN')}
              </p>
            </div>
          </>
        )}
        {imbalance !== undefined && (
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
            <p className="text-xs font-semibold text-blue-700 dark:text-blue-400 mb-1">Imbalance</p>
            <p className={`text-lg font-bold ${imbalance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {imbalance >= 0 ? '+' : ''}{(imbalance * 100).toFixed(1)}%
            </p>
          </div>
        )}
        {spread !== undefined && (
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
            <p className="text-xs font-semibold text-purple-700 dark:text-purple-400 mb-1">Spread</p>
            <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
              {spread.toFixed(2)}%
            </p>
          </div>
        )}
      </div>

      {/* Market Depth */}
      {(allBids.length > 0 || allAsks.length > 0) && (
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Market Depth</h4>
            <div className="grid grid-cols-2 gap-4">
              {/* Asks (Sell Side) */}
              <div>
                <p className="text-xs text-red-600 dark:text-red-400 font-semibold mb-2">Ask Orders</p>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {allAsks.slice(0, 10).reverse().map((ask: any, index: number) =>
                    renderDepthLevel(
                      ask.price || ask.p || 0,
                      ask.quantity || ask.qty || 0,
                      false,
                      maxQuantity
                    )
                  )}
                </div>
              </div>

              {/* Bids (Buy Side) */}
              <div>
                <p className="text-xs text-green-600 dark:text-green-400 font-semibold mb-2">Bid Orders</p>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {allBids.slice(0, 10).map((bid: any, index: number) =>
                    renderDepthLevel(
                      bid.price || bid.p || 0,
                      bid.quantity || bid.qty || 0,
                      true,
                      maxQuantity
                    )
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Fallback message if no structured data but has raw data */}
      {allBids.length === 0 && allAsks.length === 0 && Object.keys(depth).length > 0 && (
        <div className="text-center text-gray-500 dark:text-gray-400 py-4">
          <p className="text-sm">Market depth data available but in raw format</p>
          <pre className="text-xs mt-2 text-left bg-gray-50 dark:bg-gray-700 p-2 rounded overflow-auto max-h-48">
            {JSON.stringify(orderFlow, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
