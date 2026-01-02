"""Update .env file with Groq API key."""

import os
from pathlib import Path

def update_env_file():
    """Update or create .env file with Groq API key."""
    # Get API key from environment or prompt user
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("GROQ_API_KEY not found in environment variables.")
        groq_api_key = input("Enter your Groq API key (or press Enter to skip): ").strip()
        if not groq_api_key:
            print("Skipping Groq API key configuration.")
            return
    """Update or create .env file with Groq API key."""
    env_path = Path(".env")
    
    # Read existing .env if it exists
    env_vars = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update with Groq settings
    env_vars["GROQ_API_KEY"] = groq_api_key
    env_vars["LLM_PROVIDER"] = "groq"
    env_vars["LLM_MODEL"] = "llama-3.3-70b-versatile"  # Updated model name
    
    # Write back to .env
    with open(env_path, "w") as f:
        f.write("# GenAI Trading System Configuration\n")
        f.write("# LLM Provider: Groq\n\n")
        
        # Write all variables
        for key, value in sorted(env_vars.items()):
            f.write(f"{key}={value}\n")
    
    print(f"✅ Updated .env file with Groq API key")
    print(f"   LLM_PROVIDER=groq")
    print(f"   LLM_MODEL=llama-3.1-70b-versatile")
    print(f"   GROQ_API_KEY=*** (configured)")

if __name__ == "__main__":
    update_env_file()

