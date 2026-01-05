"""Shim to preserve top-level `update_env_groq` while implementation lives in `genai_module`."""

from genai_module.tools.update_env import update_env_file as main

if __name__ == "__main__":
    main()

