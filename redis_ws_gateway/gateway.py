"""Redis WebSocket Gateway - Dumb forwarder from Redis pub/sub to WebSocket clients.

This gateway:
1. Accepts WebSocket connections from UI
2. Authenticates connections (JWT/API key)
3. Subscribes to Redis pub/sub channels on behalf of clients
4. Forwards Redis messages to WebSocket clients
5. Enforces guardrails (max channels, ACL, rate limiting)

CRITICAL: Gateway must be DUMB - no business logic, only forward.
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any, List
from uuid import uuid4

import redis.asyncio as redis_async
from pymongo import MongoClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "zerodha_trading")
GATEWAY_PORT = int(os.getenv("REDIS_WS_GATEWAY_PORT", "8889"))
GATEWAY_HOST = os.getenv("REDIS_WS_GATEWAY_HOST", "0.0.0.0")

# Guardrails
MAX_CHANNELS_PER_CLIENT = int(os.getenv("MAX_CHANNELS_PER_CLIENT", "50"))
MAX_WILDCARD_SUBSCRIPTIONS = int(os.getenv("MAX_WILDCARD_SUBSCRIPTIONS", "10"))  # Increased for signal testing
MAX_MESSAGES_PER_SECOND = int(os.getenv("MAX_MESSAGES_PER_SECOND", "1000"))

# Authentication (simple API key for now, can be extended to JWT)
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
API_KEY = os.getenv("GATEWAY_API_KEY", "")

# Channel ACL - role-based access control
# Format: role -> list of allowed channel prefixes
CHANNEL_ACL: Dict[str, List[str]] = {
    "user": [
        # Type-specific tick channels (INDEX, FUT, OPT)
        "market:tick:*:INDEX",
        "market:tick:*:FUT",
        "market:tick:*:OPT",
        # Type-specific indicator channels
        "indicators:*:INDEX",
        "indicators:*:FUT",
        "indicators:*:OPT",
        # Options chain and market depth data
        "market:options:*",
        "market:options",
        "market:depth:*",
        "market:depth",
        # OHLC data for charting
        "market:ohlc:*",
        "market:ohlc",
        # Allow basic engine channels for UI consumers in development (signals and decisions)
        "engine:signal:*",
        "engine:signal",
        "signals:*",
        "trading:signals:*",
        "market:signals:*",
        "engine:decision:*",
        "engine:decision",
        # Agent response and orchestrator decision channels
        "engine:agent",
        "engine:agent:*",
        "agent:*",
        "engine:orchestrator",
        "engine:orchestrator:*",
    ],
    "admin": [
        # Type-specific tick channels
        "market:tick:*:INDEX",
        "market:tick:*:FUT",
        "market:tick:*:OPT",
        # Type-specific indicator channels
        "indicators:*:INDEX",
        "indicators:*:FUT",
        "indicators:*:OPT",
        # Engine channels
        "engine:signal:*",
        "engine:signal",
        "signals:*",
        "trading:signals:*",
        "market:signals:*",
        "engine:decision:*",
        "engine:decision",
    ],
    "internal": [
        "*",  # All channels
    ],
}

# Default role if not specified
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "user")

# Global sequence counter for messages
_sequence_counter = 0
_sequence_lock = asyncio.Lock()


async def get_next_sequence() -> int:
    """Get next sequence ID (thread-safe)."""
    global _sequence_counter
    async with _sequence_lock:
        _sequence_counter += 1
        return _sequence_counter


# Pydantic models
class SubscribeRequest(BaseModel):
    """Subscribe request from client."""
    action: str = Field(..., description="Action: 'subscribe' or 'unsubscribe'")
    channels: List[str] = Field(..., description="List of channel names or patterns")
    requestId: Optional[str] = Field(None, description="Optional request ID for response matching")


class ClientConnection:
    """Represents a WebSocket client connection."""
    
    def __init__(self, websocket: WebSocket, client_id: str, role: str = DEFAULT_ROLE):
        self.websocket = websocket
        self.client_id = client_id
        self.role = role
        self.subscribed_channels: Set[str] = set()
        self.subscribed_patterns: Set[str] = set()
        self.message_count = 0
        self.last_message_time = time.time()
        self.connected_at = datetime.now(timezone.utc)
    
    def can_subscribe(self, channel: str) -> bool:
        """Check if client can subscribe to channel based on ACL."""
        allowed_prefixes = CHANNEL_ACL.get(self.role, CHANNEL_ACL[DEFAULT_ROLE])
        
        # Check if channel matches any allowed prefix
        for prefix in allowed_prefixes:
            if prefix == "*":
                return True
            # Exact match
            if channel == prefix:
                return True
            # Prefix match (for non-wildcard prefixes)
            if "*" not in prefix and channel.startswith(prefix):
                return True
            # Pattern matching for wildcards (e.g., "market:tick:*:INDEX" matches "market:tick:BANKNIFTY:INDEX")
            if "*" in prefix:
                # Convert Redis pattern to regex: * -> .*, ? -> .
                pattern = prefix.replace("*", ".*").replace("?", ".")
                import re
                if re.match(pattern + "$", channel):
                    return True
        
        return False
    
    def is_wildcard(self, channel: str) -> bool:
        """Check if channel is a wildcard pattern."""
        return "*" in channel or "?" in channel
    
    def get_subscription_count(self) -> int:
        """Get total subscription count (channels + patterns)."""
        return len(self.subscribed_channels) + len(self.subscribed_patterns)
    
    def get_wildcard_count(self) -> int:
        """Get wildcard subscription count."""
        return len(self.subscribed_patterns)


class RedisWebSocketGateway:
    """Redis WebSocket Gateway - Dumb forwarder."""
    
    def __init__(self):
        self.app = FastAPI(title="Redis WebSocket Gateway", version="1.0.0")
        self.redis_client: Optional[redis_async.Redis] = None
        self.redis_pubsub: Optional[Any] = None
        self.mongo_client: Optional[MongoClient] = None
        self.clients: Dict[str, ClientConnection] = {}
        self.channel_subscribers: Dict[str, Set[str]] = defaultdict(set)  # channel -> set of client_ids
        self.pattern_subscribers: Dict[str, Set[str]] = defaultdict(set)  # pattern -> set of client_ids
        self.redis_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self.app.websocket("/ws")(self.websocket_endpoint)
        self.app.get("/health")(self.health_check)
        self.app.get("/stats")(self.get_stats)
    
    async def authenticate(self, token: Optional[str] = None) -> str:
        """Authenticate client and return role."""
        if not REQUIRE_AUTH:
            return DEFAULT_ROLE
        
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Simple API key check (can be extended to JWT)
        if token == API_KEY:
            return "admin"  # API key grants admin access
        
        # For now, any token grants user access (can be extended)
        return DEFAULT_ROLE
    
    async def websocket_endpoint(self, websocket: WebSocket, token: Optional[str] = Query(None)):
        """WebSocket endpoint for client connections."""
        client_id = str(uuid4())
        
        try:
            await websocket.accept()
            
            # Authenticate
            try:
                role = await self.authenticate(token)
            except HTTPException:
                await websocket.close(code=1008, reason="Authentication failed")
                return
            
            # Create client connection
            client = ClientConnection(websocket, client_id, role)
            self.clients[client_id] = client
            
            logger.info(f"Client connected: {client_id} (role: {role})")
            
            # Send welcome message
            await self.send_message(client, {
                "type": "connected",
                "clientId": client_id,
                "role": role,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            # Handle messages from client
            while True:
                try:
                    data = await websocket.receive_text()
                    await self.handle_client_message(client, data)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error handling client message: {e}", exc_info=True)
                    await self.send_error(client, str(e))
        
        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        finally:
            # Cleanup
            await self.disconnect_client(client_id)
    
    async def handle_client_message(self, client: ClientConnection, message: str):
        """Handle message from client."""
        try:
            data = json.loads(message)
            action = data.get("action")

            logger.info(f"WebSocket message from {client.client_id}: {action}, data: {data}")

            if action == "subscribe":
                channels = data.get("channels", [])
                logger.info(f"Client {client.client_id} subscribing to channels: {channels}")
                await self.handle_subscribe(client, channels, data.get("requestId"))
            
            elif action == "unsubscribe":
                channels = data.get("channels", [])
                await self.handle_unsubscribe(client, channels, data.get("requestId"))
            
            elif action == "ping":
                await self.send_message(client, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "requestId": data.get("requestId"),
                })
            
            else:
                await self.send_error(client, f"Unknown action: {action}", data.get("requestId"))
        
        except json.JSONDecodeError:
            await self.send_error(client, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling client message: {e}", exc_info=True)
            await self.send_error(client, str(e))
    
    async def handle_subscribe(self, client: ClientConnection, channels: List[str], request_id: Optional[str]):
        """Handle subscribe request."""
        logger.info(f"Processing subscribe request for {len(channels)} channels: {channels}")
        subscribed = []
        errors = []
        
        for channel in channels:
            # Check guardrails
            if client.get_subscription_count() >= MAX_CHANNELS_PER_CLIENT:
                errors.append(f"Max channels exceeded ({MAX_CHANNELS_PER_CLIENT})")
                break
            
            if client.is_wildcard(channel):
                if client.get_wildcard_count() >= MAX_WILDCARD_SUBSCRIPTIONS:
                    errors.append(f"Max wildcard subscriptions exceeded ({MAX_WILDCARD_SUBSCRIPTIONS})")
                    continue
            
            # Check ACL
            if not client.can_subscribe(channel):
                errors.append(f"Access denied to channel: {channel}")
                continue
            
            # Subscribe
            if client.is_wildcard(channel):
                client.subscribed_patterns.add(channel)
                self.pattern_subscribers[channel].add(client.client_id)
            else:
                client.subscribed_channels.add(channel)
                self.channel_subscribers[channel].add(client.client_id)
            
            subscribed.append(channel)

            # Replay last decision if applicable
            if not client.is_wildcard(channel) and (channel.startswith("engine:decision") or channel.startswith("engine:agent")):
                asyncio.create_task(self.replay_last_decision(client, channel))
        
        # Update Redis subscriptions if needed
        if subscribed and self.redis_pubsub:
            await self.update_redis_subscriptions()
        
        # Send response
        await self.send_message(client, {
            "type": "subscribed",
            "channels": subscribed,
            "errors": errors,
            "requestId": request_id,
        })
    
    async def handle_unsubscribe(self, client: ClientConnection, channels: List[str], request_id: Optional[str]):
        """Handle unsubscribe request."""
        unsubscribed = []
        
        for channel in channels:
            if channel in client.subscribed_channels:
                client.subscribed_channels.remove(channel)
                self.channel_subscribers[channel].discard(client.client_id)
                unsubscribed.append(channel)
            
            if channel in client.subscribed_patterns:
                client.subscribed_patterns.remove(channel)
                self.pattern_subscribers[channel].discard(client.client_id)
                unsubscribed.append(channel)
        
        # Update Redis subscriptions if needed
        if unsubscribed and self.redis_pubsub:
            await self.update_redis_subscriptions()
        
        # Send response
        await self.send_message(client, {
            "type": "unsubscribed",
            "channels": unsubscribed,
            "requestId": request_id,
        })

    async def replay_last_decision(self, client: ClientConnection, channel: str):
        """Replay last decision from Redis or MongoDB upon subscription."""
        if not self.redis_client:
            return

        try:
            # 1. Try Redis first (fastest)
            # Use channel name + :latest as the key
            redis_key = f"{channel}:latest"
            last_decision_raw = await self.redis_client.get(redis_key)
            
            if last_decision_raw:
                logger.info(f"Replaying last decision for {channel} from Redis")
                decision_data = json.loads(last_decision_raw)
                await self.send_message(client, {
                    "type": "data",
                    "channel": channel,
                    "data": decision_data,
                    "replayed": True,
                    "source": "redis"
                })
                return

            # 2. Fallback to MongoDB if not in Redis
            if self.mongo_client:
                logger.info(f"Last decision for {channel} not in Redis, checking MongoDB")
                db = self.mongo_client[MONGODB_DATABASE]
                
                # Extract instrument from channel (e.g., "engine:decision:BANKNIFTY" -> "BANKNIFTY")
                instrument = None
                if channel.startswith("engine:decision:"):
                    instrument = channel.replace("engine:decision:", "")
                elif channel.startswith("engine:agent:"):
                    instrument = channel.replace("engine:agent:", "")
                
                if instrument:
                    # Query MongoDB for the latest decision for this instrument
                    # For engine:decision, check 'signals' or 'orchestrator_health' or 'agent_discussions'
                    # Based on engine_module/api_service.py, agent decisions are in 'agent_discussions'
                    # And signals are in 'signals'
                    
                    collection_name = "agent_discussions" if "agent" in channel else "signals"
                    collection = db[collection_name]
                    
                    last_doc = collection.find_one(
                        {"instrument": instrument.upper()},
                        sort=[("timestamp", -1), ("created_at", -1)]
                    )
                    
                    if last_doc:
                        # Convert ObjectId and datetime to string
                        if "_id" in last_doc:
                            last_doc["_id"] = str(last_doc["_id"])
                        for k, v in last_doc.items():
                            if isinstance(v, datetime):
                                last_doc[k] = v.isoformat()
                        
                        logger.info(f"Replaying last decision for {channel} from MongoDB ({collection_name})")
                        await self.send_message(client, {
                            "type": "data",
                            "channel": channel,
                            "data": last_doc,
                            "replayed": True,
                            "source": "mongodb"
                        })
                        return

        except Exception as e:
            logger.warning(f"Error replaying last decision for {channel}: {e}", exc_info=True)
    
    async def update_redis_subscriptions(self):
        """Update Redis pub/sub subscriptions based on all client subscriptions."""
        if not self.redis_pubsub:
            return
        
        # Collect all unique channels and patterns from all clients
        all_channels = set()
        all_patterns = set()
        
        for client in self.clients.values():
            all_channels.update(client.subscribed_channels)
            all_patterns.update(client.subscribed_patterns)
        
        # Track what we're currently subscribed to (we'll maintain this)
        # For simplicity, we subscribe to all channels/patterns that any client wants
        # Redis pubsub allows multiple subscriptions to the same channel/pattern
        
        # Subscribe to all channels (Redis handles duplicates)
        for channel in all_channels:
            try:
                await self.redis_pubsub.subscribe(channel)
            except Exception as e:
                logger.warning(f"Failed to subscribe to channel {channel}: {e}")
        
        # Subscribe to all patterns (Redis handles duplicates)
        for pattern in all_patterns:
            try:
                await self.redis_pubsub.psubscribe(pattern)
            except Exception as e:
                logger.warning(f"Failed to subscribe to pattern {pattern}: {e}")
    
    async def send_message(self, client: ClientConnection, data: Dict[str, Any]):
        """Send message to client with sequence ID."""
        try:
            seq = await get_next_sequence()
            message = {
                **data,
                "seq": seq,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            await client.websocket.send_text(json.dumps(message))
            client.message_count += 1
            client.last_message_time = time.time()
        
        except Exception as e:
            logger.error(f"Error sending message to client {client.client_id}: {e}", exc_info=True)
    
    async def send_error(self, client: ClientConnection, error: str, request_id: Optional[str] = None):
        """Send error message to client."""
        await self.send_message(client, {
            "type": "error",
            "error": error,
            "requestId": request_id,
        })
    
    async def disconnect_client(self, client_id: str):
        """Disconnect client and cleanup."""
        if client_id not in self.clients:
            return
        
        client = self.clients[client_id]
        
        # Remove from subscriptions
        for channel in list(client.subscribed_channels):
            self.channel_subscribers[channel].discard(client_id)
        
        for pattern in list(client.subscribed_patterns):
            self.pattern_subscribers[pattern].discard(client_id)
        
        # Close WebSocket
        try:
            await client.websocket.close()
        except Exception:
            pass
        
        # Remove client
        del self.clients[client_id]
        
        logger.info(f"Client disconnected: {client_id}")
        
        # Update Redis subscriptions
        if self.redis_pubsub:
            await self.update_redis_subscriptions()
    
    async def start_redis_subscriber(self):
        """Start Redis pub/sub subscriber."""
        try:
            self.redis_client = redis_async.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info(f"Redis connected: {REDIS_HOST}:{REDIS_PORT}")
            
            # Create pub/sub client
            self.redis_pubsub = self.redis_client.pubsub()
            
            # Initially, no subscriptions - will be added as clients connect
            # Subscriptions are managed dynamically via update_redis_subscriptions()
            
            self.running = True
            self.redis_task = asyncio.create_task(self._redis_subscriber_loop())
            logger.info("Redis subscriber started (subscriptions will be added as clients connect)")

            # Initialize MongoDB client for replaying last decisions
            try:
                self.mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
                # Test connection
                self.mongo_client.admin.command('ping')
                logger.info(f"MongoDB connected for replay fallback: {MONGODB_URI}")
            except Exception as e:
                logger.warning(f"Failed to connect to MongoDB, replay fallback will be unavailable: {e}")
        
        except Exception as e:
            logger.error(f"Failed to start Redis subscriber: {e}", exc_info=True)
            raise
    
    async def _redis_subscriber_loop(self):
        """Main loop for Redis pub/sub subscriber."""
        logger.info("Redis subscriber loop started")
        
        while self.running:
            try:
                if not self.redis_pubsub:
                    await asyncio.sleep(1.0)
                    continue
                
                # Check if we have any active subscriptions before trying to get messages
                # Redis requires at least one subscription before get_message() can be called
                has_subscriptions = (
                    len(self.channel_subscribers) > 0 or 
                    len(self.pattern_subscribers) > 0
                )
                
                if not has_subscriptions:
                    # No subscriptions yet, wait a bit before checking again
                    await asyncio.sleep(1.0)
                    continue
                
                # Get message from Redis (with timeout)
                message = await asyncio.wait_for(
                    self.redis_pubsub.get_message(timeout=1.0),
                    timeout=1.0
                )
                
                if message and message['type'] in ['pmessage', 'message']:
                    await self.handle_redis_message(message)
            
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("Redis subscriber loop cancelled")
                break
            except RuntimeError as e:
                # Handle "pubsub connection not set" error gracefully
                # This can happen if subscriptions haven't been set up yet
                if "pubsub connection not set" in str(e).lower():
                    # Wait a bit and continue - subscriptions may be added soon
                    await asyncio.sleep(1.0)
                    continue
                else:
                    logger.error(f"RuntimeError in Redis subscriber loop: {e}", exc_info=True)
                    await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"Error in Redis subscriber loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)
        
        logger.info("Redis subscriber loop stopped")
    
    async def handle_redis_message(self, message: Dict[str, Any]):
        """Handle message from Redis pub/sub."""
        channel = message.get('channel', '')
        pattern = message.get('pattern', '')
        data = message.get('data', '')

        # Debug logging for all messages
        logger.info(f"Redis message received: channel={channel}, pattern={pattern}")

        if not data:
            return
        
        # Determine which clients should receive this message
        client_ids_to_notify: Set[str] = set()
        
        # Check direct channel subscriptions
        if channel in self.channel_subscribers:
            client_ids_to_notify.update(self.channel_subscribers[channel])
        
        # Check pattern subscriptions
        if pattern:
            if pattern in self.pattern_subscribers:
                client_ids_to_notify.update(self.pattern_subscribers[pattern])
        else:
            # Check if channel matches any pattern
            for pattern_key, client_ids in self.pattern_subscribers.items():
                if self._channel_matches_pattern(channel, pattern_key):
                    client_ids_to_notify.update(client_ids)
        
        # Forward to clients
        logger.info(f"Forwarding to {len(client_ids_to_notify)} clients: {list(client_ids_to_notify)}")
        if client_ids_to_notify:
            try:
                # Parse data (assume JSON)
                try:
                    data_obj = json.loads(data) if isinstance(data, str) else data
                except (json.JSONDecodeError, TypeError):
                    data_obj = {"raw": data}

                seq = await get_next_sequence()
                message_data = {
                    "type": "data",
                    "seq": seq,
                    "channel": channel,
                    "pattern": pattern if pattern else None,
                    "data": data_obj,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                logger.info(f"Sending WebSocket message: {message_data}")

                # Send to all subscribed clients
                disconnected_clients = []
                for client_id in client_ids_to_notify:
                    if client_id in self.clients:
                        client = self.clients[client_id]
                        try:
                            await client.websocket.send_text(json.dumps(message_data))
                            client.message_count += 1
                            client.last_message_time = time.time()
                            logger.info(f"Successfully sent to client {client_id}")
                        except Exception as e:
                            logger.warning(f"Error sending to client {client_id}: {e}")
                            disconnected_clients.append(client_id)
                    else:
                        logger.warning(f"Client {client_id} not found in clients dict")
                        disconnected_clients.append(client_id)

                # Cleanup disconnected clients
                for client_id in disconnected_clients:
                    await self.disconnect_client(client_id)

            except Exception as e:
                logger.error(f"Error handling Redis message: {e}", exc_info=True)
        else:
            logger.warning(f"No clients to notify for channel {channel}, pattern {pattern}")
    
    def _channel_matches_pattern(self, channel: str, pattern: str) -> bool:
        """Check if channel matches pattern."""
        import re
        # Convert Redis pattern to regex
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        try:
            return bool(re.match(regex_pattern, channel))
        except Exception:
            return False
    
    async def stop_redis_subscriber(self):
        """Stop Redis pub/sub subscriber."""
        self.running = False
        
        if self.redis_task:
            self.redis_task.cancel()
            try:
                await self.redis_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_pubsub:
            try:
                await self.redis_pubsub.unsubscribe()
                await self.redis_pubsub.punsubscribe()
                await self.redis_pubsub.aclose()
            except Exception as e:
                logger.warning(f"Error closing pubsub: {e}")
            self.redis_pubsub = None
        
        if self.redis_client:
            try:
                await self.redis_client.aclose()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            self.redis_client = None
        
        logger.info("Redis subscriber stopped")
    
    async def health_check(self):
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "redis-ws-gateway",
            "redis_connected": self.redis_client is not None and self.running,
            "clients_connected": len(self.clients),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_stats(self):
        """Get gateway statistics."""
        return {
            "clients_connected": len(self.clients),
            "total_subscriptions": sum(len(subs) for subs in self.channel_subscribers.values()) + 
                                  sum(len(subs) for subs in self.pattern_subscribers.values()),
            "channels_subscribed": len(self.channel_subscribers),
            "patterns_subscribed": len(self.pattern_subscribers),
            "redis_connected": self.redis_client is not None and self.running,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global gateway instance
gateway = RedisWebSocketGateway()

# Lifespan events
@gateway.app.on_event("startup")
async def startup():
    """Startup event."""
    await gateway.start_redis_subscriber()

@gateway.app.on_event("shutdown")
async def shutdown():
    """Shutdown event."""
    await gateway.stop_redis_subscriber()
    # Disconnect all clients
    for client_id in list(gateway.clients.keys()):
        await gateway.disconnect_client(client_id)


app = gateway.app
