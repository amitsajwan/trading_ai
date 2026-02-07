import tradingReducer, { fetchOrchestratorAnalysis } from './tradingSlice'

describe('tradingSlice - fetchOrchestratorAnalysis reducer', () => {
  it('should add a new orchestrator decision on fulfilled', () => {
    const initialState: any = {
      orchestratorDecisions: [],
      loading: { orchestrator: false },
      lastUpdated: null,
      error: null
    }

    const action: any = {
      type: fetchOrchestratorAnalysis.fulfilled.type,
      payload: { decision: 'BUY', confidence: 0.85, message: 'Test run' },
      meta: { arg: { instrument: 'BANKNIFTY' } }
    }

    const newState = tradingReducer(initialState, action)

    expect(newState.loading.orchestrator).toBe(false)
    expect(newState.orchestratorDecisions.length).toBe(1)
    expect(newState.orchestratorDecisions[0].final_decision).toBe('BUY')
    expect(newState.orchestratorDecisions[0].confidence).toBe(0.85)
    expect(newState.orchestratorDecisions[0].instrument).toBe('BANKNIFTY')
  })
})