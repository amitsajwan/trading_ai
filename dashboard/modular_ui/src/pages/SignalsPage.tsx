import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { RootState } from '../store'
import { fetchSignals, executeSignal, executeSignalWhenReady } from '../store/slices/tradingSlice'

export const SignalsPage: React.FC = () => {
  const dispatch = useDispatch()
  const { signals, loading } = useSelector((state: RootState) => state.trading)

  useEffect(() => {
    // DISABLED: No backend API calls to prevent errors
    // dispatch(fetchSignals() as any)
  }, [dispatch])

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">Signals</h2>

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 uppercase">
              <th className="py-2">Time</th>
              <th>Instrument</th>
              <th>Action</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Reasoning</th>
              <th>Options</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {signals && signals.length > 0 ? (
              signals.map((s) => (
                <tr key={s.signal_id || s.condition_id} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="py-3 align-top">{new Date(s.timestamp || s.created_at || Date.now()).toLocaleTimeString()}</td>
                  <td className="align-top">{s.instrument}</td>
                  <td className="align-top">{s.action}</td>
                  <td className="align-top">{s.status}</td>
                  <td className="align-top">{(Number(s.confidence) * 100).toFixed ? `${(Number(s.confidence) * 100).toFixed(1)}%` : String(s.confidence)}</td>
                  <td className="align-top">{s.reasoning || s.reason || '-'}</td>
                  <td className="align-top">
                    {s.metadata?.options_strategy_summary ? (
                      <div className="text-xs">
                        <div><strong>{s.metadata.options_strategy_summary.strategy_type}</strong></div>
                        <div>{s.metadata.options_strategy_summary.legs_count} legs • Exp: {s.metadata.options_strategy_summary.expiry}</div>
                      </div>
                    ) : '-'}
                  </td>
                  <td className="align-top">
                    <div className="flex items-center space-x-2">
                      <button className="px-2 py-1 bg-blue-600 text-white rounded text-xs" onClick={() => dispatch(executeSignal(s.signal_id || s.condition_id) as any)} disabled={s.status !== 'pending'}>
                        Execute Now
                      </button>
                      <button className="px-2 py-1 bg-gray-200 dark:bg-gray-700 text-xs rounded" onClick={() => dispatch(executeSignalWhenReady(s.signal_id || s.condition_id) as any)}>
                        Execute When Ready
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="py-6 text-center text-gray-500">No signals available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
