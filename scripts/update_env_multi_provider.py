"""Update .env file with multi-provider API keys."""

import os
from pathlib import Path

def update_env_file():
    """Update .env file with provided API keys."""
    env_path = Path(".env")
    
    # Get API keys from environment variables or prompt user
    api_keys = {}
    
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        groq_key = input("Enter Groq API key (or press Enter to skip): ").strip()
    if groq_key:
        api_keys["GROQ_API_KEY"] = groq_key
    
    google_key = os.getenv("GOOGLE_API_KEY")
    if not google_key:
        google_key = input("Enter Google API key (or press Enter to skip): ").strip()
    if google_key:
        api_keys["GOOGLE_API_KEY"] = google_key
    
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        openrouter_key = input("Enter OpenRouter API key (or press Enter to skip): ").strip()
    if openrouter_key:
        api_keys["OPENROUTER_API_KEY"] = openrouter_key
    
    if not api_keys:
        print("No API keys provided. Exiting.")
        return
    
    # Read existing .env if it exists
    env_vars = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    
    # Update with new keys
    env_vars.update(api_keys)
    
    # Set multi-provider mode
    env_vars["LLM_PROVIDER"] = "multi"  # Use multi-provider manager
    env_vars["LLM_MODEL"] = "auto"  # Auto-select model
    
    # Write back to .env
    with open(env_path, "w") as f:
        f.write("# Multi-Provider LLM Configuration\n")
        f.write("# System will automatically use best available provider with fallback\n\n")
        
        f.write("# LLM Provider Configuration\n")
        f.write(f"LLM_PROVIDER={env_vars.get('LLM_PROVIDER', 'multi')}\n")
        f.write(f"LLM_MODEL={env_vars.get('LLM_MODEL', 'auto')}\n")
        f.write(f"LLM_TEMPERATURE={env_vars.get('LLM_TEMPERATURE', '0.3')}\n\n")
        
        f.write("# Multi-Provider API Keys\n")
        f.write(f"GROQ_API_KEY={api_keys['GROQ_API_KEY']}\n")
        f.write(f"GOOGLE_API_KEY={api_keys['GOOGLE_API_KEY']}\n")
        f.write(f"OPENROUTER_API_KEY={api_keys['OPENROUTER_API_KEY']}\n\n")
        
        # Write other existing vars
        f.write("# Other Configuration\n")
        for key, value in env_vars.items():
            if key not in ["LLM_PROVIDER", "LLM_MODEL", "LLM_TEMPERATURE", "GROQ_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"]:
                f.write(f"{key}={value}\n")
    
    print("=" * 60)
    print("Multi-Provider LLM Configuration Updated")
    print("=" * 60)
    print("\n[OK] Configured Providers:")
    print("   1. Groq Cloud (Llama 3.3 70B, Mixtral)")
    print("   2. Google Gemini (Gemini 1.5 Flash)")
    print("   3. OpenRouter (DeepSeek R1, Mistral)")
    print("\n[OK] Features Enabled:")
    print("   - Automatic provider fallback")
    print("   - Rate limit handling")
    print("   - Provider rotation")
    print("   - Cost optimization")
    print("\n[OK] System will:")
    print("   - Use best available provider")
    print("   - Automatically fallback on errors/rate limits")
    print("   - Track usage and rate limits")
    print("   - Optimize for cost and performance")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    update_env_file()

