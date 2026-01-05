# top-level shim package for engine_module
import os

# Prepend the src/engine_module path so `import engine_module.*` works from repo root
_src_path = os.path.join(os.path.dirname(__file__), "src", "engine_module")
if os.path.isdir(_src_path) and _src_path not in __path__:
    __path__.insert(0, _src_path)
