---
name: python-patterns
description: >
  This skill should be used when the user asks to "write Python code", "review or refactor
  Python code", "set up a new Python project", "configure ruff, pyright, or uv",
  "resolve lint or type-check failures", or needs guidance on Pythonic idioms, type hints,
  project structure, or testing conventions. Covers personal preferences for Python style,
  tooling, and architecture patterns.
version: 1.1.0
---

# Python Development Patterns

Non-obvious Python patterns and personal coding preferences. Assumes familiarity with Python basics.

## Preferred Toolchain

| Tool                    | Role                                                       |
| ----------------------- | ---------------------------------------------------------- |
| `uv`                    | Package and virtualenv management (replaces pip/poetry)    |
| `ruff`                  | Linting **and** formatting (replaces black, flake8, isort) |
| `pyright`               | Static type checking (replaces mypy)                       |
| `pytest` + `pytest-cov` | Testing and coverage                                       |
| `pre-commit`            | Local enforcement of all checks                            |
| `hatchling`             | Build backend                                              |

## Core Principles

1. **EAFP** — Easier to Ask Forgiveness than Permission. Prefer `try/except` over condition checks.
2. **Explicit over implicit** — no magic, clear configuration, no hidden side effects.
3. **Readability counts** — obvious code over clever code. Clear names, type hints everywhere.

## Code Style

- **Single quotes** for all strings.
- **100-character** max line length.
- No commented-out code (enforced by ruff ERA rule).
- Use `%s` placeholders in log calls, not f-strings (enforced by ruff G rule).

## Type Hints

```python
import typing as t

T = t.TypeVar('T')

# Use built-in types (not typing.List, typing.Dict)
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Union types — X | None, not Optional[X]
def first(items: list[T]) -> T | None:
    return items[0] if items else None

# Protocol-based duck typing
class Renderable(t.Protocol):
    def render(self) -> str: ...

# Guard type-only imports behind TYPE_CHECKING
if t.TYPE_CHECKING:  # pragma: no cover
    from .models import MyModel
```

- Annotate **all** function parameters and return types.
- Avoid `# type: ignore` unless strictly necessary and justified.

## Error Handling

```python
# Specific exceptions, chain with `from`
try:
    with open(path) as f:
        return Config.from_json(f.read())
except FileNotFoundError as e:
    raise ConfigError(f'Config not found: {path}') from e
except json.JSONDecodeError as e:
    raise ConfigError(f'Invalid JSON: {path}') from e

# Custom exception hierarchy
class AppError(Exception): ...
class ValidationError(AppError): ...
class NotFoundError(AppError): ...
```

**Never** use bare `except:`. Always catch specific exceptions.

## Data Classes

```python
import dataclasses
import datetime

@dataclasses.dataclass
class User:
    id: str
    name: str
    email: str
    created_at: datetime.datetime = dataclasses.field(default_factory=datetime.datetime.now)
    is_active: bool = True

    def __post_init__(self):
        if '@' not in self.email:
            raise ValueError(f'Invalid email: {self.email}')
```

Use `__slots__` or `@dataclass(slots=True)` for memory efficiency with many instances.

## Context Managers

```python
# Custom context manager
@contextmanager
def timer(name: str):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f'{name} took {elapsed:.4f}s')
```

## Generators for Large Data

```python
# Yield lines one at a time — don't load full file into memory
def read_lines(path: str) -> Iterator[str]:
    with open(path) as f:
        for line in f:
            yield line.strip()

# Generator expression over list comprehension for large data
total = sum(x * x for x in range(1_000_000))  # Good
total = sum([x * x for x in range(1_000_000)])  # Bad — intermediate list
```

## Anti-Patterns

```python
# Mutable default arguments
def bad(items=[]):    ...  # Bug: shared across calls
def good(items=None): items = items or []; ...

# Type checking
if type(obj) == list:     ...  # Bad
if isinstance(obj, list): ...  # Good

# None comparison
if value == None:  ...  # Bad
if value is None:  ...  # Good

# Wildcard imports
from os.path import *         # Bad — pollutes namespace
import os                     # Good — use os.path.join, os.path.exists

# String concatenation in loops — O(n²)
result = ''.join(str(item) for item in items)  # Good

# Don't use f-strings in log calls
logger.debug('Processing %s items', count)      # Good
logger.debug(f'Processing {count} items')        # Bad
```

## Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use %s placeholders — never f-strings in log calls
logger.debug('Processing %s items', count)
logger.error('Validator %s failed: %s', name, error)
```

One module-level `logger = logging.getLogger(__name__)` per file.

## Imports

Import order is enforced by ruff (isort rules). The order is:

1. Standard library
2. Third-party packages
3. First-party / local packages

**Style convention:**

- Stdlib and third-party: `import <module>`, access via fully qualified name
- First-party: `from ... import ...`

```python
import logging
import os

import boto3

from mypackage.models import User
from mypackage.engine import Engine
```

Approved abbreviations: `import typing as t`, `import collections.abc as c`.

## Docstrings

- Module-level docstring on every module.
- Class docstring on every class.
- Docstring on every public method; include `Args:` / `Returns:` for non-trivial methods.

## Quick Reference

| Pattern | Use |
|---------|-----|
| EAFP | `try/except` over `if/else` |
| Context managers | `with` for resource management |
| List comprehensions | Simple transformations only |
| Generators | Large datasets, lazy evaluation |
| Type hints | All function signatures |
| Dataclasses | Data containers |
| `pathlib.Path` | Path operations |
| `enumerate` | Index-element pairs |
| f-strings | String formatting (but `%s` in log calls) |
| Single quotes | All strings |

## References

For detailed patterns (concurrency, decorators, package organization, tooling config), see `references/advanced-patterns.md`.
