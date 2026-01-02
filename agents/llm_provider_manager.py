"""Multi-provider LLM manager with fallback and rate limit handling."""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass, field
from config.settings import settings

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
    model: str = ""
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


class LLMProviderManager:
    """
    Manages multiple LLM providers with:
    - Automatic fallback on errors/rate limits
    - Rate limit tracking
    - Provider rotation
    - Cost optimization
    """
    
    def __init__(self):
        """Initialize provider manager."""
        self.providers: Dict[str, ProviderConfig] = {}
        self.current_provider: Optional[str] = None
        self.provider_clients: Dict[str, Any] = {}
        self._initialize_providers()
        self._select_best_provider()
    
    def _initialize_providers(self):
        """Initialize all available providers."""
        # Groq Cloud
        if settings.groq_api_key:
            self.providers["groq"] = ProviderConfig(
                name="groq",
                api_key=settings.groq_api_key,
                model="llama-3.3-70b-versatile",
                priority=1,  # High priority (fast, free tier)
                rate_limit_per_minute=30,
                rate_limit_per_day=100000,
                cost_per_1k_tokens=0.0
            )
            try:
                from groq import Groq
                self.provider_clients["groq"] = Groq(api_key=settings.groq_api_key)
                logger.info("✅ Groq provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq: {e}")
                self.providers["groq"].status = ProviderStatus.UNAVAILABLE
        
        # Google Gemini
        if settings.google_api_key:
            self.providers["gemini"] = ProviderConfig(
                name="gemini",
                api_key=settings.google_api_key,
                model="gemini-flash-latest",  # Use latest flash model (works with free tier)
                priority=2,  # High priority (free tier)
                rate_limit_per_minute=60,
                rate_limit_per_day=15000000,  # Very high limit
                cost_per_1k_tokens=0.0
            )
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.google_api_key)
                self.provider_clients["gemini"] = genai
                logger.info("✅ Google Gemini provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
                self.providers["gemini"].status = ProviderStatus.UNAVAILABLE
        
        # OpenRouter
        openrouter_key = getattr(settings, 'openrouter_api_key', None) or os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            # Use a reliable free model - try meta-llama/llama-3.2-3b-instruct:free or mistralai/mistral-7b-instruct:free
            self.providers["openrouter"] = ProviderConfig(
                name="openrouter",
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                model="meta-llama/llama-3.2-3b-instruct:free",  # Free model - verified working
                priority=3,  # Medium priority
                rate_limit_per_minute=50,
                rate_limit_per_day=50000,
                cost_per_1k_tokens=0.0
            )
            try:
                from openai import OpenAI
                self.provider_clients["openrouter"] = OpenAI(
                    api_key=openrouter_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                logger.info("✅ OpenRouter provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter: {e}")
                self.providers["openrouter"].status = ProviderStatus.UNAVAILABLE
        
        # Together AI (if configured)
        if settings.together_api_key:
            self.providers["together"] = ProviderConfig(
                name="together",
                api_key=settings.together_api_key,
                base_url="https://api.together.xyz/v1",
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                priority=4,
                rate_limit_per_minute=40,
                rate_limit_per_day=100000,
                cost_per_1k_tokens=0.0
            )
            try:
                from openai import OpenAI
                self.provider_clients["together"] = OpenAI(
                    api_key=settings.together_api_key,
                    base_url="https://api.together.xyz/v1"
                )
                logger.info("✅ Together AI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Together AI: {e}")
                self.providers["together"].status = ProviderStatus.UNAVAILABLE
        
        # Ollama (Local LLM - if configured)
        ollama_base_url = settings.ollama_base_url or "http://localhost:11434"
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        # Check if Ollama is available (no API key needed)
        try:
            import httpx
            response = httpx.get(f"{ollama_base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                self.providers["ollama"] = ProviderConfig(
                    name="ollama",
                    api_key="ollama",  # Not used but required
                    base_url=ollama_base_url,
                    model=ollama_model,
                    priority=0,  # Highest priority (local, no rate limits)
                    rate_limit_per_minute=1000,  # Very high (local)
                    rate_limit_per_day=10000000,  # Very high (local)
                    cost_per_1k_tokens=0.0  # Free (local)
                )
                try:
                    from openai import OpenAI
                    self.provider_clients["ollama"] = OpenAI(
                        api_key="ollama",
                        base_url=f"{ollama_base_url}/v1" if not ollama_base_url.endswith("/v1") else ollama_base_url
                    )
                    logger.info(f"✅ Ollama provider initialized (model: {ollama_model})")
                except Exception as e:
                    logger.warning(f"Failed to initialize Ollama client: {e}")
                    self.providers["ollama"].status = ProviderStatus.UNAVAILABLE
            else:
                logger.debug(f"Ollama not available at {ollama_base_url}")
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
        
        # OpenAI (if configured)
        if settings.openai_api_key:
            self.providers["openai"] = ProviderConfig(
                name="openai",
                api_key=settings.openai_api_key,
                model="gpt-4o-mini",  # Cost-effective
                priority=5,  # Lower priority (paid)
                rate_limit_per_minute=60,
                rate_limit_per_day=1000000,
                cost_per_1k_tokens=0.15  # Approximate
            )
            try:
                from openai import OpenAI
                self.provider_clients["openai"] = OpenAI(api_key=settings.openai_api_key)
                logger.info("✅ OpenAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")
                self.providers["openai"].status = ProviderStatus.UNAVAILABLE
        
        logger.info(f"Initialized {len([p for p in self.providers.values() if p.status == ProviderStatus.AVAILABLE])} LLM providers")
    
    def _select_best_provider(self) -> Optional[str]:
        """Select the best available provider based on priority and status."""
        # First, try to recover providers that had errors or rate limits
        for name, config in self.providers.items():
            if config.status in [ProviderStatus.ERROR, ProviderStatus.RATE_LIMITED, ProviderStatus.UNAVAILABLE]:
                self._recover_provider(name)
        
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
        
        # Sort by priority (lower = better)
        # Prioritize Gemini when others are rate limited (priority 2)
        available_providers.sort(key=lambda x: (x[1].priority, x[0] != "gemini"))
        
        best_provider = available_providers[0][0]
        self.current_provider = best_provider
        logger.info(f"✅ Selected provider: {best_provider} (priority: {self.providers[best_provider].priority})")
        return best_provider
    
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
    
    def _update_rate_limit(self, provider_name: str):
        """Update rate limit counters."""
        config = self.providers[provider_name]
        config.requests_this_minute += 1
        config.requests_today += 1
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
            try:
                client, provider = self.get_client(provider_name)
                config = self.providers[provider]
                
                # Use specified model or provider default
                model_name = model or config.model
                logger.info(f"🔄 Attempt {attempt + 1}/{max_retries}: Trying {provider} (model: {model_name})")
                
                # Call appropriate API based on provider
                if provider == "gemini":
                    # client is the genai module, already configured
                    genai_model = client.GenerativeModel(model_name)
                    prompt = f"{system_prompt}\n\n{user_message}"
                    response = genai_model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": temperature,
                            "max_output_tokens": max_tokens
                        }
                    )
                    result = response.text
                elif provider == "groq":
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    result = response.choices[0].message.content
                elif provider == "ollama":
                    # Ollama uses OpenAI-compatible API
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    result = response.choices[0].message.content
                elif provider in ["openrouter", "together", "openai"]:
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    result = response.choices[0].message.content
                else:
                    raise ValueError(f"Unsupported provider: {provider}")
                
                # Update rate limit
                self._update_rate_limit(provider)
                
                logger.info(f"✅ LLM call successful via {provider} (model: {model_name})")
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Get provider name safely (might not be set if get_client failed)
                current_provider = provider if 'provider' in locals() else (provider_name or "unknown")
                
                # Check if it's a model-specific error (like 404)
                if "404" in error_msg or "No endpoints found" in error_msg or "model" in error_msg.lower():
                    logger.error(f"Provider {current_provider} model error: {error_msg}")
                    # Mark provider as unavailable and try next
                    if current_provider in self.providers:
                        self.providers[current_provider].status = ProviderStatus.UNAVAILABLE
                        self.providers[current_provider].last_error = error_msg
                        self.providers[current_provider].last_error_time = datetime.now()
                else:
                    logger.warning(f"⚠️ Provider {current_provider} failed: {error_msg[:200]}. Trying next provider...")
                    if current_provider in self.providers:
                        self._handle_provider_error(current_provider, e)
                
                # Try next provider
                provider_name = None  # Let it select best available
                if attempt < max_retries - 1:
                    # Select next best provider
                    next_provider = self._select_best_provider()
                    if next_provider and next_provider != current_provider:
                        logger.info(f"🔄 Switching to provider: {next_provider}")
                        continue
                    else:
                        logger.error(f"No alternative provider available. All providers failed.")
                        break
                else:
                    break
        
        # All providers failed - provide helpful error message
        error_details = []
        for name, config in self.providers.items():
            if config.last_error:
                error_details.append(f"{name}: {config.last_error}")
        
        error_summary = "\n".join(error_details) if error_details else str(last_error)
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
                "last_error": config.last_error,
                "last_error_time": config.last_error_time.isoformat() if config.last_error_time else None,
                "is_current": name == self.current_provider
            }
        return status


# Global instance
_llm_manager: Optional[LLMProviderManager] = None


def get_llm_manager() -> LLMProviderManager:
    """Get global LLM provider manager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMProviderManager()
    return _llm_manager

