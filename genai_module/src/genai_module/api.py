"""Public API factories for genai_module.

This is the stable import surface for consumers (Engine, agents, etc).
"""
from pathlib import Path
from typing import Optional

from .contracts import LLMClient, PromptStore
from .adapters.provider_manager import ProviderManagerClient
from .adapters.prompt_store import FilePromptStore, PromptManagerStore


def build_llm_client(legacy_manager, default_model: Optional[str] = None) -> LLMClient:
    """Build LLMClient wrapping legacy LLMProviderManager.
    
    Args:
        legacy_manager: Instance of agents.llm_provider_manager.LLMProviderManager
        default_model: Optional default model (e.g., 'llama-3.1-8b-instant')
    
    Returns:
        LLMClient instance
    
    Example:
        from genai_module.core.llm_provider_manager import LLMProviderManager
        from genai_module.api import build_llm_client
        from genai_module.contracts import LLMRequest
        
        manager = LLMProviderManager()  # Legacy manager
        client = build_llm_client(manager, default_model="groq:llama-3.1-8b-instant")
        
        req = LLMRequest(prompt="Analyze this trade", max_tokens=256)
        resp = await client.generate(req)
        print(resp.content, resp.tokens_used, resp.cost)
    """
    return ProviderManagerClient(legacy_manager, default_model=default_model)


def build_prompt_store(
    file_root: Optional[Path] = None,
    prompt_manager = None
) -> PromptStore:
    """Build PromptStore (file-backed or wrapping legacy PromptManager).
    
    Args:
        file_root: Path for file-based store (tests, local dev); mutually exclusive with prompt_manager
        prompt_manager: Legacy config.prompt_manager.PromptManager instance (production)
    
    Returns:
        PromptStore instance
    
    Example:
        # File-based for tests/local dev
        from pathlib import Path
        store = build_prompt_store(file_root=Path("./prompts"))
        await store.save("technical_agent", "Analyze price action...")
        
        # Mongo-backed for production (wraps legacy)
        from core_kernel.config.prompt_manager import PromptManager
        pm = PromptManager()
        store = build_prompt_store(prompt_manager=pm)
        prompt = await store.get("technical_agent", version="v2")
    """
    if prompt_manager is not None:
        return PromptManagerStore(prompt_manager)
    
    if file_root is None:
        file_root = Path("./prompts_default")
    
    return FilePromptStore(file_root)

