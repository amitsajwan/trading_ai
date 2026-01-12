// ========================================
// Generated API Types from OpenAPI Schema
// ========================================

// Auto-generated from FastAPI OpenAPI specification
// Generation Date: 2024-01-XX
// Source: /api/v1/openapi.json

// ========================================
// Core API Models
// ========================================

export interface SystemHealth {
  status: 'ok' | 'degraded' | 'error';
  timestamp: string;
  database: 'ok' | 'error';
  cache: 'ok' | 'error';
  market_open: boolean;
  instrument: string;
}

export interface TradingSignal {
  signal_id: string;
  condition_id?: string;
  instrument: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  timestamp: string;
  entry_price?: number;
  entry_price_source?: 'agent' | 'tick' | 'unknown';
  stop_loss?: number;
  take_profit?: number;
  reasoning?: string;
  execution_mode?: 'IMMEDIATE' | 'CONDITIONAL';
  parsed_conditions?: Array<{ indicator: string; operator: string; threshold: number }>;
  reason_hash?: string;
  indicator?: string;
  threshold?: number;
  additional_conditions?: Array<{ indicator: string; operator: string; threshold: number }>;
  status?: string;
  metadata?: Record<string, any>;
}

export interface MarketData {
  instrument: string;
  current_price: number;
  change_24h: number;
  change_percent_24h: number;
  volume_24h: number;
  high_24h: number;
  low_24h: number;
  vwap: number;
  timestamp: string;
  status: string;
}

export interface Position {
  id: string;
  instrument: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  current_price: number;
  pnl: number;
  pnl_percent: number;
  timestamp: string;
  status: 'open' | 'closed';
}

export interface ControlStatus {
  mode: string;
  database: string;
  balance: number;
}

export interface TradingStats {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  current_streak: number;
  best_streak: number;
  worst_streak: number;
}

// ========================================
// Request Models
// ========================================

export interface ModeSwitchRequest {
  mode: 'paper' | 'live';
  confirm?: boolean;
}

export interface BalanceUpdateRequest {
  balance: number;
}

// ========================================
// Response Models
// ========================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

export interface ModeSwitchResponse {
  success: boolean;
  mode: string;
  confirmation_required?: boolean;
}

export interface BalanceResponse {
  success: boolean;
  balance: number;
}

export interface SignalConditionCheck {
  conditions_met: boolean;
  can_execute: boolean;
  signal?: TradingSignal;
  reason?: string;
  error?: string;
}

export interface TradingCycleResult {
  success: boolean;
  decision?: string;
  confidence?: number;
  error?: string;
}

// ========================================
// Collection Response Models
// ========================================

export interface SignalsResponse {
  signals: TradingSignal[];
}

export interface PositionsResponse {
  positions: Position[];
}

export interface RecentTradesResponse {
  trades: any[]; // Using any for flexibility with existing data
}

// ========================================
// Error Models
// ========================================

export interface ErrorResponse {
  error: string;
  detail?: string;
  timestamp: string;
}

// ========================================
// Agent Status Models
// ========================================

export interface AgentSummary {
  signal: string;
  confidence: number;
  reasoning: string;
  metrics?: Record<string, any>;
}

export interface AgentStatus {
  status: string;
  last_update: string;
  signal: string;
  confidence: number;
  indicators: string[];
  summary: AgentSummary;
}

export interface AgentStatusResponse {
  agents: Record<string, AgentStatus>;
}

// ========================================
// Zod Validation Schemas (Runtime Validation)
// ========================================

import { z } from 'zod';

// Core schemas
export const SystemHealthSchema = z.object({
  status: z.enum(['ok', 'degraded', 'error']),
  timestamp: z.string(),
  database: z.enum(['ok', 'error']),
  cache: z.enum(['ok', 'error']),
  market_open: z.boolean(),
  instrument: z.string()
});

export const TradingSignalSchema = z.object({
  signal_id: z.string(),
  instrument: z.string(),
  action: z.enum(['BUY', 'SELL', 'HOLD']),
  confidence: z.number().min(0).max(1),
  timestamp: z.string(),
  entry_price: z.number().optional(),
  entry_price_source: z.enum(['agent','tick','unknown']).optional(),
  stop_loss: z.number().optional(),
  take_profit: z.number().optional(),
  reasoning: z.string().optional(),
  execution_mode: z.enum(['IMMEDIATE','CONDITIONAL']).optional(),
  parsed_conditions: z.array(z.object({ indicator: z.string(), operator: z.string(), threshold: z.number() })).optional(),
  reason_hash: z.string().optional(),
  indicator: z.string().optional(),
  threshold: z.number().optional(),
  additional_conditions: z.array(z.object({ indicator: z.string(), operator: z.string(), threshold: z.number() })).optional(),
  status: z.string().optional(),
  metadata: z.record(z.any()).optional()
});

export const MarketDataSchema = z.object({
  instrument: z.string(),
  current_price: z.number(),
  change_24h: z.number(),
  change_percent_24h: z.number(),
  volume_24h: z.number(),
  high_24h: z.number(),
  low_24h: z.number(),
  vwap: z.number(),
  timestamp: z.string(),
  status: z.string()
});

export const PositionSchema = z.object({
  id: z.string(),
  instrument: z.string(),
  side: z.enum(['BUY', 'SELL']),
  quantity: z.number(),
  entry_price: z.number(),
  current_price: z.number(),
  pnl: z.number(),
  pnl_percent: z.number(),
  timestamp: z.string(),
  status: z.enum(['open', 'closed'])
});

export const ControlStatusSchema = z.object({
  mode: z.string(),
  database: z.string(),
  balance: z.number()
});

// Request schemas
export const ModeSwitchRequestSchema = z.object({
  mode: z.enum(['paper', 'live']),
  confirm: z.boolean().optional()
});

export const BalanceUpdateRequestSchema = z.object({
  balance: z.number().positive()
});

// Response schemas
export const ApiResponseSchema = <T extends z.ZodType>(dataSchema: T) =>
  z.object({
    success: z.boolean(),
    data: dataSchema.optional(),
    error: z.string().optional(),
    timestamp: z.string()
  });

export const ModeSwitchResponseSchema = z.object({
  success: z.boolean(),
  mode: z.string(),
  confirmation_required: z.boolean().optional()
});

export const BalanceResponseSchema = z.object({
  success: z.boolean(),
  balance: z.number()
});

// ========================================
// Risk Management Types (Layer 8)
// ========================================

export interface PortfolioHeatSummary {
  account_balance: number
  active_positions: number
  total_portfolio_heat: number
  max_portfolio_heat: number
  available_heat: number
  total_max_loss: number
  total_current_pnl: number
  daily_pnl: number
  weekly_pnl: number
  daily_loss_pct: number
  weekly_loss_pct: number
  can_trade: boolean
}

export interface HeatUtilization {
  total_heat: number
  max_heat: number
  available_heat: number
  utilization_pct: number
  by_strategy: Record<string, number>
  by_instrument: Record<string, number>
}

export interface KellyCalculation {
  quantity: number
  kelly_pct: number
  win_probability: number
  risk_reward_ratio: number
  risk_amount: number
  historical_stats: {
    win_rate: number
    avg_win: number
    avg_loss: number
    risk_reward: number
  }
}

export interface ApprovalResult {
  decision: 'approved' | 'rejected' | 'reduced'
  reason: string
  approved_quantity: number
  original_quantity: number
  kelly_percentage: number
  risk_amount: number
  portfolio_heat_used: number
  portfolio_heat_available: number
  details: Record<string, any>
  timestamp: string
}

export interface ApprovalHistory {
  history: Array<{
    decision: string
    reason: string
    approved_quantity: number
    kelly_percentage: number
    risk_amount: number
    timestamp: string
  }>
  count: number
}

export interface ApprovalStats {
  total_reviews: number
  approved: number
  rejected: number
  reduced?: number
  approval_rate: number
  rejection_rate: number
  reduction_rate?: number
}

export const SignalConditionCheckSchema = z.object({
  conditions_met: z.boolean(),
  can_execute: z.boolean(),
  signal: TradingSignalSchema.optional(),
  reason: z.string().optional(),
  error: z.string().optional()
});

export const TradingCycleResultSchema = z.object({
  success: z.boolean(),
  decision: z.string().optional(),
  confidence: z.number().min(0).max(1).optional(),
  error: z.string().optional()
});

// ========================================
// API Client SDK (Standalone)
// ========================================

export class TradingAPIClient {
  private baseUrl: string;
  private apiKey?: string;

  constructor(baseUrl: string = '/api/v1', apiKey?: string) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    const response = await fetch(url, {
      ...options,
      headers
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Health endpoints
  async getHealth(): Promise<SystemHealth> {
    return this.request<SystemHealth>('/health');
  }

  async getSystemHealth(): Promise<SystemHealth> {
    return this.request<SystemHealth>('/system-health');
  }

  // Trading endpoints
  async getSignals(instrument?: string): Promise<TradingSignal[]> {
    const params = instrument ? `?instrument=${instrument}` : '';
    const response = await this.request<{ signals: TradingSignal[] }>(`/trading/signals${params}`);
    return response.signals;
  }

  async getPositions(): Promise<Position[]> {
    const response = await this.request<{ positions: Position[] }>('/trading/positions');
    return response.positions;
  }

  async getTradingStats(): Promise<TradingStats> {
    return this.request<TradingStats>('/trading/stats');
  }

  async runTradingCycle(): Promise<TradingCycleResult> {
    return this.request<TradingCycleResult>('/trading/cycle', {
      method: 'POST'
    });
  }

  async checkSignalConditions(signalId: string): Promise<SignalConditionCheck> {
    return this.request<SignalConditionCheck>(`/trading/conditions/${signalId}`);
  }

  // Market data endpoints
  async getMarketData(): Promise<MarketData> {
    return this.request<MarketData>('/market-data');
  }

  async getMarketDataBySymbol(symbol: string): Promise<MarketData> {
    return this.request<MarketData>(`/market/data/${symbol}`);
  }

  // Control endpoints
  async getControlStatus(): Promise<ControlStatus> {
    return this.request<ControlStatus>('/control/status');
  }

  async switchMode(request: ModeSwitchRequest): Promise<ModeSwitchResponse> {
    return this.request<ModeSwitchResponse>('/control/mode/switch', {
      method: 'POST',
      body: JSON.stringify(request)
    });
  }

  async setBalance(balance: number): Promise<BalanceResponse> {
    return this.request<BalanceResponse>('/control/balance/set', {
      method: 'POST',
      body: JSON.stringify({ balance })
    });
  }

  async getBalance(): Promise<{ balance: number }> {
    return this.request<{ balance: number }>('/control/balance');
  }
}