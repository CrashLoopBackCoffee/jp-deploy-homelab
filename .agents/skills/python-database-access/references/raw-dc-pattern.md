# Raw+DC Pattern — Deep Reference

The **Raw+DC pattern** (Raw queries + Dataclasses) combines native SQL with typed Python
dataclasses. No ORM framework required — just an async driver and standard library dataclasses.

Popularized by Michael Kennedy (Talk Python) as the practical ORM pattern of 2026:
write SQL you understand, return typed objects you can reason about.

---

## Why Raw+DC

| Factor | Raw+DC | SQLAlchemy ORM |
|--------|--------|---------------|
| Dependencies | driver only | sqlalchemy + driver |
| AI coding assistant quality | High (asyncpg: 74M+ downloads/mo) | Lower (ORM-specific APIs) |
| Query visibility | Explicit SQL | Generated SQL (hidden by default) |
| Performance on large sets | Fastest (near-native) | ORM overhead |
| Change tracking | Manual | Automatic (session tracks objects) |
| Relationships | Explicit JOIN + mapper | `selectinload` / `joinedload` |
| Migration autogenerate | Not supported | Full support |
| Learning curve | SQL + dataclasses | SQLAlchemy API |

---

## Connection Pool Setup

### PostgreSQL — asyncpg (default)

```python
# db/pool.py
import asyncpg
from typing import Any

_pool: asyncpg.Pool | None = None


async def create_pool(dsn: str, **kwargs: Any) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn,
        min_size=kwargs.get("min_size", 5),
        max_size=kwargs.get("max_size", 20),
        command_timeout=kwargs.get("command_timeout", 30),
        max_inactive_connection_lifetime=300,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialized. Call create_pool() in lifespan.")
    return _pool
```

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import db.pool as db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_pool.create_pool(dsn="postgresql://<user>:<password>@<host>/<db>")
    yield
    await db_pool.close_pool()

app = FastAPI(lifespan=lifespan)
```

### PostgreSQL — psycopg3

Use psycopg3 when you need COPY, LISTEN/NOTIFY, or pipeline mode.
Note: psycopg3 uses `%s` placeholders, not `$1`.

```python
import psycopg_pool
from psycopg_pool import AsyncConnectionPool

pool = AsyncConnectionPool(
    conninfo="postgresql://<user>:<password>@<host>/<db>",
    min_size=5,
    max_size=20,
    open=False,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await pool.close()
```

```python
# Query with psycopg3
async with pool.connection() as conn:
    row = await conn.execute(
        "SELECT id, email FROM users WHERE id = %s", (user_id,)
    )
    record = await row.fetchone()
```

### SQLite — aiosqlite (tests / lightweight)

```python
import aiosqlite
from collections.abc import AsyncGenerator

async def get_sqlite_conn() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect("./local.db") as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
```

---

## Dataclass Design

### Core rules

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

# Always slots=True — saves memory, faster attribute access
@dataclass(slots=True)
class User:
    id: int
    email: str
    is_active: bool
    created_at: datetime

# Nested dataclasses for embedded structures
@dataclass(slots=True)
class Address:
    street: str
    city: str
    country: str
    postal_code: str

@dataclass(slots=True)
class OrderLine:
    product_id: int
    quantity: int
    unit_price_cents: int

@dataclass(slots=True)
class Order:
    id: int
    order_number: str
    customer_email: str
    status: str
    total_cents: int
    created_at: datetime
    shipping_address: Address
    line_items: list[OrderLine]
```

### Optional fields

```python
from dataclasses import dataclass, field

@dataclass(slots=True)
class UserProfile:
    id: int
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
```

### Separation: DB model vs API schema

Keep result dataclasses separate from Pydantic API schemas.
The mapper boundary is the conversion point.

```python
# db/models.py  — internal, matches DB shape
@dataclass(slots=True)
class UserRow:
    id: int
    email: str
    password_hash: str    # never expose this
    created_at: datetime

# schemas/user.py — public, Pydantic
class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    # password_hash deliberately omitted
```

---

## Mapper Functions

### Single row

```python
import asyncpg

def _user(row: asyncpg.Record) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )
```

### Nested from flat JOIN result

```python
# SQL: SELECT u.id, u.email, a.street, a.city, a.country FROM users u JOIN addresses a ...
def _user_with_address(row: asyncpg.Record) -> UserWithAddress:
    return UserWithAddress(
        id=row["id"],
        email=row["email"],
        address=Address(
            street=row["street"],
            city=row["city"],
            country=row["country"],
        ),
    )
```

### Nested from JSON column (PostgreSQL)

```python
import json

def _order(row: asyncpg.Record) -> Order:
    raw_lines = json.loads(row["line_items_json"])
    return Order(
        id=row["id"],
        order_number=row["order_number"],
        customer_email=row["customer_email"],
        status=row["status"],
        total_cents=row["total_cents"],
        created_at=row["created_at"],
        shipping_address=Address(**json.loads(row["shipping_address_json"])),
        line_items=[OrderLine(**li) for li in raw_lines],
    )
```

### List result

```python
def _users(rows: list[asyncpg.Record]) -> list[User]:
    return [_user(r) for r in rows]
```

---

## Query Functions

### Pattern: one file per domain entity

```python
# db/queries/users.py
from __future__ import annotations
import asyncpg
from db.models import User

# --- private mappers ---

def _user(row: asyncpg.Record) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )

# --- public query functions ---

async def get_user(pool: asyncpg.Pool, user_id: int) -> User | None:
    row = await pool.fetchrow(
        "SELECT id, email, is_active, created_at"
        " FROM users WHERE id = $1",
        user_id,
    )
    return _user(row) if row else None


async def get_user_by_email(pool: asyncpg.Pool, email: str) -> User | None:
    row = await pool.fetchrow(
        "SELECT id, email, is_active, created_at"
        " FROM users WHERE email = $1",
        email,
    )
    return _user(row) if row else None


async def list_users(
    pool: asyncpg.Pool, *, limit: int = 100, offset: int = 0
) -> list[User]:
    rows = await pool.fetch(
        "SELECT id, email, is_active, created_at FROM users"
        " ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit, offset,
    )
    return [_user(r) for r in rows]


async def count_users(pool: asyncpg.Pool) -> int:
    return await pool.fetchval("SELECT COUNT(*) FROM users")


async def create_user(pool: asyncpg.Pool, email: str) -> User:
    row = await pool.fetchrow(
        "INSERT INTO users (email) VALUES ($1)"
        " RETURNING id, email, is_active, created_at",
        email,
    )
    return _user(row)


async def update_user_email(
    pool: asyncpg.Pool, user_id: int, email: str
) -> User | None:
    row = await pool.fetchrow(
        "UPDATE users SET email = $1"
        " WHERE id = $2"
        " RETURNING id, email, is_active, created_at",
        email, user_id,
    )
    return _user(row) if row else None


async def deactivate_user(pool: asyncpg.Pool, user_id: int) -> bool:
    result = await pool.execute(
        "UPDATE users SET is_active = FALSE WHERE id = $1",
        user_id,
    )
    # asyncpg returns "UPDATE N" string
    return result == "UPDATE 1"
```

---

## asyncpg API Reference

| Method | Returns | Use for |
|--------|---------|---------|
| `pool.fetchrow(sql, *args)` | `Record \| None` | Single row |
| `pool.fetch(sql, *args)` | `list[Record]` | Multiple rows |
| `pool.fetchval(sql, *args)` | scalar | COUNT, single value |
| `pool.execute(sql, *args)` | `str` ("UPDATE N") | INSERT/UPDATE/DELETE without return |
| `pool.executemany(sql, args_list)` | None | Bulk insert/update |
| `conn.copy_records_to_table(...)` | None | Bulk COPY (fastest inserts) |

### Accessing Record fields

```python
row = await pool.fetchrow("SELECT id, email FROM users WHERE id = $1", 1)
# By name (preferred)
user_id = row["id"]
email = row["email"]
# By index
user_id = row[0]
# As dict
d = dict(row)
```

---

## Transactions

### Simple transaction

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO audit_log (user_id, action) VALUES ($1, $2)",
            user_id, "email_changed",
        )
        await conn.execute(
            "UPDATE users SET email = $1 WHERE id = $2",
            new_email, user_id,
        )
        # Auto-commits at block exit, rolls back on exception
```

### Savepoints (nested transactions)

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        # Outer transaction
        await conn.execute("UPDATE accounts SET balance = balance - $1 WHERE id = $2", 100, from_id)

        try:
            async with conn.transaction():
                # Savepoint — rolls back inner only on failure
                await conn.execute("UPDATE accounts SET balance = balance + $1 WHERE id = $2", 100, to_id)
        except Exception:
            # Inner rolled back, outer continues
            await conn.execute("INSERT INTO failed_transfers (from_id) VALUES ($1)", from_id)
```

### Transaction with RETURNING across statements

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        user_row = await conn.fetchrow(
            "INSERT INTO users (email) VALUES ($1) RETURNING id, email, created_at",
            email,
        )
        user = _user(user_row)

        await conn.execute(
            "INSERT INTO user_roles (user_id, role) VALUES ($1, $2)",
            user.id, "member",
        )

    return user  # committed
```

---

## FastAPI Integration

### Pool dependency

```python
# api/dependencies.py
import asyncpg
from db.pool import get_pool

def pool_dep() -> asyncpg.Pool:
    return get_pool()
```

### Route with pool injection

```python
# api/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
import asyncpg
from api.dependencies import pool_dep
from db.queries import users as user_queries
from schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    pool: asyncpg.Pool = Depends(pool_dep),
) -> UserResponse:
    user = await user_queries.get_user(pool, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    payload: UserCreate,
    pool: asyncpg.Pool = Depends(pool_dep),
) -> UserResponse:
    existing = await user_queries.get_user_by_email(pool, payload.email)
    if existing:
        raise HTTPException(409, "Email already registered")
    user = await user_queries.create_user(pool, email=payload.email)
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)
```

### Connection-scoped dependency (for multi-statement transactions)

```python
from collections.abc import AsyncGenerator

async def conn_dep(
    pool: asyncpg.Pool = Depends(pool_dep),
) -> AsyncGenerator[asyncpg.Connection, None]:
    async with pool.acquire() as conn:
        yield conn

# Route using explicit connection for a transaction
@router.post("/transfer")
async def transfer(
    payload: TransferRequest,
    conn: asyncpg.Connection = Depends(conn_dep),
) -> None:
    async with conn.transaction():
        await conn.execute(...)
        await conn.execute(...)
```

---

## Bulk Operations

### executemany — batch insert

```python
records = [("a@example.com",), ("b@example.com",), ("c@example.com",)]
await pool.executemany(
    "INSERT INTO users (email) VALUES ($1) ON CONFLICT DO NOTHING",
    records,
)
```

### COPY — fastest bulk insert

```python
async with pool.acquire() as conn:
    await conn.copy_records_to_table(
        "users",
        records=[(1, "a@example.com", True), (2, "b@example.com", True)],
        columns=["id", "email", "is_active"],
    )
```

---

## Testing Raw+DC

### pytest-asyncio fixture with real PostgreSQL

```python
import pytest_asyncio
import asyncpg

@pytest_asyncio.fixture()
async def pool(postgresql_dsn: str):
    p = await asyncpg.create_pool(postgresql_dsn, min_size=1, max_size=5)
    yield p
    await p.close()

@pytest.mark.asyncio
async def test_create_user(pool: asyncpg.Pool) -> None:
    from db.queries.users import create_user, get_user
    user = await create_user(pool, email="test@example.com")
    assert user.id > 0
    fetched = await get_user(pool, user.id)
    assert fetched is not None
    assert fetched.email == "test@example.com"
```

### Stub pool for unit tests

```python
from unittest.mock import AsyncMock, MagicMock
import asyncpg

def make_mock_pool(fetchrow_return=None, fetch_return=None, fetchval_return=None):
    pool = MagicMock(spec=asyncpg.Pool)
    pool.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    pool.fetchval = AsyncMock(return_value=fetchval_return)
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool
```

---

## Security

- **Always parameterized queries** — `$1`, `$2`, never f-strings
- Never pass user input as column names or table names — use allowlists
- asyncpg automatically uses binary protocol — strings can't be misinterpreted as SQL

```python
# SAFE
await pool.fetchrow("SELECT * FROM users WHERE email = $1", user_input)

# DANGEROUS — never do this
await pool.fetchrow(f"SELECT * FROM users WHERE email = '{user_input}'")
```

---

## Placeholder Reference

| Driver | Placeholder | Example |
|--------|-------------|---------|
| asyncpg | `$1`, `$2`, ... | `WHERE id = $1` |
| psycopg3 | `%s` | `WHERE id = %s` |
| aiosqlite | `?` | `WHERE id = ?` |
