"""Setup guide for free LLM providers."""

import os
from pathlib import Path
from dotenv import load_dotenv, set_key

env_path = Path(".env")
load_dotenv(env_path)

def setup_ollama():
    """Setup Ollama - completely free, runs locally."""
    print("=" * 60)
    print("Ollama Setup (100% FREE - Runs Locally)")
    print("=" * 60)
    print("\n1. Install Ollama:")
    print("   Windows: Download from https://ollama.com/download")
    print("   Mac/Linux: curl -fsSL https://ollama.com/install.sh | sh")
    print("\n2. Pull a model (choose one):")
    print("   ollama pull llama3.2:3b        # Small, fast")
    print("   ollama pull llama3.1:8b         # Balanced")
    print("   ollama pull mistral:7b          # Good quality")
    print("   ollama pull qwen2.5:7b         # Alternative")
    print("\n3. Verify Ollama is running:")
    print("   curl http://localhost:11434/api/tags")
    print("\n4. Update .env:")
    
    model = input("\nEnter model name (e.g., llama3.2:3b): ").strip() or "llama3.2:3b"
    
    set_key(env_path, "LLM_PROVIDER", "ollama")
    set_key(env_path, "LLM_MODEL", model)
    set_key(env_path, "OLLAMA_BASE_URL", "http://localhost:11434")
    
    print("\n✅ Ollama configured!")
    print(f"   Provider: ollama")
    print(f"   Model: {model}")
    print("\nNote: Ollama runs completely free on your machine.")
    print("No API keys needed, no rate limits!")

def setup_huggingface():
    """Setup Hugging Face Inference API - free tier."""
    print("=" * 60)
    print("Hugging Face Setup (FREE Tier Available)")
    print("=" * 60)
    print("\n1. Get free API key:")
    print("   Visit: https://huggingface.co/settings/tokens")
    print("   Create a token (read access is enough)")
    print("\n2. Free tier limits:")
    print("   - 1000 requests/day (free)")
    print("   - No credit card needed")
    print("\n3. Available models:")
    print("   - meta-llama/Llama-3.2-3B-Instruct")
    print("   - mistralai/Mistral-7B-Instruct-v0.2")
    print("   - microsoft/Phi-3-mini-4k-instruct")
    
    api_key = input("\nEnter Hugging Face API key: ").strip()
    if not api_key:
        print("❌ API key required")
        return False
    
    model = input("Enter model name (default: meta-llama/Llama-3.2-3B-Instruct): ").strip() or "meta-llama/Llama-3.2-3B-Instruct"
    
    set_key(env_path, "LLM_PROVIDER", "huggingface")
    set_key(env_path, "LLM_MODEL", model)
    set_key(env_path, "HUGGINGFACE_API_KEY", api_key)
    
    print("\n✅ Hugging Face configured!")
    print(f"   Provider: huggingface")
    print(f"   Model: {model}")

def setup_together():
    """Setup Together AI - free tier."""
    print("=" * 60)
    print("Together AI Setup (FREE Tier Available)")
    print("=" * 60)
    print("\n1. Get free API key:")
    print("   Visit: https://api.together.xyz/")
    print("   Sign up for free account")
    print("\n2. Free tier limits:")
    print("   - $25 free credits")
    print("   - No credit card needed initially")
    
    api_key = input("\nEnter Together AI API key: ").strip()
    if not api_key:
        print("❌ API key required")
        return False
    
    model = input("Enter model name (default: meta-llama/Llama-3-70b-chat-hf): ").strip() or "meta-llama/Llama-3-70b-chat-hf"
    
    set_key(env_path, "LLM_PROVIDER", "together")
    set_key(env_path, "LLM_MODEL", model)
    set_key(env_path, "TOGETHER_API_KEY", api_key)
    
    print("\n✅ Together AI configured!")
    print(f"   Provider: together")
    print(f"   Model: {model}")

def setup_gemini():
    """Setup Google Gemini - free tier."""
    print("=" * 60)
    print("Google Gemini Setup (FREE Tier Available)")
    print("=" * 60)
    print("\n1. Get free API key:")
    print("   Visit: https://aistudio.google.com/app/apikey")
    print("   Create a free API key")
    print("\n2. Free tier limits:")
    print("   - 60 requests/minute")
    print("   - 1,500 requests/day")
    print("   - No credit card needed")
    
    api_key = input("\nEnter Google API key: ").strip()
    if not api_key:
        print("❌ API key required")
        return False
    
    model = input("Enter model name (default: gemini-pro): ").strip() or "gemini-pro"
    
    set_key(env_path, "LLM_PROVIDER", "gemini")
    set_key(env_path, "LLM_MODEL", model)
    set_key(env_path, "GOOGLE_API_KEY", api_key)
    
    print("\n✅ Google Gemini configured!")
    print(f"   Provider: gemini")
    print(f"   Model: {model}")

def main():
    """Main function."""
    import sys
    
    print("=" * 60)
    print("FREE LLM Provider Setup")
    print("=" * 60)
    print("\nChoose a FREE provider:")
    print("1. Ollama - 100% FREE, runs locally (RECOMMENDED)")
    print("2. Hugging Face - Free tier (1000 requests/day)")
    print("3. Together AI - Free tier ($25 credits)")
    print("4. Google Gemini - Free tier (1500 requests/day)")
    print("\nCurrent provider:", os.getenv("LLM_PROVIDER", "groq"))
    print("=" * 60)
    
    if len(sys.argv) > 1:
        choice = sys.argv[1].lower()
    else:
        choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1" or choice == "ollama":
        setup_ollama()
    elif choice == "2" or choice == "huggingface":
        setup_huggingface()
    elif choice == "3" or choice == "together":
        setup_together()
    elif choice == "4" or choice == "gemini":
        setup_gemini()
    else:
        print("Invalid choice. Run again with: python scripts/setup_free_llm.py [1-4]")

if __name__ == "__main__":
    main()

