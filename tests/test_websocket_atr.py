import websocket
import json
import time

messages_received = 0

def on_message(ws, message):
    global messages_received
    try:
        data = json.loads(message)
        channel = data.get('channel', '')
        if 'indicators' in channel:
            indicators_data = data.get('data', {})
            atr_14 = indicators_data.get('atr_14')
            atr_20 = indicators_data.get('atr_20')
            rsi_14 = indicators_data.get('rsi_14')
            print(f'📊 Indicators: ATR_14={atr_14}, ATR_20={atr_20}, RSI_14={rsi_14}')
            messages_received += 1
            if messages_received >= 3:  # Get a few messages then stop
                ws.close()
    except Exception as e:
        print('Error parsing message:', e)

def on_open(ws):
    print('WebSocket connected, waiting for indicators...')

if __name__ == '__main__':
    try:
        ws = websocket.WebSocketApp('ws://localhost:8889/ws', on_message=on_message, on_open=on_open)
        ws.run_forever(ping_interval=10, ping_timeout=5)
    except KeyboardInterrupt:
        print('Test stopped')
    except Exception as e:
        print('WebSocket test failed:', e)