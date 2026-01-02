"""Base agent class for all trading agents."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from agents.state import AgentState
from agents.llm_provider_manager import get_llm_manager
from config.settings import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all trading agents.
    Provides common functionality: LLM client, prompt loading, state updates.
    """
    
    def __init__(self, agent_name: str, system_prompt: Optional[str] = None):
        """Initialize base agent."""
        self.agent_name = agent_name
        self.system_prompt = system_prompt or self._get_default_prompt()
        # Use multi-provider manager for automatic fallback
        self.llm_manager = get_llm_manager()
        # Keep old client for backward compatibility (will use manager)
        self.llm_client = None  # Deprecated - use llm_manager instead
        logger.info(f"Initialized {agent_name} agent with multi-provider LLM manager")
    
    def _initialize_llm_client(self):
        """Initialize LLM client (Groq, OpenAI, Azure OpenAI, Ollama, Hugging Face, Together AI, or Gemini)."""
        if settings.llm_provider == "groq":
            if not settings.groq_api_key:
                raise ValueError("No Groq API key configured. Set GROQ_API_KEY in .env file.")
            try:
                from groq import Groq
                return Groq(api_key=settings.groq_api_key)
            except ImportError:
                raise ImportError("Groq package not installed. Run: pip install groq")
        elif settings.llm_provider == "azure":
            if settings.azure_openai_endpoint and settings.azure_openai_api_key:
                from openai import AzureOpenAI
                return AzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=settings.azure_openai_endpoint
                )
            else:
                raise ValueError("Azure OpenAI credentials not configured.")
        elif settings.llm_provider == "openai":
            if settings.openai_api_key:
                return OpenAI(api_key=settings.openai_api_key)
            else:
                raise ValueError("No OpenAI API key configured. Set OPENAI_API_KEY in .env file.")
        elif settings.llm_provider == "ollama":
            # Ollama - completely free, runs locally
            try:
                from openai import OpenAI
                # Ollama uses OpenAI-compatible API
                return OpenAI(
                    api_key="ollama",  # Not used but required
                    base_url=settings.ollama_base_url
                )
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
        elif settings.llm_provider == "huggingface":
            # Hugging Face Inference API - free tier available
            if not settings.huggingface_api_key:
                raise ValueError("No Hugging Face API key configured. Set HUGGINGFACE_API_KEY in .env file.")
            try:
                # Hugging Face is handled directly in _call_llm, return a dummy client
                from huggingface_hub import InferenceClient
                return InferenceClient(token=settings.huggingface_api_key)
            except ImportError:
                raise ImportError("huggingface_hub package not installed. Run: pip install huggingface_hub")
        elif settings.llm_provider == "together":
            # Together AI - free tier available
            if not settings.together_api_key:
                raise ValueError("No Together AI API key configured. Set TOGETHER_API_KEY in .env file.")
            try:
                from openai import OpenAI
                return OpenAI(
                    api_key=settings.together_api_key,
                    base_url="https://api.together.xyz/v1"
                )
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
        elif settings.llm_provider == "gemini":
            # Google Gemini - free tier available
            if not settings.google_api_key:
                raise ValueError("No Google API key configured. Set GOOGLE_API_KEY in .env file.")
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.google_api_key)
                # Return a wrapper that mimics OpenAI interface
                return GeminiClient(api_key=settings.google_api_key)
            except ImportError:
                raise ImportError("Google Generative AI package not installed. Run: pip install google-generativeai")
        else:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}. Use 'groq', 'openai', 'azure', 'ollama', 'huggingface', 'together', or 'gemini'.")
    
    @abstractmethod
    def _get_default_prompt(self) -> str:
        """Get default system prompt for this agent."""
        pass
    
    def _call_llm(self, user_message: str, temperature: Optional[float] = None) -> str:
        """
        Call LLM with system prompt and user message.
        Uses multi-provider manager with automatic fallback.
        Returns the response text.
        """
        if temperature is None:
            temperature = settings.llm_temperature
        
        try:
            logger.info(f"🔵 [{self.agent_name}] Calling LLM...")
            # Use multi-provider manager for automatic fallback
            response = self.llm_manager.call_llm(
                system_prompt=self.system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=settings.max_tokens
            )
            logger.info(f"✅ [{self.agent_name}] LLM response received ({len(response)} chars)")
            return response
            
        except Exception as e:
            error_str = str(e)
            # Check if all providers failed - if so, log and re-raise
            if "All LLM providers failed" in error_str:
                logger.error(f"❌ [{self.agent_name}] All LLM providers failed: {e}")
            else:
                logger.warning(f"⚠️ [{self.agent_name}] LLM call failed, will retry with fallback: {e}")
            # Re-raise to let caller handle (agents will use defaults if needed)
            raise
    
    def _call_llm_structured(self, user_message: str, response_format: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call LLM with structured output format.
        Returns parsed JSON response.
        """
        import json
        
        logger.info(f"🔵 [{self.agent_name}] Calling LLM for structured output...")
        
        # Add format instruction to user message
        format_instruction = f"\n\nRespond in JSON format matching this schema: {json.dumps(response_format, indent=2)}"
        full_message = user_message + format_instruction
        
        try:
            response_text = self._call_llm(full_message, temperature=0.1)  # Lower temperature for structured output
            logger.info(f"✅ [{self.agent_name}] LLM response received for structured output ({len(response_text)} chars)")
        except Exception as e:
            logger.error(f"❌ [{self.agent_name}] LLM call failed in _call_llm_structured: {e}")
            raise
        
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Clean up the text - remove any leading/trailing whitespace
            response_text = response_text.strip()
            
            # Try to find JSON object boundaries
            # Look for first { and last }
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                # Extract just the JSON part
                json_text = response_text[start_idx:end_idx + 1]
                return json.loads(json_text)
            else:
                # Fallback: try parsing the whole thing
                return json.loads(response_text)
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ [{self.agent_name}] Failed to parse JSON response: {e}")
            logger.error(f"❌ [{self.agent_name}] Response text (first 500 chars): {response_text[:500]}")
            # Try to extract just the first valid JSON object
            try:
                # Find first complete JSON object
                brace_count = 0
                start = response_text.find('{')
                if start != -1:
                    for i in range(start, len(response_text)):
                        if response_text[i] == '{':
                            brace_count += 1
                        elif response_text[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_text = response_text[start:i+1]
                                return json.loads(json_text)
            except:
                pass
            raise
    
    @abstractmethod
    def process(self, state: AgentState) -> AgentState:
        """
        Process the agent state and return updated state.
        This is the main method that each agent must implement.
        """
        pass
    
    def update_state(self, state: AgentState, output: Dict[str, Any], explanation: str = "") -> None:
        """Update agent state with output and explanation."""
        state.update_agent_output(self.agent_name, output)
        if explanation:
            state.add_explanation(self.agent_name, explanation)
    
    def _retry_on_error(self, func, max_retries: int = 3, delay: float = 1.0):
        """Retry a function call on error."""
        import time
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Max retries reached for {self.agent_name}: {e}")
                    raise
                logger.warning(f"Retry {attempt + 1}/{max_retries} for {self.agent_name}: {e}")
                time.sleep(delay * (attempt + 1))  # Exponential backoff

