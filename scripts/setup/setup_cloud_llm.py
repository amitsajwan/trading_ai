"""Quick setup script for free cloud LLM providers."""

import os
import sys
from pathlib import Path

def update_env_file(env_path: Path, updates: dict):
    """Update .env file with new values."""
    env_vars = {}
    
    # Read existing .env if it exists
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update with new values
    env_vars.update(updates)
    
    # Write back
    with open(env_path, "w") as f:
        f.write("# GenAI Trading System Configuration\n")
        f.write("# LLM Provider: Cloud (Fast & Free)\n\n")
        
        # Write all variables
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")

def main():
    """Setup cloud LLM provider."""
    print("=" * 60)
    print("Cloud LLM Provider Setup")
    print("=" * 60)
    print("\nThis script helps you configure FREE cloud LLM providers.")
    print("These are MUCH faster than local Ollama!\n")
    
    env_path = Path(".env")
    
    # Check what API keys are already available
    print("Checking for existing API keys...\n")
    
    groq_key = os.getenv("GROQ_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    providers_found = []
    if groq_key:
        providers_found.append("Groq")
    if google_key:
        providers_found.append("Gemini")
    if openrouter_key:
        providers_found.append("OpenRouter")
    
    if providers_found:
        print(f"✅ Found API keys for: {', '.join(providers_found)}\n")
    else:
        print("⚠️  No API keys found in environment.\n")
        print("You can:")
        print("1. Set them in .env file manually")
        print("2. Export them in your shell")
        print("3. Get free keys from:")
        print("   - Groq: https://console.groq.com")
        print("   - Gemini: https://aistudio.google.com/app/apikey")
        print("   - OpenRouter: https://openrouter.ai\n")
    
    # Ask which provider to use
    print("Available FREE providers (fastest to slowest):")
    print("1. Groq - FASTEST (~1-2s per call)")
    print("2. Gemini - Fast (~2-5s per call)")
    print("3. OpenRouter - Medium (~3-8s per call)")
    print("4. Auto-select (uses fastest available)\n")
    
    choice = input("Select provider (1-4) or press Enter for auto-select: ").strip()
    
    updates = {}
    
    if choice == "1" or (not choice and groq_key):
        # Groq
        if not groq_key:
            groq_key = input("Enter GROQ_API_KEY (or press Enter to skip): ").strip()
            if groq_key:
                updates["GROQ_API_KEY"] = groq_key
        if groq_key or updates.get("GROQ_API_KEY"):
            updates["LLM_PROVIDER"] = "groq"
            updates["GROQ_MODEL"] = "llama-3.1-8b-instant"  # Fastest Groq model
            print("\n✅ Configured Groq (fastest free provider)")
    
    elif choice == "2":
        # Gemini
        if not google_key:
            google_key = input("Enter GOOGLE_API_KEY (or press Enter to skip): ").strip()
            if google_key:
                updates["GOOGLE_API_KEY"] = google_key
        if google_key or updates.get("GOOGLE_API_KEY"):
            updates["LLM_PROVIDER"] = "gemini"
            print("\n✅ Configured Gemini")
    
    elif choice == "3":
        # OpenRouter
        if not openrouter_key:
            openrouter_key = input("Enter OPENROUTER_API_KEY (or press Enter to skip): ").strip()
            if openrouter_key:
                updates["OPENROUTER_API_KEY"] = openrouter_key
        if openrouter_key or updates.get("OPENROUTER_API_KEY"):
            updates["LLM_PROVIDER"] = "openrouter"
            updates["OPENROUTER_MODEL"] = "meta-llama/llama-3.2-3b-instruct:free"
            print("\n✅ Configured OpenRouter")
    
    else:
        # Auto-select (multi-provider mode)
        updates["LLM_PROVIDER"] = "multi"
        if groq_key:
            updates["GROQ_MODEL"] = "llama-3.1-8b-instant"
        if openrouter_key:
            updates["OPENROUTER_MODEL"] = "meta-llama/llama-3.2-3b-instruct:free"
        print("\n✅ Configured multi-provider mode (auto-selects fastest)")
    
    if updates:
        update_env_file(env_path, updates)
        print(f"\n✅ Updated {env_path}")
        print("\nNext steps:")
        print("1. Run: python scripts/test_local_llm.py  # Test LLM")
        print("2. Run: python scripts/verify_all_components.py  # Full verification")
    else:
        print("\n⚠️  No changes made. Make sure API keys are set in .env or environment.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup cancelled")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


