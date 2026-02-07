import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // Load environment variables from .env files and config.env
  const env = loadEnv(mode, process.cwd(), '')

  // Also load from config.env if it exists (fallback for additional config)
  try {
    const fs = require('fs')
    const path = require('path')
    const configPath = path.join(process.cwd(), 'config.env')
    if (fs.existsSync(configPath)) {
      const configContent = fs.readFileSync(configPath, 'utf8')
      configContent.split('\n').forEach(line => {
        const [key, ...valueParts] = line.split('=')
        if (key && key.startsWith('VITE_')) {
          const value = valueParts.join('=').trim()
          if (value && !env[key]) { // Only set if not already set by loadEnv
            env[key] = value
          }
        }
      })
    }
  } catch (e) {
    console.warn('Could not load config.env:', e.message)
  }

  // Ensure VITE_INSTRUMENT_SYMBOL has a default
  if (!env.VITE_INSTRUMENT_SYMBOL) {
    env.VITE_INSTRUMENT_SYMBOL = 'BANKNIFTY26JANFUT'
  }

  return {
  plugins: [react()],
  server: {
    port: 8888,
    strictPort: false, // Allow fallback to other ports
    host: true,
    hmr: {
      port: 8888, // Use same port as dev server to avoid conflicts
    },
    // Ensure SPA routing works properly
    historyApiFallback: {
      index: '/index.html'
    },
    proxy: {
      // Control mode API (UI needs this to choose LIVE vs BACKTEST subscriptions)
      // Route to Engine API because it is the source of truth for execution mode/run_id.
      '/api/control': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => path,
      },

      // Market data mappings: normalize UI paths to market_data API routes
      '/api/v1/options/chain': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1\/options\/chain/, '/api/v1/options/chain'),
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('Proxy error for options chain:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('Proxying options chain request:', req.url, '->', proxyReq.path);
          });
        }
      },
      '/api/market-data/options/chain': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/market-data\/options\/chain/, '/api/v1/options/chain'),
      },
      '/api/market-data/technical': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/market-data\/technical/, '/api/v1/technical/indicators'),
      },
      // Technical indicators endpoint (alternative path)
      '/api/technical-indicators': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Extract symbol from query string
            const url = new URL(req.url, 'http://localhost:8888')
            const symbol = url.searchParams.get('symbol') || env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT'
            // Rewrite the path to include the symbol
            proxyReq.path = `/api/v1/technical/indicators/${symbol}`
            // Preserve other query parameters if any
            url.searchParams.delete('symbol')
            const remainingQuery = url.search
            if (remainingQuery) {
              proxyReq.path += remainingQuery
            }
          })
        },
      },
      '/api/market-data': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            const url = new URL(req.url, 'http://localhost:8888')
            const pathname = url.pathname

            // If the request is exactly the collection root, map to overview endpoint
            if (pathname === '/api/market-data' || pathname === '/api/market-data/') {
              const symbol = url.searchParams.get('symbol') || env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT'
              proxyReq.path = `/api/v1/market/overview?symbol=${symbol}`
            } else {
              // Otherwise keep previous behavior so /tick, /ohlc, /depth etc map to /api/v1/market/*
              proxyReq.path = pathname.replace(/^\/api\/market-data/, '/api/v1/market') + url.search
            }
          })
        },
      },

      // News service
      '/api/news': {
        target: 'http://localhost:8005',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/news/, '/api/v1/news'),
      },

      // Engine-specific overrides (must come before general /api/engine route)
      '/api/engine/agents/status': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/agent-status',
      },
      '/api/engine/decision/latest': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/decision/latest',
      },
      '/api/engine/portfolio': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/portfolio',
      },
      '/api/orchestrator-decisions': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/orchestrator-decisions',
      },
      '/api/generate-strikes': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/generate-strikes',
      },
      '/api/trading/execute-when-ready': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/trading/execute-when-ready',
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('Proxy error for execute-when-ready:', err);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('Proxying execute-when-ready request:', req.url, '->', proxyReq.path);
          });
        }
      },
      // Trading cycle endpoint - proxy directly to Engine API analyze
      '/api/trading/cycle': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/analyze',
        configure: (proxy, _options) => {
          proxy.on('error', (err, req, res) => {
            console.log('Proxy error:', err)
          })
        },
      },
      // Trading signals endpoint
      '/api/trading/signals': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Extract instrument from query or default to env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT'
            const url = new URL(req.url, 'http://localhost:8888')
            const instrument = url.searchParams.get('instrument') || env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT'
            proxyReq.path = `/api/v1/signals/${instrument}`
          })
        },
      },
      // Trading positions endpoint - route to User API
      '/api/trading/positions': {
        target: 'http://localhost:8007',
        changeOrigin: true,
        rewrite: (path) => path,  // Keep path as-is: /api/trading/positions
      },
      // Trading endpoints - general catch-all (must come after specific routes)
      '/api/trading': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            const originalPath = proxyReq.path
            // Map /api/trading/* to Engine API endpoints
            if (originalPath.startsWith('/api/trading/signals')) {
              const url = new URL(req.url, 'http://localhost:8888')
              const instrument = url.searchParams.get('instrument') || env.VITE_INSTRUMENT_SYMBOL || 'BANKNIFTY26JANFUT'
              proxyReq.path = `/api/v1/signals/${instrument}`
            } else if (originalPath.startsWith('/api/trading/execute')) {
              proxyReq.path = originalPath.replace('/api/trading', '/api/v1')
            } else if (originalPath.startsWith('/api/trading/cycle')) {
              proxyReq.path = '/api/v1/analyze'
            }
          })
        },
      },
      // Engine service (general route - must come after specific routes)
      '/api/engine': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/engine/, '/api/v1'),
      },
      // Redis WebSocket Gateway proxy (if needed for CORS)
      // Note: UI connects directly to ws://localhost:8889/ws via VITE_WS_URL
      // This proxy is kept for potential future use but not currently needed
      '/ws': {
        target: 'ws://localhost:8889',
        ws: true,
        changeOrigin: true,
      },

      // Options strategy agent endpoint (served by Engine API)
      '/api/options-strategy-agent': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        rewrite: (path) => '/api/v1/options-strategy-agent',
      },
      // Agent status endpoint (served by Dashboard API)
      '/api/agent-status': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/agent-status/, '/api/agent-status'),
      },
      // Portfolio endpoint (served by User API)
      '/api/portfolio': {
        target: 'http://localhost:8007',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/portfolio/, '/api/portfolio'),
      },
      // Recent trades endpoint (served by User API)
      '/api/recent-trades': {
        target: 'http://localhost:8007',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/recent-trades/, '/api/recent-trades'),
      },

      // User service
      '/api/user': {
        target: 'http://localhost:8007',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/user/, '/api'),
      },
      
      // Analytics endpoints - now proxy to FastAPI backend
      '/api/analytics': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/analytics/, '/api/analytics'),
      },
      
      // Risk Management API (Layer 8) - proxy to FastAPI dashboard backend
      // FastAPI dashboard (app.py) runs on port 8000 (API backend only)
      // Vite proxies /api/risk/* requests to the FastAPI backend
      '/api/risk': {
        target: 'http://localhost:8000',  // FastAPI dashboard backend
        changeOrigin: true,
        rewrite: (path) => path,  // Keep path as-is: /api/risk/*
      },
      // Dashboard API endpoints - proxy to FastAPI backend
      '/api/health': {
        target: 'http://localhost:8000',  // FastAPI dashboard backend
        changeOrigin: true,
        rewrite: (path) => path,
      },
      // General dashboard API catch-all (must come after specific routes)
      '/api': {
        target: 'http://localhost:8000',  // FastAPI dashboard backend for unmatched /api/* routes
        changeOrigin: true,
        rewrite: (path) => path,
        // Only proxy if not already matched by other proxy rules
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            // Skip if already handled by other proxies
            const path = proxyReq.path;
            if (path.startsWith('/api/market-data') || 
                path.startsWith('/api/news') || 
                path.startsWith('/api/engine') || 
                path.startsWith('/api/trading') ||
                path.startsWith('/api/user') ||
                path.startsWith('/api/portfolio') ||
                path.startsWith('/api/agent-status') ||
                path.startsWith('/api/recent-trades') ||
                path.startsWith('/api/analytics')) {
              // These are handled by other proxies, don't proxy here
              return;
            }
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  };
})
