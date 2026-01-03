"""Update .env file with News API key."""

import os
from pathlib import Path

def update_env_file():
    """Add News API key to .env file."""
    env_file = Path(".env")
    key = "e62a52a9a7694cf3815922daa89d2810"
    
    if not env_file.exists():
        print("Creating .env file...")
        content = f"NEWS_API_KEY={key}\n"
    else:
        content = env_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Check if NEWS_API_KEY already exists
        has_key = any('NEWS_API_KEY' in line for line in lines)
        
        if has_key:
            # Update existing key
            lines = [line if not line.startswith('NEWS_API_KEY') else f'NEWS_API_KEY={key}' 
                    for line in lines]
            content = '\n'.join(lines)
        else:
            # Add new key
            content += f'\nNEWS_API_KEY={key}\n'
    
    env_file.write_text(content, encoding='utf-8')
    print("News API key added/updated in .env")

if __name__ == "__main__":
    update_env_file()

