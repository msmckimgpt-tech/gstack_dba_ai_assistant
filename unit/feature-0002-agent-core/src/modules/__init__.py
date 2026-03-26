"""Unified namespace for agent modules.

All modules were originally a single file. This __init__.py:
1. Loads all submodules in dependency order
2. Injects cross-module names into each module's globals
3. Re-exports everything for backward-compatible `from modules.X import *`
"""
from . import config
from . import utils
from . import db
from . import memory
from . import knowledge
from . import insight
from . import render
from . import schema
from . import domain
from . import llm
from . import mcp_client
from . import file_ops
from . import planner
from . import sql_ops

# Collect all exported names from every module
_all_modules = [
    config, utils, db, memory, knowledge, insight,
    render, schema, domain, llm, mcp_client, file_ops,
    planner, sql_ops,
]

_all_names: dict[str, object] = {}
for _mod in _all_modules:
    for _name in getattr(_mod, "__all__", []):
        if _name not in _all_names:
            _obj = getattr(_mod, _name, None)
            if _obj is not None:
                _all_names[_name] = _obj

# Inject cross-module names into each module's globals
# so that functions can reference names from any module
for _mod in _all_modules:
    for _name, _obj in _all_names.items():
        if _name not in _mod.__dict__:
            _mod.__dict__[_name] = _obj

# Build __all__ from all module exports (includes _ prefixed names)
__all__ = list(_all_names.keys())

# Re-export all names into package namespace for agent_cli.py compatibility
from .config import *
from .utils import *
from .db import *
from .memory import *
from .knowledge import *
from .insight import *
from .render import *
from .schema import *
from .domain import *
from .llm import *
from .mcp_client import *
from .file_ops import *
from .planner import *
from .sql_ops import *
