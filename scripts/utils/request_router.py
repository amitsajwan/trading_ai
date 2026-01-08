"""
Request Router for Multi-Provider LLM System
Routes API requests to the best available provider with automatic fallback
"""

import logging
from typing import Optional, Dict, Any
from scripts.utils.api_manager import APIManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom exceptions
class RateLimitError(Exception):
    """Raised when a provider returns an HTTP 429 / rate limit"""
    def __init__(self, message: str = "", reset_seconds: Optional[int] = None):
        super().__init__(message)
        self.reset_seconds = reset_seconds

class ProviderUnavailableError(Exception):
    """Raised when a provider is unavailable due to missing libraries or misconfiguration"""
    pass


class RequestRouter:
    """
    Routes API requests to the best available provider with automatic fallback.
    Implements per-provider circuit breaker and retry logic for transient errors.
    """
    
    def __init__(self):
        self.api_manager = APIManager()
        # Circuit breaker state per provider: { provider: {count, open_until (timestamp)} }
        self._provider_failures = {}
        self.failure_threshold = 2  # failures to open circuit
        self.cooldown_seconds = 30  # seconds to keep circuit open
        self._max_call_retries = 2  # retries per provider call (in addition to provider fallback)
    
    def make_llm_request(
        self, 
        prompt: str, 
        max_tokens: int = 1000, 
        temperature: float = 0.3,
        preferred_provider: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make an LLM inference request with automatic provider selection and fallback.
        
        Args:
            prompt: The input prompt for the LLM
            max_tokens: Maximum tokens in the response
            temperature: Sampling temperature (0-1)
            preferred_provider: Preferred provider name (optional)
            
        Returns:
            Dict with provider, response, and tokens_used
        """
        available_providers = self.api_manager.get_available_providers("llm")
        
        if not available_providers:
            raise Exception("❌ No available LLM providers!")
        
        # If preferred provider specified, try it first
        if preferred_provider:
            for provider_name, provider_info in available_providers:
                if provider_name == preferred_provider:
                    try:
                        return self._try_provider(
                            provider_name, 
                            provider_info, 
                            prompt, 
                            max_tokens, 
                            temperature
                        )
                    except Exception as e:
                        logger.error(f"❌ Preferred provider {provider_name} failed: {e}")
                        break
        
        # Try providers in priority order with circuit breaker awareness
        last_error = None
        for provider_name, provider_info in available_providers:
            # Skip provider if circuit is open
            state = self._provider_failures.get(provider_name, {})
            from datetime import datetime
            if state.get('open_until') and state['open_until'] > datetime.now().timestamp():
                logger.warning(f"⚠️ Skipping provider {provider_name} due to open circuit (cooldown)")
                continue

            try:
                return self._try_provider(
                    provider_name, 
                    provider_info, 
                    prompt, 
                    max_tokens, 
                    temperature
                )
            except Exception as e:
                logger.error(f"❌ Error with {provider_name}: {e}")
                last_error = e
                # increment failure count
                st = self._provider_failures.get(provider_name, {'count': 0})
                st['count'] = st.get('count', 0) + 1
                from datetime import datetime, timedelta
                if st['count'] >= self.failure_threshold:
                    new_open = (datetime.now() + timedelta(seconds=self.cooldown_seconds)).timestamp()
                    # If an open_until is already set (e.g. from a RateLimitError), don't override it
                    existing_open = st.get('open_until')
                    if existing_open and existing_open > datetime.now().timestamp():
                        # Keep existing shorter/longer window set by provider
                        st['open_until'] = existing_open
                    else:
                        st['open_until'] = new_open
                    logger.warning(f"⛔ Opening circuit for {provider_name} until {st['open_until']}")
                self._provider_failures[provider_name] = st
                continue
        
        raise Exception(f"❌ All providers failed! Last error: {last_error}")
    
    def _try_provider(
        self, 
        provider_name: str, 
        provider_info: Dict, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        """Try to make a request with a specific provider"""
        logger.info(f"🔄 Attempting request with {provider_name}...")
        
        api_key = provider_info["key"]
        model = provider_info.get("model", "default")
        
        # Try the provider call with retries for transient errors
        last_exc = None
        for attempt in range(1, self._max_call_retries + 2):
            try:
                # Route to appropriate provider
                if provider_name == "cohere":
                    response = self._call_cohere(api_key, prompt, max_tokens, temperature, model)
                elif provider_name == "ai21":
                    response = self._call_ai21(api_key, prompt, max_tokens, temperature, model)
                elif provider_name == "groq":
                    response = self._call_groq(api_key, prompt, max_tokens, temperature, model)
                elif provider_name == "huggingface":
                    response = self._call_huggingface(api_key, prompt, max_tokens, temperature, model)
                elif provider_name == "openai":
                    response = self._call_openai(api_key, prompt, max_tokens, temperature, model)
                elif provider_name == "google":
                    response = self._call_google(api_key, prompt, max_tokens, temperature, model)
                else:
                    raise Exception(f"Unknown provider: {provider_name}")

                # Log successful usage
                tokens_used = response.get("tokens_used", max_tokens)
                self.api_manager.log_usage(provider_name, tokens_used)

                logger.info(f"✅ Request successful with {provider_name} ({tokens_used} tokens)")
                # Reset failure count on success
                if provider_name in self._provider_failures:
                    self._provider_failures.pop(provider_name, None)
                return {
                    "provider": provider_name,
                    "response": response,
                    "tokens_used": tokens_used,
                    "model": model
                }
            except ProviderUnavailableError as e:
                # Missing library or configuration - mark provider unavailable long-term and stop retrying
                logger.error(f"❌ Provider {provider_name} unavailable: {e}")
                from datetime import datetime, timedelta
                st = self._provider_failures.get(provider_name, {'count': 0})
                st['count'] = self.failure_threshold
                st['open_until'] = (datetime.now() + timedelta(hours=24)).timestamp()
                self._provider_failures[provider_name] = st
                raise
            except RateLimitError as e:
                # Provider informed us of rate limit; open circuit until reset
                logger.warning(f"⚠️ [{provider_name}] Rate limited: {e}")
                from datetime import datetime, timedelta
                reset_seconds = getattr(e, 'reset_seconds', None) or (self.cooldown_seconds * 10)
                st = self._provider_failures.get(provider_name, {'count': 0})
                st['count'] = self.failure_threshold
                st['open_until'] = (datetime.now() + timedelta(seconds=reset_seconds)).timestamp()
                self._provider_failures[provider_name] = st
                raise
            except Exception as e:
                last_exc = e
                logger.warning(f"⚠️ [{provider_name}] Attempt {attempt} failed: {e}")
                # simple exponential backoff
                import time
                time.sleep(0.2 * (2 ** (attempt - 1)))
                continue

        # If we reach here, all attempts failed for this provider
        raise last_exc
    
    def _call_cohere(self, api_key: str, prompt: str, max_tokens: int, temperature: float, model: str) -> Dict:
        """Call Cohere API"""
        try:
            import cohere
            co = cohere.Client(api_key)
            response = co.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model
            )
            text = response.generations[0].text
            # Estimate tokens (rough approximation)
            tokens_used = len(prompt.split()) + len(text.split())
            return {
                "text": text,
                "tokens_used": tokens_used
            }
        except ImportError:
            raise ProviderUnavailableError("Cohere library not installed. Run: pip install cohere")
    
    def _call_ai21(self, api_key: str, prompt: str, max_tokens: int, temperature: float, model: str) -> Dict:
        """Call AI21 API"""
        try:
            import requests
            response = requests.post(
                f"https://api.ai21.com/studio/v1/{model}/complete",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "prompt": prompt,
                    "maxTokens": max_tokens,
                    "temperature": temperature
                }
            )
            # Detect rate limit explicitly
            if response.status_code == 429:
                ra = response.headers.get('Retry-After')
                try:
                    reset_seconds = int(ra) if ra and str(ra).isdigit() else None
                except Exception:
                    reset_seconds = None
                raise RateLimitError("AI21 rate limited", reset_seconds=reset_seconds)
            response.raise_for_status()
            data = response.json()
            text = data["completions"][0]["data"]["text"]
            tokens_used = len(prompt.split()) + len(text.split())
            return {
                "text": text,
                "tokens_used": tokens_used
            }
        except ImportError:
            raise ProviderUnavailableError("Requests library not installed. Run: pip install requests")
        except Exception as e:
            # Map HTTP 429 to RateLimitError when requests raises
            try:
                import requests as _req
                if isinstance(e, _req.HTTPError) and getattr(e, 'response', None) is not None and e.response.status_code == 429:
                    ra = e.response.headers.get('Retry-After')
                    try:
                        reset_seconds = int(ra) if ra and str(ra).isdigit() else None
                    except Exception:
                        reset_seconds = None
                    raise RateLimitError(str(e), reset_seconds=reset_seconds)
            except Exception:
                pass
            err_str = str(e)
            if '429' in err_str or 'rate limit' in err_str.lower():
                raise RateLimitError(err_str)
            raise
    
    def _call_groq(self, api_key: str, prompt: str, max_tokens: int, temperature: float, model: str) -> Dict:
        """Call Groq API"""
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return {
                "text": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens
            }
        except ImportError:
            raise ProviderUnavailableError("Groq library not installed. Run: pip install groq")
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate limit' in err_str.lower():
                raise RateLimitError(err_str)
            raise
    
    def _call_huggingface(self, api_key: str, prompt: str, max_tokens: int, temperature: float, model: str) -> Dict:
        """Call HuggingFace Inference API"""
        try:
            import requests
            API_URL = f"https://api-inference.huggingface.co/models/{model}"
            headers = {"Authorization": f"Bearer {api_key}"}
            
            response = requests.post(
                API_URL,
                headers=headers,
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": max_tokens,
                        "temperature": temperature
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list) and len(data) > 0:
                text = data[0].get("generated_text", "")
            else:
                text = data.get("generated_text", str(data))
            
            tokens_used = len(prompt.split()) + len(text.split())
            return {
                "text": text,
                "tokens_used": tokens_used
            }
        except ImportError:
            raise ProviderUnavailableErrornavailableError("Requests library not installed. Run: pip install requests")
    
    def _call_openai(self, api_key: str, prompt: str, max_tokens: int, temperature: float, model: str) -> Dict:
        """Call OpenAI API"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return {
                "text": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens
            }
        except ImportError:
            raise ProviderUnavailableError("OpenAI library not installed. Run: pip install openai")
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate limit' in err_str.lower():
                raise RateLimitError(err_str)
            raise
    
    def _call_google(self, api_key: str, prompt: str, max_tokens: int, temperature: float, model: str) -> Dict:
        """Call Google Gemini API"""
        try:
            import google.genai as genai
            genai.configure(api_key=api_key)
            model_obj = genai.GenerativeModel(model)
            
            response = model_obj.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            text = response.text
            tokens_used = len(prompt.split()) + len(text.split())
            return {
                "text": text,
                "tokens_used": tokens_used
            }
        except ImportError:
            raise ProviderUnavailableError("Google AI library not installed. Run: pip install google-genai")
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate limit' in err_str.lower():
                raise RateLimitError(err_str)
            raise
    
    def get_stats(self) -> Dict:
        """Get usage statistics"""
        return self.api_manager.get_usage_stats()
    
    def estimate_lifespan(self, avg_tokens_per_day: int = 10000) -> Dict:
        """Estimate remaining lifespan of API keys"""
        return self.api_manager.estimate_remaining_days(avg_tokens_per_day)
    
    def reset_usage(self, provider_name: Optional[str] = None):
        """Reset usage for testing purposes"""
        if provider_name:
            self.api_manager.reset_provider_usage(provider_name)
        else:
            logger.warning("⚠️ Use api_manager.reset_provider_usage(provider_name) for specific provider")

