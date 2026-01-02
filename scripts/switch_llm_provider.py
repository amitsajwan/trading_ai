"""Switch LLM provider to avoid rate limits."""

import os
from pathlib import Path
from dotenv import load_dotenv, set_key

# Load existing .env
env_path = Path(".env")
load_dotenv(env_path)

def switch_to_openai():
    """Switch to OpenAI provider."""
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in .env")
        print("\nTo use OpenAI:")
        print("1. Get API key from: https://platform.openai.com/api-keys")
        print("2. Add to .env: OPENAI_API_KEY=sk-...")
        print("3. Run this script again")
        return False
    
    set_key(env_path, "LLM_PROVIDER", "openai")
    set_key(env_path, "LLM_MODEL", "gpt-4o-mini")  # Cost-effective model
    print("✅ Switched to OpenAI")
    print("   Provider: openai")
    print("   Model: gpt-4o-mini (cost-effective)")
    print("\nNote: OpenAI charges per token. Monitor usage at: https://platform.openai.com/usage")
    return True

def switch_to_azure():
    """Switch to Azure OpenAI provider."""
    if not os.getenv("AZURE_OPENAI_ENDPOINT") or not os.getenv("AZURE_OPENAI_API_KEY"):
        print("❌ Azure OpenAI credentials not found in .env")
        print("\nTo use Azure OpenAI:")
        print("1. Set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
        print("2. Set AZURE_OPENAI_API_KEY=your-key")
        print("3. Set AZURE_OPENAI_API_VERSION=2024-02-15-preview")
        print("4. Run this script again")
        return False
    
    set_key(env_path, "LLM_PROVIDER", "azure")
    set_key(env_path, "LLM_MODEL", "gpt-4o-mini")  # Or your deployed model name
    print("✅ Switched to Azure OpenAI")
    print("   Provider: azure")
    print("   Model: gpt-4o-mini")
    return True

def switch_to_groq():
    """Switch back to Groq (if you upgrade tier)."""
    if not os.getenv("GROQ_API_KEY"):
        print("❌ GROQ_API_KEY not found in .env")
        return False
    
    set_key(env_path, "LLM_PROVIDER", "groq")
    set_key(env_path, "LLM_MODEL", "llama-3.3-70b-versatile")
    print("✅ Switched to Groq")
    print("   Provider: groq")
    print("   Model: llama-3.3-70b-versatile")
    print("\nNote: Free tier has 100K tokens/day limit. Upgrade at: https://console.groq.com/settings/billing")
    return True

def show_current_config():
    """Show current LLM configuration."""
    provider = os.getenv("LLM_PROVIDER", "groq")
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    
    print("=" * 60)
    print("Current LLM Configuration")
    print("=" * 60)
    print(f"Provider: {provider}")
    print(f"Model: {model}")
    print("=" * 60)
    
    # Check available providers
    print("\nAvailable Providers:")
    print("1. OpenAI - Requires OPENAI_API_KEY")
    print("   - Models: gpt-4o, gpt-4o-mini, gpt-4-turbo")
    print("   - Cost: ~$0.15-30 per 1M tokens (depending on model)")
    print("   - Get key: https://platform.openai.com/api-keys")
    
    print("\n2. Azure OpenAI - Requires AZURE_OPENAI_ENDPOINT + API_KEY")
    print("   - Models: gpt-4o, gpt-4-turbo, etc.")
    print("   - Cost: Varies by Azure subscription")
    print("   - Setup: https://azure.microsoft.com/en-us/products/ai-services/openai-service")
    
    print("\n3. Groq (Current) - Requires GROQ_API_KEY")
    print("   - Models: llama-3.3-70b-versatile, mixtral-8x7b-32768")
    print("   - Free tier: 100K tokens/day")
    print("   - Upgrade: https://console.groq.com/settings/billing")
    print("=" * 60)

def main():
    """Main function."""
    import sys
    
    show_current_config()
    
    if len(sys.argv) > 1:
        provider = sys.argv[1].lower()
        
        if provider == "openai":
            switch_to_openai()
        elif provider == "azure":
            switch_to_azure()
        elif provider == "groq":
            switch_to_groq()
        else:
            print(f"❌ Unknown provider: {provider}")
            print("Usage: python scripts/switch_llm_provider.py [openai|azure|groq]")
    else:
        print("\nTo switch providers, run:")
        print("   python scripts/switch_llm_provider.py openai")
        print("   python scripts/switch_llm_provider.py azure")
        print("   python scripts/switch_llm_provider.py groq")

if __name__ == "__main__":
    main()

