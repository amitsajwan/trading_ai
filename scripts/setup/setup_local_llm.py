"""Setup script for local LLM integration."""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header(text):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def check_ollama_installed():
    """Check if Ollama is installed."""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def install_ollama():
    """Install Ollama based on platform."""
    system = platform.system()
    print_header("Installing Ollama")
    
    if system == "Windows":
        print("Windows installation:")
        print("1. Download Ollama from: https://ollama.com/download/windows")
        print("2. Run the installer")
        print("3. Restart your terminal")
        print("\nAfter installation, run this script again to pull models.")
        return False
    elif system == "Linux":
        print("Installing Ollama on Linux...")
        try:
            subprocess.run(["curl", "-fsSL", "https://ollama.com/install.sh"], check=True)
            subprocess.run(["sh", "install.sh"], check=True)
            print("✅ Ollama installed successfully!")
            return True
        except Exception as e:
            print(f"❌ Error installing Ollama: {e}")
            print("Please install manually: https://ollama.com/download")
            return False
    elif system == "Darwin":  # macOS
        print("Installing Ollama on macOS...")
        try:
            subprocess.run(["curl", "-fsSL", "https://ollama.com/install.sh"], check=True)
            subprocess.run(["sh", "install.sh"], check=True)
            print("✅ Ollama installed successfully!")
            return True
        except Exception as e:
            print(f"❌ Error installing Ollama: {e}")
            print("Please install manually: https://ollama.com/download")
            return False
    else:
        print(f"❌ Unsupported platform: {system}")
        return False

def pull_model(model_name):
    """Pull a model using Ollama."""
    print(f"Pulling model: {model_name}")
    try:
        result = subprocess.run(["ollama", "pull", model_name], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Model {model_name} pulled successfully!")
            return True
        else:
            print(f"❌ Error pulling model: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def update_env_file():
    """Update .env file with Ollama configuration."""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("⚠️ .env file not found. Creating new one...")
        env_content = ""
    else:
        env_content = env_path.read_text()
    
    # Check if Ollama config already exists
    if "OLLAMA_BASE_URL" in env_content:
        print("⚠️ Ollama configuration already exists in .env")
        response = input("Update existing configuration? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Add/update Ollama configuration
    lines = env_content.split("\n")
    updated_lines = []
    ollama_added = False
    
    for line in lines:
        if line.startswith("LLM_PROVIDER="):
            updated_lines.append("LLM_PROVIDER=ollama")
            ollama_added = True
        elif line.startswith("OLLAMA_BASE_URL="):
            updated_lines.append("OLLAMA_BASE_URL=http://localhost:11434")
            ollama_added = True
        elif line.startswith("OLLAMA_MODEL="):
            updated_lines.append("OLLAMA_MODEL=llama3.1:8b")
            ollama_added = True
        else:
            updated_lines.append(line)
    
    # Add Ollama config if not present
    if not ollama_added:
        updated_lines.append("")
        updated_lines.append("# Local LLM Configuration (Ollama)")
        updated_lines.append("LLM_PROVIDER=ollama")
        updated_lines.append("OLLAMA_BASE_URL=http://localhost:11434")
        updated_lines.append("OLLAMA_MODEL=llama3.1:8b")
    
    env_path.write_text("\n".join(updated_lines))
    print("✅ Updated .env file with Ollama configuration")

def test_ollama():
    """Test Ollama connection."""
    print_header("Testing Ollama Connection")
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Ollama is running! Found {len(models)} model(s)")
            for model in models:
                print(f"   - {model.get('name', 'Unknown')}")
            return True
        else:
            print(f"❌ Ollama returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("   Make sure Ollama is running: ollama serve")
        return False

def main():
    """Main setup function."""
    print_header("Local LLM Setup (Ollama)")
    
    # Check if Ollama is installed
    if not check_ollama_installed():
        print("❌ Ollama is not installed.")
        install_ollama()
        if not check_ollama_installed():
            print("\n⚠️ Please install Ollama and run this script again.")
            return
    else:
        print("✅ Ollama is installed")
    
    # Test connection
    if not test_ollama():
        print("\n⚠️ Ollama is not running. Starting Ollama...")
        print("   Please run 'ollama serve' in another terminal")
        print("   Or install Ollama if not installed")
        return
    
    # Recommend models
    print_header("Recommended Models")
    print("1. llama3.1:8b      - Best balance (recommended)")
    print("2. mistral:7b        - Fastest")
    print("3. phi3:3.8b         - Smallest")
    print("4. llama3.1:70b      - Best quality (requires more RAM)")
    
    model_choice = input("\nEnter model name to pull (or 'skip' to skip): ").strip()
    
    if model_choice.lower() != 'skip' and model_choice:
        if pull_model(model_choice):
            print(f"✅ Model {model_choice} ready!")
        else:
            print(f"❌ Failed to pull {model_choice}")
    else:
        print("⚠️ Skipping model pull. You can pull models later with: ollama pull <model>")
    
    # Update .env
    print_header("Updating Configuration")
    update_env_file()
    
    # Final instructions
    print_header("Setup Complete!")
    print("Next steps:")
    print("1. Make sure Ollama is running: ollama serve")
    print("2. Pull a model if you haven't: ollama pull llama3.1:8b")
    print("3. Restart your trading system")
    print("4. Monitor LLM calls in the logs")
    print("\nTo test:")
    print("  python -c \"from agents.llm_provider_manager import LLMProviderManager; m = LLMProviderManager(); print(m.call_llm('You are a trader.', 'Analyze Bank Nifty'))\"")

if __name__ == "__main__":
    main()


