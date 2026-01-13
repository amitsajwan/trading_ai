# How to Access MarketDataPage

## URL Path

The MarketDataPage is accessible at:

```
http://localhost:8888/market-data
```

## Navigation

### Via Sidebar
The page should be accessible through the sidebar navigation menu (if configured).

### Direct URL
You can navigate directly to:
- **Full URL**: `http://localhost:8888/market-data`
- **Relative path**: `/market-data`

## Starting the Development Server

To access the page, start the Vite development server:

```bash
cd dashboard/modular_ui
npm run dev
```

The server will start on **port 8888** (as configured in `vite.config.js`).

## What You'll See

On the MarketDataPage, you'll see:

1. **LiveTickDataWidgetV2** (new component with data layer)
   - Shows tick data for selected instrument
   - "Live" indicator when WebSocket connected
   - "Cached" indicator when using cached data
   - No flickering during WS transitions

2. **OptionsChainWidget**
3. **OrderFlowWidget**
4. **HistoricalDataWidget**

## Testing Checklist

Once you access the page, verify:

- [ ] Page loads without errors
- [ ] LiveTickDataWidgetV2 displays tick data
- [ ] Instrument selector works (BANKNIFTY, NIFTY, etc.)
- [ ] "Live" indicator shows when WS connected
- [ ] "Cached" indicator shows when WS disconnected
- [ ] No flickering when WS disconnects/reconnects
- [ ] Refresh button works
- [ ] Data updates in real-time (if WS connected)

## Route Configuration

The route is configured in `src/App.tsx`:

```tsx
<Route path="/market-data" element={<MarketDataPage />} />
```

## Other Available Routes

- `/` or `/dashboard` - DashboardPage
- `/market-data` - MarketDataPage (with LiveTickDataWidgetV2)
- `/trading` - TradingPage
- `/signals` - SignalsPage
- `/analytics` - AnalyticsPage
- `/news` - NewsPage
- `/settings` - SettingsPage
