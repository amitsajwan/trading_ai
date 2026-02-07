#!/usr/bin/env python3
"""Monitor raw_ticks channel and capture messages with their byte representation."""
import redis
import json
import time
import sys

def monitor_raw_ticks():
    # Connect to Redis with decode_responses=False to get raw bytes
    r = redis.Redis(host='localhost', port=6380, db=0, decode_responses=False)
    
    ps = r.pubsub()
    channel = "raw_ticks:BANKNIFTY26FEBFUT"
    ps.subscribe(channel)
    
    print(f"Subscribed to {channel}")
    print("Listening for messages... (Ctrl+C to stop)")
    print("="*80)
    
    message_count = 0
    try:
        for message in ps.listen():
            if message['type'] == 'message':
                message_count += 1
                data = message['data']
                
                print(f"\n[MESSAGE {message_count}]")
                print(f"Type: {type(data)}")
                print(f"Length: {len(data)}")
                
                # Show first 100 chars of raw bytes
                if isinstance(data, bytes):
                    print(f"Raw bytes (first 100): {data[:100]}")
                    print(f"Full repr: {repr(data)}")
                    
                    # Decode
                    try:
                        decoded = data.decode('utf-8')
                        print(f"Decoded (OK): {decoded[:100]}...")
                        
                        # Try to parse JSON
                        try:
                            parsed = json.loads(decoded)
                            print("✓ JSON parsed successfully")
                            print(f"  Keys: {list(parsed.keys())}")
                        except json.JSONDecodeError as je:
                            print(f"✗ JSON decode error: {je}")
                            print(f"  At char {je.colno}, line {je.lineno}")
                            print(f"  Showing chars around error position:")
                            start = max(0, je.pos - 20)
                            end = min(len(decoded), je.pos + 20)
                            print(f"  ...{repr(decoded[start:end])}...")
                    except UnicodeDecodeError as ue:
                        print(f"✗ UTF-8 decode error: {ue}")
                        decoded_replace = data.decode('utf-8', errors='replace')
                        print(f"Decoded (with replace): {decoded_replace[:100]}...")
                else:
                    print(f"Data: {data}")
                
                print("-"*80)
                
                if message_count >= 5:
                    print("\nReceived 5 messages, stopping")
                    break
    
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        ps.close()

if __name__ == "__main__":
    monitor_raw_ticks()
