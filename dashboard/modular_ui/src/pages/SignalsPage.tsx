import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { fetchSignals, executeSignal, executeSignalWhenReady } from '../store/slices/tradingSlice'

const renderConditionStatus = (condition: any) => {
  const { indicator, operator, threshold, current_value } = condition
  let status = 'waiting'
  let statusText = 'Waiting'
  let statusColor = 'text-yellow-600'

  if (current_value !== undefined) {
    let met = false
    switch (operator) {
      case '>':
        met = current_value > threshold
        break
      case '<':
        met = current_value < threshold
        break
      case '>=':
        met = current_value >= threshold
        break
      case '<=':
        met = current_value <= threshold
        break
      case '==':
      case 'EQUALS':
        met = current_value === threshold
        break
      case 'BETWEEN':
        met = Array.isArray(threshold) && current_value >= threshold[0] && current_value <= threshold[1]
        break
      default:
        met = false
    }

    if (met) {
      status = 'met'
      statusText = '✓ Met'
      statusColor = 'text-green-600'
    } else {
      status = 'not_met'
      statusText = '✗ Not met'
      statusColor = 'text-red-600'
    }
  }

  return (
    <div className="text-xs">
      <div className="font-medium">{indicator.replace('_', ' ').toUpperCase()}</div>
      <div className={`${statusColor} font-medium`}>{statusText}</div>
      <div className="text-gray-500">
        {operator === 'BETWEEN' && Array.isArray(threshold)
          ? `${threshold[0]} - ${threshold[1]}`
          : `${operator} ${threshold}`
        }
      </div>
      {current_value !== undefined && (
        <div className="text-gray-700 font-mono">
          Current: {typeof current_value === 'number' ? current_value.toFixed(2) : current_value}
        </div>
      )}
    </div>
  )
}

const renderConditionsColumn = (signal: any) => {
  if (signal.execution_mode === 'IMMEDIATE') {
    return <div className="text-xs text-green-600">Ready to execute</div>
  }

  if (signal.parsed_conditions && signal.parsed_conditions.length > 0) {
    return (
      <div className="space-y-1">
        {signal.parsed_conditions.map((condition: any, idx: number) => (
          <div key={idx} className="border-b border-gray-100 dark:border-gray-700 last:border-b-0 pb-1 last:pb-0">
            {renderConditionStatus(condition)}
          </div>
        ))}
      </div>
    )
  }

  return <div className="text-xs text-gray-500">-</div>
}

export const SignalsPage: React.FC = () => {
  const dispatch = useDispatch()
  const { signals, loading } = useSelector((state: RootState) => state.trading)

  useEffect(() => {
    // Load signals when on Signals page
    dispatch(fetchSignals() as any)
  }, [dispatch])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-semibold">Signals</h2>
        <div className="text-sm text-gray-600 dark:text-gray-400">
          5-minute deduplication • ATR-based risk management
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase">
              <th className="py-2">Time</th>
              <th>Instrument</th>
              <th>Action</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Conditions</th>
              <th>Risk Management</th>
              <th>Position Sizing</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {signals && signals.length > 0 ? (
              signals.map((s) => (
                <tr key={s.signal_id || s.condition_id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="py-3 align-top">{new Date(s.timestamp || s.created_at || Date.now()).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}</td>
                  <td className="align-top">{s.instrument}</td>
                  <td className="align-top">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      s.action?.toUpperCase() === 'BUY' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                      s.action?.toUpperCase() === 'SELL' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                      'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                    }`}>
                      {s.action}
                    </span>
                  </td>
                  <td className="align-top">
                    <span className={`px-2 py-1 rounded text-xs ${
                      s.status === 'pending' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                      s.status === 'monitoring' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                      s.status === 'triggered' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                      s.status === 'executed' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                      'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                    }`}>
                      {s.status}
                    </span>
                  </td>
                  <td className="align-top">
                    <div className="text-sm font-medium">
                      {(Number(s.confidence) * 100).toFixed ? `${(Number(s.confidence) * 100).toFixed(1)}%` : String(s.confidence)}
                    </div>
                    {s.details?.position_size_suggestion && (
                      <div className="text-xs text-gray-500">
                        Size: {(s.details.position_size_suggestion.size_multiplier * 100).toFixed(0)}%
                      </div>
                    )}
                  </td>
                  <td className="align-top">
                    {renderConditionsColumn(s)}
                  </td>
                  <td className="align-top text-xs">
                    {s.details?.stop_loss && s.details?.take_profit ? (
                      <div>
                        <div>SL: {Number(s.details.stop_loss).toFixed(2)}</div>
                        <div>TP: {Number(s.details.take_profit).toFixed(2)}</div>
                        {s.details?.risk_reward_ratio && (
                          <div className="text-green-600">R:R {s.details.risk_reward_ratio.toFixed(1)}</div>
                        )}
                      </div>
                    ) : s.reasoning || s.reason || '-'}
                  </td>
                  <td className="align-top text-xs">
                    {s.details?.position_size_suggestion ? (
                      <div>
                        <div>Risk: {(s.details.position_size_suggestion.risk_amount_pct * 100).toFixed(1)}%</div>
                        <div>Mult: {s.details.position_size_suggestion.size_multiplier}x</div>
                        <div className={`font-medium ${
                          s.details.position_size_suggestion.size_multiplier >= 1.5 ? 'text-green-600' :
                          s.details.position_size_suggestion.size_multiplier >= 1.0 ? 'text-yellow-600' :
                          'text-red-600'
                        }`}>
                          {s.details.position_size_suggestion.size_multiplier >= 1.5 ? 'Aggressive' :
                           s.details.position_size_suggestion.size_multiplier >= 1.0 ? 'Normal' : 'Conservative'}
                        </div>
                      </div>
                    ) : s.metadata?.options_strategy_summary ? (
                      <div>
                        <div><strong>{s.metadata.options_strategy_summary.strategy_type}</strong></div>
                        <div>{s.metadata.options_strategy_summary.legs_count} legs • Exp: {s.metadata.options_strategy_summary.expiry}</div>
                      </div>
                    ) : '-'}
                  </td>
                  <td className="align-top">
                    <div className="flex items-center space-x-2">
                      {s.execution_mode === 'IMMEDIATE' ? (
                        <button className="px-2 py-1 bg-green-600 text-white rounded text-xs" onClick={() => dispatch(executeSignalWhenReady(s.signal_id || s.condition_id) as any)} disabled={s.status !== 'pending'}>
                          Execute Now
                        </button>
                      ) : (
                        <button className={`px-2 py-1 text-white rounded text-xs ${
                          s.parsed_conditions?.every((c: any) => c.current_value !== undefined &&
                            (() => {
                              const { operator, threshold, current_value } = c
                              switch (operator) {
                                case '>': return current_value > threshold
                                case '<': return current_value < threshold
                                case '>=': return current_value >= threshold
                                case '<=': return current_value <= threshold
                                case '==':
                                case 'EQUALS': return current_value === threshold
                                case 'BETWEEN': return Array.isArray(threshold) && current_value >= threshold[0] && current_value <= threshold[1]
                                default: return false
                              }
                            })()
                          ) ? 'bg-green-600' : 'bg-blue-600'
                        }`} onClick={() => dispatch(executeSignalWhenReady(s.signal_id || s.condition_id) as any)} disabled={s.status !== 'pending'}>
                          {s.status === 'monitoring' ? 'Monitoring...' : 'Execute When Ready'}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={9} className="py-6 text-center text-gray-500">No signals available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
