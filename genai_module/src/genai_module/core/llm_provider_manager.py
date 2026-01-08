"""Multi-provider LLM manager with fallback and rate limit handling."""

import os
import logging
import time
import random
import concurrent.futures
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass, field
import os

logger = logging.getLogger(__name__)


class ProviderStatus(str, Enum):
    """Provider status."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = ""  # Primary/default model
    models: List[str] = field(default_factory=list)  # Optional rotation list
    priority: int = 0  # Lower = higher priority
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 100000
    cost_per_1k_tokens: float = 0.0
    status: ProviderStatus = ProviderStatus.AVAILABLE
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    requests_today: int = 0
    requests_this_minute: int = 0
    last_request_time: Optional[datetime] = None
    minute_window_start: Optional[datetime] = None
    tokens_today: int = 0
    daily_token_quota: Optional[int] = None


class LLMProviderManager:
    """
    Manages multiple LLM providers with:
    - Automatic fallback on errors/rate limits
    - Rate limit tracking
    - Provider rotation
    - Cost optimization
    """
    
    def __init__(self, settings=None):
        """Initialize provider manager.

        Accept an optional `settings` object (dependency injection). If not provided,
        the manager will try to import `core_kernel.config.settings.settings`, and
        fall back to environment-based defaults when `core_kernel` is not present.
        """
        # Dependency injection: settings can be provided by caller (preferred for tests)
        if settings is None:
            try:
                from core_kernel.config.settings import settings as _settings  # type: ignore
                settings = _settings
            except Exception:
                # Lightweight fallback so module can be imported in minimal test environments
                class _FallbackSettings:
                    pass
                fs = _FallbackSettings()
                fs.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                fs.groq_api_key = os.getenv("GROQ_API_KEY")
                fs.google_api_key = os.getenv("GOOGLE_API_KEY")
                fs.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
                fs.together_api_key = os.getenv("TOGETHER_API_KEY")
                fs.openai_api_key = os.getenv("OPENAI_API_KEY")
                fs.cohere_api_key = os.getenv("COHERE_API_KEY")
                fs.ai21_api_key = os.getenv("AI21_API_KEY")
                fs.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
                fs.mongodb_db_name = os.getenv("MONGODB_DB_NAME", "genai_db")
                settings = fs
        self.settings = settings

        self.providers: Dict[str, ProviderConfig] = {}
        self.current_provider: Optional[str] = None
        self.provider_clients: Dict[str, Any] = {}
        # Semaphore to limit parallel Ollama calls (Ollama doesn't handle parallel well)
        self._ollama_semaphore = None
        # Global semaphore to cap total concurrent LLM calls across all agents
        max_concurrency = int(os.getenv("LLM_MAX_CONCURRENCY", "3"))
        self._global_semaphore = threading.Semaphore(max(1, max_concurrency))
        # Provider rotation counter for load distribution
        self._rotation_counter = 0
        # Model rotation trackers
        self._model_lock = threading.Lock()
        self._model_counters: Dict[str, int] = {}
        # Track parallel group assignments to ensure different providers
        self._parallel_assignments: Dict[str, List[str]] = {}
        # Lock for thread-safe parallel assignment
        self._assignment_lock = threading.Lock()
        # Selection strategy: random | round_robin | weighted | hash | single
        self.selection_strategy: str = os.getenv("LLM_SELECTION_STRATEGY", "random").lower()
        # Single provider mode: use only one provider to reduce load
        self.single_provider_mode: bool = os.getenv("SINGLE_PROVIDER", "false").lower() == "true"
        self.primary_provider: str = os.getenv("PRIMARY_PROVIDER", "groq")
        # Provider usage counters (for metrics and to avoid hammering one provider)
        self.provider_usage_counter: Dict[str, int] = {}
        # Per-provider recent usage timestamps for soft throttling
        self._usage_times: Dict[str, List[datetime]] = {}
        self._usage_lock = threading.Lock()
        # Soft throttle threshold per minute (skip providers temporarily when exceeded)
        self._soft_throttle_per_min = int(os.getenv("LLM_SOFT_THROTTLE", "20"))
        # Health check thread control
        self._health_check_interval = int(os.getenv("LLM_HEALTH_CHECK_INTERVAL", "60"))
        self._stop_health_thread = threading.Event()
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._initialize_providers()
        self._select_best_provider()
        # Start health check thread
        try:
            self._health_thread.start()
        except Exception as e:
            logger.debug(f"Failed to start health check thread: {e}")

    def _health_check_loop(self):
        """Background loop that pings providers and attempts recovery."""
        import time
        while not self._stop_health_thread.is_set():
            try:
                for name in list(self.providers.keys()):
                    config = self.providers[name]
                    if config.status != ProviderStatus.AVAILABLE:
                        # Try to recover rate-limited or errored providers
                        self._recover_provider(name)
                    # Periodic health check for available providers (lightweight)
                    if config.status == ProviderStatus.AVAILABLE:
                        healthy = self.check_provider_health(name, timeout=2)
                        if not healthy:
                            logger.warning(f"⚠️ Health check failed for provider {name}; marking as degraded")
                            config.status = ProviderStatus.ERROR
                            config.last_error = "Health check failed"
                            config.last_error_time = datetime.now()
                time.sleep(self._health_check_interval)
            except Exception as e:
                logger.debug(f"Health check loop error: {e}")
                time.sleep(self._health_check_interval)
    
    def _initialize_providers(self):
        """Initialize all available providers (Groq, Cohere, AI21 with multi-key support)."""
        # Helper to load model lists from env (comma-separated) with a single fallback
        def _get_model_list(single_env: str, plural_env: str, default: str) -> List[str]:
            models_env = os.getenv(plural_env)
            if models_env:
                models = [m.strip() for m in models_env.split(",") if m.strip()]
                return models or [default]
            single = os.getenv(single_env)
            return [single] if single else [default]

        # Groq - FASTEST provider with load balancing support (Priority: 0 - Highest)
        groq_keys = self._get_multiple_api_keys("GROQ_API_KEY")
        if groq_keys:
            # Best Groq model for fast inference: llama-3.1-70b-versatile or llama-3.1-8b-instant
            groq_model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
            groq_models = _get_model_list("GROQ_MODEL", "GROQ_MODELS", groq_model)

            # Store multiple keys for load balancing
            self._groq_keys = groq_keys
            self._groq_key_index = 0

            self.providers["groq"] = ProviderConfig(
                name="groq",
                api_key=groq_keys[0],  # Primary key for config, but we'll rotate in calls
                model=groq_model,
                models=groq_models,
                priority=0,  # HIGHEST priority - fastest provider
                rate_limit_per_minute=30 * len(groq_keys),  # Scale rate limits with multiple keys
                rate_limit_per_day=100000 * len(groq_keys),
                cost_per_1k_tokens=0.0
            )
            # Store API keys directly - we'll use httpx for requests
            self.provider_clients["groq"] = groq_keys  # List of API keys for load balancing
            logger.info(f"✅ Groq provider initialized with {len(groq_keys)} API keys (model: {groq_model})")
        
        # Cohere - Advanced reasoning with multi-key support (Priority: 1)
        cohere_keys = self._get_multiple_api_keys("COHERE_API_KEY")
        if cohere_keys:
            # Best Cohere model: command-r-plus (best) or command-r (faster)
            cohere_model = os.getenv("COHERE_MODEL", "command-r-plus")
            cohere_models = _get_model_list("COHERE_MODEL", "COHERE_MODELS", cohere_model)
            
            # Store multiple keys for load balancing
            self._cohere_keys = cohere_keys
            self._cohere_key_index = 0
            
            self.providers["cohere"] = ProviderConfig(
                name="cohere",
                api_key=cohere_keys[0],  # Primary key, will rotate
                model=cohere_model,
                models=cohere_models,
                priority=1,  # Second priority
                rate_limit_per_minute=100 * len(cohere_keys),
                rate_limit_per_day=5000000 * len(cohere_keys),
                cost_per_1k_tokens=0.0
            )
            # Store API keys for load balancing
            self.provider_clients["cohere"] = cohere_keys
            logger.info(f"✅ Cohere provider initialized with {len(cohere_keys)} API keys (model: {cohere_model})")
        
        # AI21 - Quality language models with multi-key support (Priority: 2)
        ai21_keys = self._get_multiple_api_keys("AI21_API_KEY")
        if ai21_keys:
            # Best AI21 model: jamba-instruct (latest) or j2-ultra (powerful)
            ai21_model = os.getenv("AI21_MODEL", "jamba-instruct")
            ai21_models = _get_model_list("AI21_MODEL", "AI21_MODELS", ai21_model)
            
            # Store multiple keys for load balancing
            self._ai21_keys = ai21_keys
            self._ai21_key_index = 0
            
            self.providers["ai21"] = ProviderConfig(
                name="ai21",
                api_key=ai21_keys[0],  # Primary key, will rotate
                model=ai21_model,
                models=ai21_models,
                priority=2,  # Third priority
                rate_limit_per_minute=60 * len(ai21_keys),
                rate_limit_per_day=300000 * len(ai21_keys),
                cost_per_1k_tokens=0.0
            )
            # Store API keys for load balancing
            self.provider_clients["ai21"] = ai21_keys
            logger.info(f"✅ AI21 provider initialized with {len(ai21_keys)} API keys (model: {ai21_model})")
        
        logger.info(f"Initialized {len([p for p in self.providers.values() if p.status == ProviderStatus.AVAILABLE])} LLM providers")
    
    def _get_multiple_api_keys(self, base_key_name: str) -> List[str]:
        """Get multiple API keys for load balancing (e.g., GROQ_API_KEY, GROQ_API_KEY_2, etc.)."""
        keys = []

        # Primary key
        primary_key = getattr(self.settings, base_key_name.lower(), None) or os.getenv(base_key_name)
        if primary_key:
            keys.append(primary_key)

        # Additional keys (2, 3, 4, etc.)
        for i in range(2, 10):  # Support up to 9 keys
            key_name = f"{base_key_name}_{i}"
            key = os.getenv(key_name)
            if key:
                keys.append(key)
            else:
                break

        return keys
    
    def _select_best_provider(self, use_rotation: bool = False) -> Optional[str]:
        """Select the best available provider based on priority and status."""
        # SINGLE PROVIDER MODE: Use only the primary provider to reduce load
        if self.single_provider_mode and self.primary_provider in self.providers:
            primary_config = self.providers[self.primary_provider]
            if primary_config.status == ProviderStatus.AVAILABLE:
                self.current_provider = self.primary_provider
                logger.info(f"🎯 Single provider mode: Using {self.primary_provider} (primary)")
                return self.primary_provider
            elif primary_config.status in [ProviderStatus.ERROR, ProviderStatus.RATE_LIMITED, ProviderStatus.UNAVAILABLE]:
                # Try to recover primary provider
                self._recover_provider(self.primary_provider)
                if primary_config.status == ProviderStatus.AVAILABLE:
                    self.current_provider = self.primary_provider
                    logger.info(f"✅ Primary provider {self.primary_provider} recovered")
                    return self.primary_provider
                else:
                    logger.warning(f"⚠️ Primary provider {self.primary_provider} unavailable, falling back to others")

        # First, try to recover providers that had errors or rate limits
        for name, config in list(self.providers.items()):
            if config.status in [ProviderStatus.ERROR, ProviderStatus.RATE_LIMITED, ProviderStatus.UNAVAILABLE]:
                self._recover_provider(name)
                # If provider still marked unavailable, try a health check to re-evaluate
                if config.status != ProviderStatus.AVAILABLE:
                    healthy = self.check_provider_health(name)
                    if healthy:
                        config.status = ProviderStatus.AVAILABLE
                        config.last_error = None
                        config.last_error_time = None
                        logger.info(f"✅ Provider {name} recovered via health check during selection")
                    else:
                        logger.debug(f"Provider {name} remains unavailable during selection")
        
        available_providers = [
            (name, config) for name, config in self.providers.items()
            if config.status == ProviderStatus.AVAILABLE
        ]
        
        if not available_providers:
            logger.error("❌ No available LLM providers!")
            # Log status of all providers for debugging
            for name, config in self.providers.items():
                status_info = f"{config.status.value}"
                if config.status == ProviderStatus.RATE_LIMITED and config.last_error_time:
                    wait_time = (config.last_error_time - datetime.now()).total_seconds()
                    if wait_time > 0:
                        status_info += f" (resets in {wait_time:.0f}s)"
                logger.error(f"  {name}: {status_info} - {config.last_error[:100] if config.last_error else 'No error'}")
            return None
        
        # Sort by priority (lower = better), then by token availability
        def _provider_score(provider_tuple):
            name, config = provider_tuple
            priority_score = config.priority

            # Boost providers with more available tokens
            token_score = 0
            if config.daily_token_quota and config.tokens_today is not None:
                available_tokens = config.daily_token_quota - config.tokens_today
                if available_tokens > 0:
                    # Higher score for providers with more available tokens
                    token_score = min(10, available_tokens / 10000)  # Cap at 10 priority points

            return priority_score - token_score  # Lower score = higher priority

        available_providers.sort(key=_provider_score)

        # If rotation enabled, distribute load across cloud providers
        if use_rotation and len(available_providers) > 1 and not self.single_provider_mode:
            # Skip Ollama in rotation (too slow for parallel calls)
            cloud_providers = [p for p in available_providers if p[0] != "ollama"]
            if cloud_providers:
                # Rotate through cloud providers
                if not hasattr(self, '_rotation_counter'):
                    self._rotation_counter = 0
                self._rotation_counter += 1
                selected_idx = self._rotation_counter % len(cloud_providers)
                best_provider = cloud_providers[selected_idx][0]
                logger.debug(f"🔄 Rotated to provider: {best_provider} (rotation #{self._rotation_counter})")
            else:
                # Fallback to all providers if no cloud providers
                if not hasattr(self, '_rotation_counter'):
                    self._rotation_counter = 0
                self._rotation_counter += 1
                selected_idx = self._rotation_counter % len(available_providers)
                best_provider = available_providers[selected_idx][0]
        else:
            # Use highest priority provider
            best_provider = available_providers[0][0]
        
        self.current_provider = best_provider
        logger.info(f"✅ Selected provider: {best_provider} (priority: {self.providers[best_provider].priority})")
        return best_provider

    def _select_model(self, provider_name: str) -> str:
        """Round-robin model selection for a provider when multiple models are configured."""
        config = self.providers[provider_name]
        if not config.models:
            return config.model
        if len(config.models) == 1:
            return config.models[0]
        with self._model_lock:
            counter = self._model_counters.get(provider_name, 0)
            model = config.models[counter % len(config.models)]
            self._model_counters[provider_name] = counter + 1
            return model

    # --- Usage tracking & soft throttling helpers ---
    def _record_usage(self, provider_name: str):
        """Record a timestamped selection for a provider and increment counters.

        Also persist a rolling counter in MongoDB so the dashboard (in a separate process)
        can surface usage_counts across services.
        """
        now = datetime.now()
        with self._usage_lock:
            self._usage_times.setdefault(provider_name, []).append(now)
        self.provider_usage_counter[provider_name] = self.provider_usage_counter.get(provider_name, 0) + 1
        # Persist to MongoDB (best-effort)
        try:
            from mongodb_schema import get_mongo_client, get_collection
            client = get_mongo_client()
            db = client[self.settings.mongodb_db_name]
            coll = get_collection(db, 'llm_usage')
            coll.update_one({'_id': 'counters'}, {'$inc': {provider_name: 1}, '$set': {'timestamp': datetime.utcnow().isoformat()}}, upsert=True)
        except Exception:
            # Non-fatal - persistence is best-effort
            pass

    def _clean_usage(self, provider_name: str):
        """Remove timestamps older than one minute for provider throttling."""
        cutoff = datetime.now() - timedelta(seconds=60)
        with self._usage_lock:
            times = self._usage_times.get(provider_name, [])
            self._usage_times[provider_name] = [t for t in times if t >= cutoff]

    def _is_throttled(self, provider_name: str) -> bool:
        """Return True if provider has exceeded soft throttle threshold in the last minute."""
        self._clean_usage(provider_name)
        with self._usage_lock:
            cnt = len(self._usage_times.get(provider_name, []))
        return cnt >= self._soft_throttle_per_min
    
    def get_provider_for_agent(self, agent_name: str, parallel_group: Optional[str] = None) -> Optional[str]:
        """
        Get a provider for a specific agent, distributing load across providers.
        This prevents all agents from hitting the same provider simultaneously.
        
        For parallel execution, ensures different agents get different providers.
        
        Args:
            agent_name: Name of the agent (e.g., "technical", "fundamental")
            parallel_group: Optional group identifier for parallel agents (e.g., "analysis_parallel")
                          Agents in same group will get different providers
        
        Returns:
            Provider name or None if none available
        """
        # Recover providers first
        for name, config in self.providers.items():
            if config.status in [ProviderStatus.ERROR, ProviderStatus.RATE_LIMITED, ProviderStatus.UNAVAILABLE]:
                self._recover_provider(name)
        
        # Get available cloud providers (skip Ollama for parallel calls)
        cloud_providers = [
            (name, config) for name, config in self.providers.items()
            if config.status == ProviderStatus.AVAILABLE and name != "ollama"
        ]

        # Soft throttling: avoid providers approaching their minute rate limit
        try:
            throttle_factor = float(os.getenv("LLM_SOFT_THROTTLE_FACTOR", "0.8"))
        except Exception:
            throttle_factor = 0.8
        def _is_throttled(cfg: ProviderConfig):
            if not cfg.minute_window_start:
                return False
            allowed = max(1, int(cfg.rate_limit_per_minute * throttle_factor))
            return getattr(cfg, 'requests_this_minute', 0) >= allowed

        # Filter out providers currently above the soft throttle threshold
        available_filtered = [(n,c) for (n,c) in cloud_providers if not _is_throttled(c)]
        if not available_filtered and cloud_providers:
            # If all providers are throttled, fall back to original list (we will let rate-limit checks handle it later)
            available_filtered = cloud_providers
        cloud_providers = available_filtered
        
        if not cloud_providers:
            # Fallback to all providers including Ollama
            cloud_providers = [
                (name, config) for name, config in self.providers.items()
                if config.status == ProviderStatus.AVAILABLE
            ]
        
        if not cloud_providers:
            return None
        
        # Apply soft-throttle: filter out providers that exceeded recent usage
        available_filtered = [(n, c) for (n, c) in cloud_providers if not self._is_throttled(n)]
        if available_filtered:
            cloud_providers = available_filtered
        # If all providers are throttled, fall back to original list to avoid total blockage
        # Sort by priority
        cloud_providers.sort(key=lambda x: x[1].priority)
        
        if parallel_group:
            # For parallel execution, use round-robin within the group
            # Thread-safe assignment to prevent race conditions
            with self._assignment_lock:
                if parallel_group not in self._parallel_assignments:
                    self._parallel_assignments[parallel_group] = []
                
                # Get providers already assigned in this parallel group
                assigned_providers = set(self._parallel_assignments[parallel_group])
                
                # Find providers NOT yet assigned in this group
                unassigned_providers = [
                    (name, config) for name, config in cloud_providers
                    if name not in assigned_providers
                ]
                
                if unassigned_providers:
                    # Choose a random unassigned provider to distribute load within the group
                    provider = random.choice(unassigned_providers)[0]
                    self._parallel_assignments[parallel_group].append(provider)
                    # Record usage and persist counters
                    try:
                        self._record_usage(provider)
                    except Exception:
                        pass
                    logger.info(f"📊 Assigned provider {provider} to agent {agent_name} (parallel group: {parallel_group}, avoiding duplicates, strategy={self.selection_strategy})")
                else:
                    # All providers assigned, pick using configured strategy
                    strategy = self.selection_strategy
                    names = [p[0] for p in cloud_providers]
                    if strategy == 'round_robin':
                        if not hasattr(self, '_rotation_counter'):
                            self._rotation_counter = 0
                        self._rotation_counter += 1
                        provider = names[self._rotation_counter % len(names)]
                    elif strategy == 'weighted':
                        # Inverse priority weighting (lower priority -> higher weight)
                        weights = [1.0 / (p[1].priority + 1) for p in cloud_providers]
                        provider = random.choices(names, weights=weights, k=1)[0]
                    elif strategy == 'hash':
                        agent_hash = hash(agent_name) % 1000
                        selected_idx = agent_hash % len(names)
                        provider = names[selected_idx]
                    else:  # default: random
                        provider = random.choice(names)
                    # Record usage and persist counters
                    try:
                        self._record_usage(provider)
                    except Exception:
                        pass
                    logger.info(f"📊 Assigned provider {provider} to agent {agent_name} (parallel group: {parallel_group}, strategy={strategy})")
        else:
            # Use configured strategy to select provider for non-parallel calls
            strategy = self.selection_strategy
            names = [p[0] for p in cloud_providers]
            if strategy == 'round_robin':
                if not hasattr(self, '_rotation_counter'):
                    self._rotation_counter = 0
                self._rotation_counter += 1
                provider = names[self._rotation_counter % len(names)]
                logger.debug(f"📊 Assigned provider {provider} to agent {agent_name} (round_robin, rotation #{self._rotation_counter})")
            elif strategy == 'weighted':
                # Inverse priority weighting (lower priority -> higher weight)
                weights = [1.0 / (p[1].priority + 1) for p in cloud_providers]
                provider = random.choices(names, weights=weights, k=1)[0]
                logger.debug(f"📊 Assigned provider {provider} to agent {agent_name} (weighted selection)")
            elif strategy == 'hash':
                agent_hash = hash(agent_name) % 1000
                selected_idx = agent_hash % len(names)
                provider = names[selected_idx]
                logger.debug(f"📊 Assigned provider {provider} to agent {agent_name} (hash: {agent_hash})")
            else:  # default: random
                provider = random.choice(names)
                logger.debug(f"📊 Assigned provider {provider} to agent {agent_name} (random)")

        # Record usage and track counts for metrics and throttling
        try:
            self._record_usage(provider)
        except Exception:
            # Fallback increment if record fails
            try:
                self.provider_usage_counter[provider] = self.provider_usage_counter.get(provider, 0) + 1
            except Exception:
                pass
        return provider
    
    def _check_rate_limit(self, provider_name: str) -> bool:
        """Check if provider is within rate limits."""
        config = self.providers[provider_name]
        now = datetime.now()
        
        # Reset minute window if needed
        if config.minute_window_start is None or (now - config.minute_window_start).total_seconds() > 60:
            config.minute_window_start = now
            config.requests_this_minute = 0
        
        # Check minute limit
        if config.requests_this_minute >= config.rate_limit_per_minute:
            logger.warning(f"Provider {provider_name} hit minute rate limit")
            config.status = ProviderStatus.RATE_LIMITED
            return False
        
        # Check daily limit (simplified - would need proper tracking)
        if config.requests_today >= config.rate_limit_per_day:
            logger.warning(f"Provider {provider_name} hit daily rate limit")
            config.status = ProviderStatus.RATE_LIMITED
            return False
        
        return True
    
    def _update_rate_limit(self, provider_name: str, tokens_used: int = 0):
        """Update rate limit counters and token usage."""
        config = self.providers[provider_name]
        config.requests_this_minute += 1
        config.requests_today += 1
        config.tokens_today = getattr(config, 'tokens_today', 0) + tokens_used
        config.last_request_time = datetime.now()
    
    def _handle_provider_error(self, provider_name: str, error: Exception):
        """Handle provider error and mark as unavailable temporarily."""
        config = self.providers[provider_name]
        error_str = str(error)
        
        # Check if it's a rate limit error (429)
        is_rate_limit = "429" in error_str or "rate limit" in error_str.lower() or "Rate limit" in error_str
        
        if is_rate_limit:
            # Extract rate limit reset time if available
            reset_time = None
            import re
            
            # Try multiple patterns to extract reset time
            # Pattern 1: "Please try again in 4m36.48s" (Groq format - minutes and seconds)
            reset_match = re.search(r'try again in\s+(\d+)m(\d+\.?\d*)s', error_str, re.IGNORECASE)
            if reset_match:
                minutes = int(reset_match.group(1))
                seconds = float(reset_match.group(2))
                reset_seconds = (minutes * 60) + seconds
                reset_time = datetime.now() + timedelta(seconds=reset_seconds)
                logger.info(f"⏰ Provider {provider_name} rate limited. Will retry after {reset_seconds:.0f}s ({minutes}m{seconds:.0f}s) (at {reset_time.strftime('%H:%M:%S')})")
            
            # Pattern 1b: "try again in X minutes" or "try again in X seconds"
            elif re.search(r'try again in', error_str, re.IGNORECASE):
                reset_match = re.search(r'try again in\s+(\d+\.?\d*)\s*(m|min|minutes|s|seconds)', error_str, re.IGNORECASE)
                if reset_match:
                    reset_value = float(reset_match.group(1))
                    unit = reset_match.group(2).lower()
                    if unit.startswith('m'):
                        reset_seconds = reset_value * 60
                    else:
                        reset_seconds = reset_value
                    reset_time = datetime.now() + timedelta(seconds=reset_seconds)
                    logger.info(f"⏰ Provider {provider_name} rate limited. Will retry after {reset_seconds:.0f}s (at {reset_time.strftime('%H:%M:%S')})")
            
            # Pattern 2: X-RateLimit-Reset header (Unix timestamp in milliseconds)
            elif "X-RateLimit-Reset" in error_str:
                reset_match = re.search(r'X-RateLimit-Reset[\'":\s]+(\d+)', error_str)
                if reset_match:
                    reset_timestamp_ms = int(reset_match.group(1))
                    reset_timestamp = reset_timestamp_ms / 1000  # Convert to seconds
                    reset_time = datetime.fromtimestamp(reset_timestamp)
                    wait_seconds = (reset_time - datetime.now()).total_seconds()
                    if wait_seconds > 0:
                        logger.info(f"⏰ Provider {provider_name} rate limited. Will retry after {wait_seconds:.0f}s (at {reset_time.strftime('%H:%M:%S')})")
            
            # Pattern 3: "retry in X seconds/minutes"
            if not reset_time:
                reset_match = re.search(r'retry.*?(\d+\.?\d*)\s*(?:s|seconds|min|minutes)', error_str, re.IGNORECASE)
                if reset_match:
                    reset_value = float(reset_match.group(1))
                    if 'min' in error_str[reset_match.start():reset_match.end()+5].lower():
                        reset_seconds = reset_value * 60
                    else:
                        reset_seconds = reset_value
                    reset_time = datetime.now() + timedelta(seconds=reset_seconds)
                    logger.info(f"⏰ Provider {provider_name} rate limited. Will retry after {reset_seconds:.0f}s")
            
            # Default: 5 minutes if no reset time found
            if not reset_time:
                reset_time = datetime.now() + timedelta(minutes=5)
                logger.warning(f"⏰ Provider {provider_name} rate limited. Will retry after 5 minutes (default).")
            
            config.status = ProviderStatus.RATE_LIMITED
            config.last_error = error_str
            # Store reset time in last_error_time for recovery check
            config.last_error_time = reset_time
        else:
            config.status = ProviderStatus.ERROR
            config.last_error = error_str
            config.last_error_time = datetime.now()
            logger.warning(f"Provider {provider_name} error: {error}. Will retry after 5 minutes.")

        # Route an alert for operator visibility (non-blocking)
        try:
            from monitoring.alert_router import send_alert
            alert_type = 'provider_rate_limited' if is_rate_limit else 'provider_error'
            severity = 'warning' if is_rate_limit else 'critical'
            details = {
                'provider': provider_name,
                'error': error_str,
                'reset_time': config.last_error_time.isoformat() if config.last_error_time else None
            }
            send_alert(alert_type, f"Provider {provider_name} status: {config.status.value}", severity=severity, details=details, source='llm_provider_manager')
        except Exception as ae:
            logger.debug(f"Failed to route alert for provider {provider_name}: {ae}")
        
        # Select next best provider
        self._select_best_provider()
    
    def _recover_provider(self, provider_name: str):
        """Recover provider after error (after cooldown period)."""
        if provider_name not in self.providers:
            return
        config = self.providers[provider_name]
        if config.last_error_time:
            now = datetime.now()
            # Check if reset time has passed (for rate limits, last_error_time is the reset time)
            time_since_reset = (now - config.last_error_time).total_seconds()
            
            # Don't recover if it's a model error (404) - that won't fix itself
            is_model_error = config.last_error and (
                "404" in config.last_error or 
                "No endpoints found" in config.last_error or
                "model" in config.last_error.lower() or
                "No module named" in config.last_error  # Missing package
            )
            
            # Check if it's a rate limit
            is_rate_limit = config.status == ProviderStatus.RATE_LIMITED or (
                config.last_error and ("429" in config.last_error or "rate limit" in config.last_error.lower())
            )
            
            if is_model_error:
                # Model errors persist - don't auto-recover
                logger.debug(f"Provider {provider_name} has model error, skipping recovery")
                return
            
            if is_rate_limit:
                # For rate limits, check if reset time has passed
                # If last_error_time was set to reset time, check if now > reset time
                if time_since_reset >= 0:  # Reset time has passed
                    config.status = ProviderStatus.AVAILABLE
                    config.last_error = None
                    logger.info(f"✅ Provider {provider_name} recovered from rate limit (waited {abs(time_since_reset):.0f}s)")
                else:
                    # Still waiting for rate limit to reset
                    wait_time = abs(time_since_reset)
                    logger.debug(f"⏳ Provider {provider_name} still rate limited. Resets in {wait_time:.0f}s")
            else:
                # For other errors, wait 5 minutes
                if time_since_reset > 300:  # 5 minutes
                    config.status = ProviderStatus.AVAILABLE
                    config.last_error = None
                    logger.info(f"✅ Provider {provider_name} recovered after {time_since_reset:.0f}s")
        else:
            # If there's no last_error_time but status is not AVAILABLE, attempt a quick health check
            if config.status != ProviderStatus.AVAILABLE:
                healthy = self.check_provider_health(provider_name)
                if healthy:
                    config.status = ProviderStatus.AVAILABLE
                    config.last_error = None
                    config.last_error_time = None
                    logger.info(f"✅ Provider {provider_name} marked healthy by quick check")
                else:
                    logger.debug(f"Provider {provider_name} still unhealthy by quick check")
    
    def get_client(self, provider_name: Optional[str] = None) -> Tuple[Any, str]:
        """
        Get LLM client for specified provider or best available.
        
        Returns:
            Tuple of (client, provider_name)
        """
        if provider_name:
            if provider_name not in self.providers:
                raise ValueError(f"Unknown provider: {provider_name}")
            if not self._check_rate_limit(provider_name):
                # Fallback to best available
                provider_name = self._select_best_provider()
        else:
            provider_name = self.current_provider or self._select_best_provider()
        
        if not provider_name:
            raise RuntimeError("No available LLM providers!")
        
        # Recover providers that had errors
        for name in self.providers:
            if name != provider_name:
                self._recover_provider(name)
        
        # Try to recover providers before checking rate limit
        self._recover_provider(provider_name)
        
        if not self._check_rate_limit(provider_name):
            # Try next provider
            provider_name = self._select_best_provider()
            if not provider_name:
                # Try to recover all providers one more time
                for name in self.providers:
                    self._recover_provider(name)
                provider_name = self._select_best_provider()
                if not provider_name:
                    raise RuntimeError("All providers rate limited!")
        
        return self.provider_clients[provider_name], provider_name
    
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.2,
        model_override: Optional[str] = None,
        system_prompt: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Tuple[str, int, Optional[float]]:
        """Legacy helper that powers the ProviderManagerClient adapter.

        Accepts a prompt string and returns the raw text along with lightweight
        token/cost estimates so the new `LLMClient` interface can wrap the
        existing provider manager without each caller re-implementing the
        selection / retry logic.
        """
        if not prompt:
            raise ValueError("prompt is required")

        default_system_prompt = os.getenv(
            "LLM_SYSTEM_PROMPT",
            "You are Zerodha's multi-agent trading assistant. Provide concise, risk-aware reasoning.",
        )
        system_prompt = system_prompt or default_system_prompt

        response_text = self.call_llm(
            system_prompt=system_prompt,
            user_message=prompt,
            model=model_override,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_name=provider_name,
        )

        # Rough token estimate to keep downstream telemetry consistent
        combined_prompt = f"{system_prompt}\n\n{prompt}"
        prompt_tokens = len(combined_prompt.split())
        response_tokens = len(str(response_text).split())
        tokens_used = max(1, prompt_tokens + response_tokens)

        resolved_provider = provider_name or self.current_provider
        cost = None
        if resolved_provider and resolved_provider in self.providers:
            per_thousand = self.providers[resolved_provider].cost_per_1k_tokens or 0.0
            if per_thousand > 0:
                cost = round((tokens_used / 1000.0) * per_thousand, 6)

        return response_text, tokens_used, cost

    def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        provider_name: Optional[str] = None
    ) -> str:
        """
        Call LLM with automatic fallback.
        
        Args:
            system_prompt: System prompt
            user_message: User message
            model: Model name (overrides provider default)
            temperature: Temperature
            max_tokens: Max tokens
            provider_name: Specific provider to use (optional)
        
        Returns:
            LLM response text
        """
        max_retries = len(self.providers)
        last_error = None

        for attempt in range(max_retries):
            self._global_semaphore.acquire()
            jitter = random.uniform(0.1, 0.6)
            time.sleep(jitter)
            try:
                client, provider = self.get_client(provider_name)
                config = self.providers[provider]

                model_name = model or self._select_model(provider)
                call_start_time = time.time()
                logger.info(f"🔄 Attempt {attempt + 1}/{max_retries}: Trying {provider} (model: {model_name})")

                if provider == "groq":
                    def _call_groq():
                        import httpx

                        # Load balancing: rotate between multiple Groq API keys
                        if hasattr(self, '_groq_keys') and len(self._groq_keys) > 1:
                            # Round-robin key selection for load balancing
                            key_index = getattr(self, '_groq_key_index', 0)
                            api_key = self._groq_keys[key_index % len(self._groq_keys)]
                            self._groq_key_index = (key_index + 1) % len(self._groq_keys)
                            logger.debug(f"Using Groq key #{(key_index % len(self._groq_keys)) + 1} for load balancing")
                        else:
                            # Single key fallback
                            api_key = self.provider_clients.get(provider)
                            if isinstance(api_key, list):
                                api_key = api_key[0]  # Use first key if it's a list

                        # Direct HTTP call to Groq API
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }

                        data = {
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_message}
                            ],
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        }

                        response = httpx.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers=headers,
                            json=data,
                            timeout=60.0
                        )
                        response.raise_for_status()
                        result = response.json()
                        return result

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_call_groq)
                        response = future.result(timeout=60.0)
                        result = response["choices"][0]["message"]["content"]
                elif provider == "cohere":
                    import cohere
                    
                    # Load balancing: rotate between multiple Cohere API keys
                    if hasattr(self, '_cohere_keys') and len(self._cohere_keys) > 1:
                        # Round-robin key selection for load balancing
                        key_index = getattr(self, '_cohere_key_index', 0)
                        api_key = self._cohere_keys[key_index % len(self._cohere_keys)]
                        self._cohere_key_index = (key_index + 1) % len(self._cohere_keys)
                        logger.debug(f"Using Cohere key #{(key_index % len(self._cohere_keys)) + 1} for load balancing")
                    else:
                        # Single key fallback
                        api_key = self.provider_clients.get(provider)
                        if isinstance(api_key, list):
                            api_key = api_key[0]  # Use first key if it's a list
                    
                    co = cohere.Client(api_key=api_key)
                    response = co.chat(
                        model=model_name,
                        message=user_message,
                        preamble=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    result = response.text
                elif provider == "ai21":
                    import requests
                    
                    # Load balancing: rotate between multiple AI21 API keys
                    if hasattr(self, '_ai21_keys') and len(self._ai21_keys) > 1:
                        # Round-robin key selection for load balancing
                        key_index = getattr(self, '_ai21_key_index', 0)
                        api_key = self._ai21_keys[key_index % len(self._ai21_keys)]
                        self._ai21_key_index = (key_index + 1) % len(self._ai21_keys)
                        logger.debug(f"Using AI21 key #{(key_index % len(self._ai21_keys)) + 1} for load balancing")
                    else:
                        # Single key fallback
                        api_key = self.provider_clients.get(provider)
                        if isinstance(api_key, list):
                            api_key = api_key[0]  # Use first key if it's a list
                    
                    # Use modern chat completions API for jamba-instruct
                    url = f"https://api.ai21.com/studio/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    }
                    response = requests.post(url, headers=headers, json=data, timeout=60)
                    response.raise_for_status()
                    result = response.json()["choices"][0]["message"]["content"]
                else:
                    raise ValueError(f"Unsupported provider: {provider}")

                # Estimate tokens used (simple heuristic) and update rate/token counters
                tokens_used = max(1, len((system_prompt + user_message).split()) + len(str(result).split()))
                try:
                    self._update_rate_limit(provider, tokens_used=tokens_used)
                except Exception:
                    # Fallback to safe update
                    self._update_rate_limit(provider, tokens_used=0)

                call_elapsed = time.time() - call_start_time
                logger.info(f"✅ LLM call successful via {provider} (model: {model_name}) in {call_elapsed:.1f}s, tokens_est={tokens_used}")
                return result

            except concurrent.futures.TimeoutError as e:
                last_error = e
                current_provider = provider if 'provider' in locals() else (provider_name or "unknown")
                logger.error(f"❌ Provider {current_provider} timed out")
                if current_provider in self.providers:
                    self._handle_provider_error(current_provider, e)
                provider_name = None
                if attempt < max_retries - 1:
                    next_provider = self._select_best_provider()
                    if next_provider and next_provider != current_provider:
                        logger.info(f"🔄 Switching to provider: {next_provider} after timeout")
                        continue
                    else:
                        logger.error("No alternative provider available after timeout.")
                        break
                else:
                    break
            except Exception as e:
                last_error = e
                error_msg = str(e)
                current_provider = provider if 'provider' in locals() else (provider_name or "unknown")

                if "404" in error_msg or "No endpoints found" in error_msg or "model" in error_msg.lower():
                    logger.error(f"Provider {current_provider} model error: {error_msg}")
                    if current_provider in self.providers:
                        self.providers[current_provider].status = ProviderStatus.UNAVAILABLE
                        self.providers[current_provider].last_error = error_msg
                        self.providers[current_provider].last_error_time = datetime.now()
                else:
                    logger.warning(f"⚠️ Provider {current_provider} failed: {error_msg[:200]}. Trying next provider...")
                    if current_provider in self.providers:
                        self._handle_provider_error(current_provider, e)

                provider_name = None
                if attempt < max_retries - 1:
                    next_provider = self._select_best_provider()
                    if next_provider and next_provider != current_provider:
                        logger.info(f"🔄 Switching to provider: {next_provider}")
                        continue
                    else:
                        logger.error("No alternative provider available. All providers failed.")
                        break
                else:
                    break
            finally:
                try:
                    self._global_semaphore.release()
                except Exception:
                    pass

        error_details = []
        for name, config in self.providers.items():
            if config.last_error:
                error_details.append(f"{name}: {config.last_error}")

        error_summary = "\n".join(error_details) if error_details else str(last_error)
        
        # FINAL FALLBACK: Try our multi-provider API manager with Cohere, AI21, etc.
        logger.warning("🔄 All existing providers failed. Trying multi-provider fallback...")
        try:
            from utils.request_router import RequestRouter
            fallback_router = RequestRouter()
            
            # Combine system and user messages
            combined_prompt = f"{system_prompt}\n\n{user_message}"
            
            fallback_result = fallback_router.make_llm_request(
                prompt=combined_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            logger.info(f"✅ Multi-provider fallback successful via {fallback_result['provider']}")
            return fallback_result['response']['text']
            
        except Exception as fallback_error:
            logger.error(f"❌ Multi-provider fallback also failed: {fallback_error}")
            # Continue with original error
        
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}\nProvider errors:\n{error_summary}")
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all providers."""
        status = {}
        for name, config in self.providers.items():
            status[name] = {
                "status": config.status.value,
                "priority": config.priority,
                "requests_today": config.requests_today,
                "requests_this_minute": config.requests_this_minute,
                "rate_limit_per_minute": config.rate_limit_per_minute,
                "rate_limit_per_day": config.rate_limit_per_day,
                "tokens_today": getattr(config, 'tokens_today', 0),
                "daily_token_quota": getattr(config, 'daily_token_quota', None),
                "last_error": config.last_error,
                "last_error_time": config.last_error_time.isoformat() if config.last_error_time else None,
                "is_current": name == self.current_provider
            }        
        # Add multi-provider fallback status
        try:
            from utils.request_router import RequestRouter
            router = RequestRouter()
            multi_stats = router.get_stats()
            
            status["multi_provider_fallback"] = {
                "status": "available",
                "providers": {
                    name: {
                        "usage": info["usage"],
                        "limit": info["limit"],
                        "usage_percent": info["usage_percent"],
                        "has_key": info["has_key"],
                        "model": info["model"]
                    }
                    for name, info in multi_stats.items()
                },
                "description": "Cohere, AI21, Groq, HuggingFace, OpenAI, Google fallback"
            }
        except Exception as e:
            status["multi_provider_fallback"] = {
                "status": "error",
                "error": str(e)
            }
        
        return status

    def check_provider_health(self, provider_name: str, timeout: int = 5) -> bool:
        """Quick health check for a provider by making a lightweight call or ping.

        Returns True if healthy, False otherwise.
        """
        if provider_name not in self.providers:
            return False
        config = self.providers[provider_name]
        try:
            # Try to call a minimal API with very small max_tokens
            try:
                if provider_name == 'groq':
                    import httpx

                    # Groq: direct HTTP call for health check
                    # Use load balancing for health checks too
                    if hasattr(self, '_groq_keys') and len(self._groq_keys) > 1:
                        # Test all keys, succeed if any work
                        for i, api_key in enumerate(self._groq_keys):
                            try:
                                headers = {
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json"
                                }
                                data = {
                                    "model": config.model,
                                    "messages": [{"role": "system", "content": "health check"}, {"role": "user", "content": "ping"}],
                                    "max_tokens": 1
                                }
                                response = httpx.post(
                                    "https://api.groq.com/openai/v1/chat/completions",
                                    headers=headers,
                                    json=data,
                                    timeout=timeout
                                )
                                if response.status_code == 200:
                                    return True  # At least one key works
                            except Exception:
                                continue  # Try next key
                        return False  # All keys failed
                    else:
                        # Single key health check
                        api_key = self.provider_clients.get(provider_name)
                        if isinstance(api_key, list):
                            api_key = api_key[0]

                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                        data = {
                            "model": config.model,
                            "messages": [{"role": "system", "content": "health check"}, {"role": "user", "content": "ping"}],
                            "max_tokens": 1
                        }
                        response = httpx.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers=headers,
                            json=data,
                            timeout=timeout
                        )
                        return response.status_code == 200
                elif provider_name == 'cohere':
                    import cohere
                    api_key = self.provider_clients.get(provider_name)
                    if isinstance(api_key, list):
                        api_key = api_key[0]
                    co = cohere.Client(api_key=api_key)
                    response = co.chat(
                        model=config.model,
                        message="ping",
                        max_tokens=1,
                        temperature=0.0
                    )
                    return True
                elif provider_name == 'ai21':
                    import requests
                    api_key = self.provider_clients.get(provider_name)
                    if isinstance(api_key, list):
                        api_key = api_key[0]
                    url = f"https://api.ai21.com/studio/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "model": config.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                        "temperature": 0.0
                    }
                    response = requests.post(url, headers=headers, json=data, timeout=timeout)
                    response.raise_for_status()
                    return True
                else:
                    # Unknown provider - assume unhealthy
                    return False
            except Exception as e:
                logger.debug(f"Health check call failed for {provider_name}: {e}")
                return False
        except Exception as e:
            logger.debug(f"Health check error for {provider_name}: {e}")
            return False


# Global instance
_llm_manager: Optional[LLMProviderManager] = None


def get_llm_manager(settings: Optional[Any] = None) -> LLMProviderManager:
    """Get global LLM provider manager instance.

    Optionally accepts a `settings` object (dependency injection) so callers
    can provide the application settings explicitly (recommended for tests).
    """
    global _llm_manager
    if _llm_manager is None:
        if settings is None:
            try:
                from core_kernel.config.settings import settings as _settings  # type: ignore
                settings = _settings
            except Exception:
                settings = None
        _llm_manager = LLMProviderManager(settings=settings)
    return _llm_manager


