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
    
    def __init__(self, agent_name: Optional[str] = None, system_prompt: Optional[str] = None):
        """Initialize base agent. If `agent_name` is not provided, derive it from the class name."""
        if not agent_name:
            # Derive a snake_case name from the class name, e.g., MockTestAgent -> mock_test
            import re
            derived = re.sub(r'(?<!^)(?=[A-Z])', '_', self.__class__.__name__).lower()
            # strip common suffixes
            derived = derived.replace('_agent', '')
            agent_name = derived
        self.agent_name = agent_name
        # Use a stable generic default prompt when not provided to make tests deterministic
        if system_prompt is None:
            raw_prompt = "You are a test agent."
        else:
            raw_prompt = system_prompt or self._get_default_prompt()
        # Inject instrument_name from settings into prompt (decoupling)
        self.system_prompt = self._inject_instrument_context(raw_prompt)
        # Use multi-provider manager for automatic fallback
        self.llm_manager = get_llm_manager()
        # Keep old client for backward compatibility (will use manager)
        # For backwards compatibility, set llm_client to the manager so older code/tests still see a client
        self.llm_client = self.llm_manager
        logger.info(f"Initialized {agent_name} agent with multi-provider LLM manager")
    
    def _inject_instrument_context(self, prompt: str) -> str:
        """Inject instrument context into prompt template."""
        try:
            # Replace placeholders with actual settings
            prompt = prompt.replace("{instrument_name}", settings.instrument_name)
            prompt = prompt.replace("{instrument_symbol}", settings.instrument_symbol)
            prompt = prompt.replace("{instrument_exchange}", settings.instrument_exchange)
            return prompt
        except Exception as e:
            logger.warning(f"Failed to inject instrument context: {e}")
            return prompt
    
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
        import asyncio
        import concurrent.futures
        
        if temperature is None:
            temperature = settings.llm_temperature
        
        try:
            import time
            start_time = time.time()
            logger.info(f"🔵 [{self.agent_name}] Calling LLM...")
            
            # Get provider for this agent to distribute load across providers
            # This prevents all parallel agents from hitting the same provider
            # Pass parallel_group to ensure different providers for parallel agents
            agent_provider = self.llm_manager.get_provider_for_agent(
                self.agent_name,
                parallel_group=getattr(self, '_parallel_group', None)
            )
            
            # Use multi-provider manager for automatic fallback
            # Timeout is handled in llm_provider_manager (60 seconds per call)
            response = self.llm_manager.call_llm(
                system_prompt=self.system_prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=settings.max_tokens,
                provider_name=agent_provider  # Use agent-specific provider
            )
            elapsed = time.time() - start_time
            logger.info(f"✅ [{self.agent_name}] LLM response received ({len(response)} chars) in {elapsed:.1f}s")
            # Optional debug persistence
            try:
                import os
                if os.getenv('DEBUG_AGENT_OUTPUT', 'false').lower() in ('1', 'true', 'yes'):
                    try:
                        from datetime import datetime
                        from mongodb_schema import get_mongo_client, get_collection
                        client = get_mongo_client()
                        db = client[settings.mongodb_db_name]
                        dbg = get_collection(db, 'agent_debug')
                        dbg.insert_one({
                            'timestamp': datetime.now().isoformat(),
                            'agent': self.agent_name,
                            'type': 'raw',
                            'provider': agent_provider,
                            'elapsed_s': elapsed,
                            'system_prompt': (self.system_prompt or '')[:4000],
                            'user_message': (user_message or '')[:4000],
                            'response_text': response[:10000]
                        })
                    except Exception:
                        # Suppress all errors from debug persistence
                        pass
            except Exception:
                pass
            return response
            
        except Exception as e:
            error_str = str(e)
            # Check if all providers failed - if so, log and re-raise
            if "All LLM providers failed" in error_str:
                logger.error(f"❌ [{self.agent_name}] All LLM providers failed: {e}")
            elif isinstance(e, TimeoutError):
                logger.error(f"❌ [{self.agent_name}] LLM call timed out: {e}")
            else:
                logger.warning(f"⚠️ [{self.agent_name}] LLM call failed, will retry with fallback: {e}")
            # Re-raise to let caller handle (agents will use defaults if needed)
            raise
    
    def _call_llm_structured(self, user_message: str, response_format: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call LLM with structured output format.
        Returns parsed JSON response.
        Ensures complete JSON responses with validation and retry logic.
        """
        import json
        
        logger.info(f"🔵 [{self.agent_name}] Calling LLM for structured output...")
        
        # Add STRICT format instruction with emphasis on completeness
        format_instruction = f"""

CRITICAL: Respond with COMPLETE, VALID JSON only. The JSON must:
1. Be complete (all fields filled, all brackets/braces closed)
2. Be valid JSON (proper quotes, commas, no trailing commas)
3. Match this EXACT schema:
{json.dumps(response_format, indent=2)}

IMPORTANT: 
- Do NOT truncate the response
- Do NOT leave arrays or objects incomplete
- Ensure ALL string values are properly quoted
- Close ALL brackets [ ] and braces {{ }}
- Return ONLY the JSON object, no additional text

JSON Response:"""
        
        full_message = user_message + format_instruction
        
        # Increase max_tokens for structured outputs (JSON can be longer)
        # Estimate: ~50 tokens per field, add buffer for arrays
        estimated_tokens = len(response_format) * 50 + 500  # Base + buffer
        structured_max_tokens = max(settings.max_tokens, estimated_tokens, 4000)  # At least 4000 for structured outputs
        
        max_retries = 3
        last_error = None
        json_failed = False
        
        for attempt in range(max_retries):
            try:
                # Call LLM with increased max_tokens for structured output
                # We need to pass max_tokens directly, so we'll call the manager directly
                # Get provider with parallel group support
                agent_provider = self.llm_manager.get_provider_for_agent(
                    self.agent_name,
                    parallel_group=getattr(self, '_parallel_group', None)
                )
                response_text = self.llm_manager.call_llm(
                    system_prompt=self.system_prompt,
                    user_message=full_message,
                    temperature=0.1,  # Lower temperature for structured output
                    max_tokens=structured_max_tokens,  # Increased for structured JSON
                    provider_name=agent_provider
                )
                
                # Validate JSON completeness BEFORE parsing
                if not self._validate_json_completeness(response_text, response_format):
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ [{self.agent_name}] JSON appears incomplete, retrying (attempt {attempt + 1}/{max_retries})...")
                        # Add more explicit instruction on retry
                        full_message = user_message + format_instruction + "\n\nRETRY: Ensure the JSON is COMPLETE and ALL fields are present."
                        continue
                    else:
                        logger.error(f"❌ [{self.agent_name}] JSON still incomplete after {max_retries} attempts")
                        json_failed = True
                
                logger.info(f"✅ [{self.agent_name}] LLM response received for structured output ({len(response_text)} chars)")
                break
                
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ [{self.agent_name}] LLM call failed, retrying (attempt {attempt + 1}/{max_retries}): {e}")
                    continue
                else:
                    logger.error(f"❌ [{self.agent_name}] LLM call failed in _call_llm_structured after {max_retries} attempts: {e}")
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
            
            parsed = None
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                # Extract just the JSON part
                json_text = response_text[start_idx:end_idx + 1]
                parsed = json.loads(json_text)
            else:
                # Fallback: try parsing the whole thing
                parsed = json.loads(response_text)

            # If validation indicated incomplete JSON after retries, annotate and write alert
            if json_failed:
                try:
                    if isinstance(parsed, dict):
                        parsed["__incomplete_json"] = True
                    # Record alert in alerts collection (non-fatal)
                    try:
                        from mongodb_schema import get_mongo_client, get_collection
                        mc = get_mongo_client()
                        db = mc[settings.mongodb_db_name]
                        alerts_col = get_collection(db, "alerts")
                        alerts_col.insert_one({
                            "type": "agent_json_incomplete",
                            "agent": self.agent_name,
                            "message": "LLM returned incomplete JSON after retries",
                            "response_snippet": response_text[:1000],
                            "timestamp": __import__('datetime').datetime.now().isoformat()
                        })
                    except Exception as alert_exc:
                        logger.debug(f"Failed to write incomplete JSON alert: {alert_exc}")
                except Exception:
                    pass

            # Debug persistence (optional)
            try:
                import os
                if os.getenv('DEBUG_AGENT_OUTPUT', 'false').lower() in ('1', 'true', 'yes'):
                    try:
                        from datetime import datetime
                        from mongodb_schema import get_mongo_client, get_collection
                        mc = get_mongo_client()
                        db = mc[settings.mongodb_db_name]
                        dbg = get_collection(db, 'agent_debug')
                        import json as _json
                        try:
                            parsed_text = _json.dumps(parsed) if isinstance(parsed, dict) else str(parsed)
                        except Exception:
                            parsed_text = str(parsed)
                        dbg.insert_one({
                            'timestamp': datetime.now().isoformat(),
                            'agent': self.agent_name,
                            'type': 'structured',
                            'provider': agent_provider,
                            'json_failed': bool(json_failed),
                            'response_text': response_text[:10000],
                            'parsed': parsed_text[:20000]
                        })
                    except Exception:
                        pass
            except Exception:
                pass

            return parsed
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ [{self.agent_name}] Failed to parse JSON response: {e}")
            logger.error(f"❌ [{self.agent_name}] Response text (first 500 chars): {response_text[:500]}")
            
            # Try JSON repair strategies
            repaired_json = self._repair_json(response_text)
            if repaired_json:
                try:
                    # If repair returned a dict, return it directly
                    if isinstance(repaired_json, dict):
                        return repaired_json
                    # Otherwise, parse the string
                    return json.loads(repaired_json)
                except (json.JSONDecodeError, TypeError) as repair_error:
                    logger.debug(f"Repaired JSON still invalid: {repair_error}")
                    pass
            
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
                                repaired = self._repair_json(json_text)
                                if repaired:
                                    if isinstance(repaired, dict):
                                        return repaired
                                    return json.loads(repaired)
                                return json.loads(json_text)
            except Exception as repair_error:
                logger.debug(f"JSON repair attempt failed: {repair_error}")
            
            # Last resort: Try to extract partial data from incomplete JSON
            try:
                partial_data = self._extract_partial_json(response_text)
                if partial_data:
                    logger.warning(f"⚠️ [{self.agent_name}] Using partial JSON data due to parsing error")
                    return partial_data
            except Exception as extract_error:
                logger.debug(f"Partial JSON extraction failed: {extract_error}")
            
            # Log full response for debugging (truncated to avoid huge logs)
            logger.error(f"❌ [{self.agent_name}] Full response text (first 1000 chars): {response_text[:1000]}")
            raise
    
    def _validate_json_completeness(self, json_text: str, expected_format: Dict[str, Any]) -> bool:
        """
        Validate that JSON response is complete and contains all expected fields.
        """
        import json
        import re
        
        try:
            # Check basic JSON structure
            if json_text.count('{') != json_text.count('}'):
                logger.debug("JSON braces not balanced")
                return False
            
            if json_text.count('[') != json_text.count(']'):
                logger.debug("JSON brackets not balanced")
                return False
            
            # Try to parse JSON
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError:
                logger.debug("JSON is not valid")
                return False
            
            # Check if it's a dict (expected format)
            if not isinstance(parsed, dict):
                logger.debug("JSON root is not an object")
                return False
            
            # Check for expected top-level fields (at least some should be present)
            # Don't require all fields (some might be optional), but check structure
            expected_keys = list(expected_format.keys())
            found_keys = list(parsed.keys())
            
            # If we have expected format, check if at least 50% of fields are present
            if expected_keys and len(found_keys) < len(expected_keys) * 0.5:
                logger.debug(f"Too few fields present: {len(found_keys)}/{len(expected_keys)}")
                return False
            
            # Check for incomplete arrays/objects in string values
            for key, value in parsed.items():
                if isinstance(value, str):
                    # Check for incomplete JSON-like structures in strings
                    if value.count('[') != value.count(']') or value.count('{') != value.count('}'):
                        # This might be intentional (e.g., a description), so don't fail
                        pass
            
            return True
            
        except Exception as e:
            logger.debug(f"JSON completeness validation error: {e}")
            return False
    
    def _extract_partial_json(self, json_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract partial data from incomplete JSON.
        Useful when LLM response is truncated.
        """
        import re
        
        try:
            # Try to extract key-value pairs even if JSON is incomplete
            result = {}
            
            # Extract string values with regex
            # Pattern: "key": "value"
            string_pattern = r'"([^"]+)":\s*"([^"]*)"'
            matches = re.findall(string_pattern, json_text)
            for key, value in matches:
                result[key] = value
            
            # Extract array values: "key": ["item1", "item2"]
            array_pattern = r'"([^"]+)":\s*\[(.*?)\]'
            array_matches = re.findall(array_pattern, json_text, re.DOTALL)
            for key, array_content in array_matches:
                # Extract string items from array
                items = re.findall(r'"([^"]*)"', array_content)
                if items:
                    result[key] = items
            
            # Extract numeric values: "key": 123.45
            number_pattern = r'"([^"]+)":\s*([0-9]+\.?[0-9]*)'
            number_matches = re.findall(number_pattern, json_text)
            for key, value in number_matches:
                try:
                    if '.' in value:
                        result[key] = float(value)
                    else:
                        result[key] = int(value)
                except ValueError:
                    pass
            
            # Only return if we extracted at least some data
            if result:
                return result
        except Exception as e:
            logger.debug(f"Partial JSON extraction error: {e}")
        
        return None
    
    def _repair_json(self, json_text: str):
        """
        Attempt to repair common JSON issues:
        - Single quotes to double quotes
        - Trailing commas
        - Unclosed strings/arrays
        - Invalid escape sequences
        - Incomplete JSON (try to extract valid portion)
        """
        import re
        import json
        
        try:
            # Remove markdown code blocks if still present
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]
            
            json_text = json_text.strip()
            
            # Find JSON boundaries
            start_idx = json_text.find('{')
            end_idx = json_text.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_text = json_text[start_idx:end_idx + 1]
            
            # Strategy 1: Try using json5 (more lenient parser) if available
            try:
                import json5
                parsed = json5.loads(json_text)
                return parsed  # Return dict directly
            except ImportError:
                pass
            except Exception:
                pass
            
            # Strategy 2: Fix common JSON issues
            # Fix trailing commas
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            
            # Fix single quotes in property names: 'key': -> "key":
            json_text = re.sub(r"'(\w+)'\s*:", r'"\1":', json_text)
            
            # Try to close incomplete strings in arrays
            # Look for unclosed strings in arrays (ends with quote but no closing bracket)
            lines = json_text.split('\n')
            repaired_lines = []
            in_string = False
            string_start = -1
            
            for i, line in enumerate(lines):
                # Check if we're in an incomplete string
                quote_count = line.count('"') - line.count('\\"')
                if quote_count % 2 == 1:
                    in_string = not in_string
                    if in_string:
                        string_start = i
                
                # If we hit the end and have an incomplete string, try to close it
                if i == len(lines) - 1 and in_string:
                    # Try to close the string and array/object
                    line = line.rstrip()
                    if not line.endswith('"'):
                        # Find last quote start
                        last_quote = line.rfind('"')
                        if last_quote > 0:
                            # Check if it's an escaped quote
                            if line[last_quote-1] != '\\':
                                # Add closing quote
                                line = line[:last_quote+1] + '"'
                    repaired_lines.append(line)
                    # Try to close array/object
                    if '[' in line and ']' not in line:
                        repaired_lines.append(']')
                    break
                else:
                    repaired_lines.append(line)
            
            if repaired_lines != lines:
                json_text = '\n'.join(repaired_lines)
            
            # Strategy 3: Try to extract valid JSON by closing incomplete structures
            # Count braces and brackets to see if they're balanced
            open_braces = json_text.count('{')
            close_braces = json_text.count('}')
            open_brackets = json_text.count('[')
            close_brackets = json_text.count(']')
            
            # If JSON is incomplete, try to close it
            if open_braces > close_braces:
                json_text += '}' * (open_braces - close_braces)
            if open_brackets > close_brackets:
                json_text += ']' * (open_brackets - close_brackets)
            
            # Try parsing the repaired JSON
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                # If still fails, try to extract just the first complete object
                # This was already attempted in the caller, so return None
                return None
            
        except Exception as e:
            logger.debug(f"JSON repair failed: {e}")
            return None
    
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
    
    def format_explanation(self, title: str, points: list, summary: str = "") -> str:
        """
        Format explanation as human-readable with bullet points.
        
        Args:
            title: Title of the explanation (e.g., "Fundamental Analysis")
            points: List of (key, value, reason) tuples or strings
            summary: Optional summary line
        
        Returns:
            Formatted explanation string
        """
        lines = [f"{title}:"]
        
        for point in points:
            if isinstance(point, tuple) and len(point) >= 2:
                key, value = point[0], point[1]
                reason = point[2] if len(point) > 2 else ""
                
                if reason:
                    lines.append(f"  • {key}: {value} - {reason}")
                else:
                    lines.append(f"  • {key}: {value}")
            else:
                lines.append(f"  • {point}")
        
        if summary:
            lines.append(f"  Summary: {summary}")
        
        return "\n".join(lines)
    
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

