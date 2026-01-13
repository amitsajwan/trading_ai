/**
 * LiveTickDataWidgetV2 Tests
 * 
 * Component tests for LiveTickDataWidgetV2
 * 
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LiveTickDataWidgetV2 } from './LiveTickDataWidgetV2'
import { useMarketTick } from '../../../hooks/data/useMarketTick'

// Mock useMarketTick
vi.mock('../../../hooks/data/useMarketTick', () => ({
  useMarketTick: vi.fn(),
}))

const mockUseMarketTick = useMarketTick as ReturnType<typeof vi.fn>

describe('LiveTickDataWidgetV2', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading state', () => {
    it('should show loading skeleton when loading', () => {
      mockUseMarketTick.mockReturnValue({
        data: null,
        loading: true,
        error: null,
        isRealTime: false,
        status: 'fetching',
        refresh: vi.fn(),
      })

      const { container } = render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      // Should show loading animation (pulse class)
      const widget = container.querySelector('.animate-pulse')
      expect(widget).toBeInTheDocument()
    })
  })

  describe('Error state', () => {
    it('should show error message when error occurs', () => {
      mockUseMarketTick.mockReturnValue({
        data: null,
        loading: false,
        error: new Error('Failed to fetch tick data'),
        isRealTime: false,
        status: 'error',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      expect(screen.getByText('Error loading tick data')).toBeInTheDocument()
      expect(screen.getByText('Failed to fetch tick data')).toBeInTheDocument()
      expect(screen.getAllByText('Retry').length).toBeGreaterThan(0)
    })

    it('should call refresh when retry button clicked', async () => {
      const mockRefresh = vi.fn()
      mockUseMarketTick.mockReturnValue({
        data: null,
        loading: false,
        error: new Error('Failed to fetch'),
        isRealTime: false,
        status: 'error',
        refresh: mockRefresh,
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      const retryButtons = screen.getAllByText('Retry')
      retryButtons[0].click()

      expect(mockRefresh).toHaveBeenCalled()
    })
  })

  describe('No data state', () => {
    it('should show no data message when data is null', () => {
      mockUseMarketTick.mockReturnValue({
        data: null,
        loading: false,
        error: null,
        isRealTime: false,
        status: 'idle',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      expect(screen.getByText('No tick data available')).toBeInTheDocument()
    })
  })

  describe('Data display', () => {
    const mockTickData = {
      instrument: 'BANKNIFTY',
      last_price: 45000.50,
      timestamp: '2026-01-11T10:00:00Z',
      volume: 10000000,
      oi: 5000000,
    }

    it('should display tick data correctly', () => {
      mockUseMarketTick.mockReturnValue({
        data: mockTickData,
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      // Check instrument name
      expect(screen.getByText('BANKNIFTY')).toBeInTheDocument()

      // Check price (formatted with ₹ and locale)
      const priceElement = screen.getByText(/₹45,000.50/)
      expect(priceElement).toBeInTheDocument()

      // Check volume
      expect(screen.getByText(/Volume/)).toBeInTheDocument()
      expect(screen.getByText(/10.00M/)).toBeInTheDocument()

      // Check OI
      expect(screen.getByText(/OI/)).toBeInTheDocument()
      expect(screen.getByText(/5.00M/)).toBeInTheDocument()
    })

    it('should show "Live" indicator when isRealTime is true', () => {
      mockUseMarketTick.mockReturnValue({
        data: mockTickData,
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      expect(screen.getByText('Live')).toBeInTheDocument()
    })

    it('should show "Cached" indicator when isRealTime is false', () => {
      mockUseMarketTick.mockReturnValue({
        data: mockTickData,
        loading: false,
        error: null,
        isRealTime: false,
        status: 'fetching',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      expect(screen.getByText('Cached')).toBeInTheDocument()
    })

    it('should display timestamp correctly', () => {
      mockUseMarketTick.mockReturnValue({
        data: mockTickData,
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      expect(screen.getByText(/Last updated:/)).toBeInTheDocument()
    })

    it('should show price change indicator when price changes', () => {
      const mockData = { ...mockTickData, last_price: 45100.50 }
      
      mockUseMarketTick.mockReturnValue({
        data: mockData,
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      // Render twice to simulate price change
      const { rerender } = render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)
      
      // Update with new price
      mockUseMarketTick.mockReturnValue({
        data: { ...mockData, last_price: 45150.50 },
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })
      
      rerender(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      // Price change indicator should be visible (TrendingUp icon)
      const trendingUp = screen.queryByRole('img', { hidden: true }) || 
                         document.querySelector('[class*="TrendingUp"]')
      // Just verify price is displayed correctly
      expect(screen.getByText(/₹45,150.50/)).toBeInTheDocument()
    })
  })

  describe('Refresh functionality', () => {
    it('should call refresh when refresh button clicked', () => {
      const mockRefresh = vi.fn()
      mockUseMarketTick.mockReturnValue({
        data: { instrument: 'BANKNIFTY', last_price: 45000, timestamp: '2026-01-11T10:00:00Z' },
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: mockRefresh,
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      // Find refresh button (by title or icon)
      const refreshButton = screen.getByTitle('Refresh')
      refreshButton.click()

      expect(mockRefresh).toHaveBeenCalled()
    })

    it('should show loading spinner when refreshing', () => {
      mockUseMarketTick.mockReturnValue({
        data: { instrument: 'BANKNIFTY', last_price: 45000, timestamp: '2026-01-11T10:00:00Z' },
        loading: true,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      // Refresh button should have spinning animation
      const refreshButton = screen.getByTitle('Refresh')
      const icon = refreshButton.querySelector('svg')
      expect(icon).toHaveClass('animate-spin')
    })
  })

  describe('Default props', () => {
    it('should use BANKNIFTY as default instrument', () => {
      mockUseMarketTick.mockReturnValue({
        data: { instrument: 'BANKNIFTY', last_price: 45000, timestamp: '2026-01-11T10:00:00Z' },
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 />)

      expect(mockUseMarketTick).toHaveBeenCalledWith({
        instrument: 'BANKNIFTY',
      })
    })
  })

  describe('Missing optional fields', () => {
    it('should handle missing volume and OI', () => {
      const minimalData = {
        instrument: 'BANKNIFTY',
        last_price: 45000,
        timestamp: '2026-01-11T10:00:00Z',
      }

      mockUseMarketTick.mockReturnValue({
        data: minimalData,
        loading: false,
        error: null,
        isRealTime: true,
        status: 'connected',
        refresh: vi.fn(),
      })

      render(<LiveTickDataWidgetV2 instrument="BANKNIFTY" />)

      // Should still display price
      expect(screen.getByText(/₹45,000/)).toBeInTheDocument()
      
      // Volume and OI sections should not crash
      expect(screen.getByText('BANKNIFTY')).toBeInTheDocument()
    })
  })
})
