# Python Advanced Patterns

## Decorators

### Function Decorators

```python
import collections.abc as c
import functools
import time

def timer(func: c.Callable) -> c.Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f'{func.__name__} took {elapsed:.4f}s')
        return result
    return wrapper
```

### Parameterized Decorators

```python
def repeat(times: int):
    def decorator(func: c.Callable) -> c.Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return [func(*args, **kwargs) for _ in range(times)]
        return wrapper
    return decorator
```

### Class-Based Decorators

```python
class CountCalls:
    def __init__(self, func: c.Callable):
        functools.update_wrapper(self, func)
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        return self.func(*args, **kwargs)
```

## Concurrency Patterns

### Threading for I/O-Bound Tasks

```python
import concurrent.futures

def fetch_all_urls(urls: list[str]) -> dict[str, str]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in urls}
        results = {}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception as e:
                results[url] = f'Error: {e}'
    return results
```

### Multiprocessing for CPU-Bound Tasks

```python
import concurrent.futures

def process_all(datasets: list[list[int]]) -> list[int]:
    with concurrent.futures.ProcessPoolExecutor() as executor:
        return list(executor.map(process_data, datasets))
```

### Async/Await for Concurrent I/O

```python
import asyncio
import aiohttp

async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()
    except aiohttp.ClientError as e:
        return f'Error: {e}'

async def fetch_all(urls: list[str]) -> dict[str, str]:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return dict(zip(urls, results))
```

## Package Organization

### Standard Project Layout

```
myproject/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       ├── models/
│       └── utils/
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── pyproject.toml
└── README.md
```

### Import Order

```python
# stdlib — import the module, use fully qualified access
import collections.abc as c
import logging
import os
import typing as t

# third-party — same style
import boto3
import requests

# first-party — import names directly
from mypackage.models import User
from mypackage.engine import Engine
```

Import order and sorting enforced by ruff (isort rules). Blank line between `import` and `from...import` within each group (`lines-between-types = 1`).

### __init__.py Exports

```python
__version__ = '1.0.0'
from mypackage.models import User, Post
__all__ = ['User', 'Post']
```

## Context Manager Classes

```python
class DatabaseTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.begin_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        return False
```

## Tooling Configuration

### pyproject.toml

```toml
[project]
name = 'mypackage'
version = '1.0.0'
requires-python = '>=3.14'

[build-system]
requires = ['hatchling']
build-backend = 'hatchling.build'

[dependency-groups]
dev = [
    'pytest',
    'pytest-cov',
    'pre-commit',
    'ruff',
    'pyright',
]

[tool.ruff]
line-length = 100
target-version = 'py314'

[tool.ruff.lint]
extend-select = [
    'A',      # flake8-builtins
    'C4',     # flake8-comprehensions
    'ERA',    # eradicate (no commented-out code)
    'G',      # flake8-logging-format
    'I',      # isort
    'ISC',    # flake8-implicit-string-concat
    'PL',     # Pylint
    'RET',    # flake8-return
    'RUF100', # unused noqa
    'SLF',    # flake8-self (private member access)
]
ignore = [
    'ISC001',  # conflicts with ruff formatter
    'PLR0912', # too many branches
    'PLR0913', # too many arguments
    'PLR0915', # too many statements
    'PLR2004', # magic value in comparison
    'PLR1711', # useless return
]

[tool.ruff.lint.isort]
lines-between-types = 1

[tool.ruff.lint.per-file-ignores]
'tests/*' = ['SLF001']

[tool.ruff.format]
quote-style = 'single'

[tool.pyright]
deprecateTypingAliases = true
reportUnnecessaryTypeIgnoreComment = true
venv = '.venv'
venvPath = '.'

[tool.pytest.ini_options]
testpaths = ['tests']
addopts = '--cov=src --cov-report=term-missing'

[tool.coverage.run]
branch = true
source = ['src']

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### Pre-commit Configuration

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff-format
      - id: ruff
        args: [--fix]
  - repo: local
    hooks:
      - id: pyright
        name: pyright
        entry: uv run pyright
        language: system
        types: [python]
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
        stages: [pre-push]
```

### Essential Commands

```bash
uv run ruff format .         # Format
uv run ruff check --fix .    # Lint + auto-fix
uv run pyright               # Type check
uv run pytest --cov=src      # Test with coverage
```

## Named Tuples

```python
import typing as t

class Point(t.NamedTuple):
    x: float
    y: float

    def distance(self, other: 'Point') -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
```

## Logging Patterns

```python
import logging

logger = logging.getLogger(__name__)

# Use %s placeholders — never f-strings in log calls
logger.debug('Processing %s items', count)
logger.info('User %s logged in from %s', user_id, ip)
logger.error('Validator %s failed: %s', name, error)

# Suppress noisy third-party loggers in app entry points
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
```

## Testing Conventions

- Tests live in `tests/`, mirroring `src/` structure.
- Use `pytest`; `unittest.TestCase` acceptable for complex setups.
- Use `unittest.mock.patch` for mocking external dependencies.
- Branch coverage must be ≥ 80%.
- Annotate uncoverable lines with `# pragma: no cover`.

## Dataclasses, Enums, ABCs

```python
import abc
import dataclasses
import enum

@dataclasses.dataclass
class Result:
    """Describe the data container."""
    level: Level
    message: str
    optional_field: str | None = None

class Level(enum.Enum):
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

class BaseValidator(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def validate(self, data: 'MyModel') -> list[Result]: ...
```

- Prefer `@dataclasses.dataclass` for data containers.
- Use `@dataclass(slots=True)` for memory efficiency with many instances.
- Use `enum.Enum` (not `IntEnum` unless arithmetic is needed).
- ABCs use `abc.ABC` + `@abc.abstractmethod`.

## Docstring Conventions

- Module-level docstring on every module: `"""Brief description of module purpose."""`
- Class docstring on every class.
- Docstring on every public method; include `Args:` / `Returns:` for non-trivial methods.
- Entry point pattern:

```python
def main() -> None:
    """Application entry point."""
    sys.exit(run())

if __name__ == '__main__':
    main()
```
