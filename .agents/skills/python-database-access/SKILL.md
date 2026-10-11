---
name: python-database-access
description: >
  This skill should be used when the user asks to "write async database access code",
  "set up SQLAlchemy async sessions", "use asyncpg with FastAPI", "implement Raw+DC",
  "create repository and Unit of Work patterns", "wire database dependencies into FastAPI",
  "write Alembic migrations", "map database rows to dataclasses", or
  "fix async database session errors". Covers SQLAlchemy async ORM sessions, Raw+DC
  query functions, asyncpg/psycopg3 drivers, repository pattern, Unit of Work,
  Alembic migrations, and mapper functions.
---

**Tags:** python, fastapi, sqlalchemy, asyncpg, postgresql, sqlite, repository, alembic, async, raw-dc, dataclass

# Python Database Access

Async database access patterns for FastAPI. Two first-class approaches:

| Approach | When to use |
|----------|-------------|
| **SQLAlchemy ORM** | Complex domain with relationships, change tracking, Alembic autogenerate |
| **Raw+DC** | Simple/read-heavy DALs, maximum AI tooling support, minimal dependencies |

> **Complements existing skills**
> - `postgres-patterns` — PostgreSQL SQL, schema design, indexing, RLS
> - `python-patterns` — Pythonic idioms, type hints, PEP 8

---

## Pattern Choice

### Raw+DC (Raw queries + Dataclasses)

Proposed by Michael Kennedy as the "ORM pattern of 2026": write native SQL with parameterized queries, map results to `@dataclass(slots=True)` at the boundary. No ORM framework.

**Choose Raw+DC when:**
- The DAL is primarily reads or simple CRUD
- Minimum dependencies matter (only the async driver)
- AI coding assistant support matters (asyncpg has 50x+ more training data than any ORM)
- Performance on large result sets matters
- Full visibility into the SQL being executed matters

**Choose SQLAlchemy ORM when:**
- Complex object graphs with relationships that need navigation in Python
- Alembic `--autogenerate` is required for migrations
- Change tracking is needed (modify attributes, flush, done)
- The team is already fluent with SQLAlchemy

Both patterns compose with the repository concept and Alembic for migrations.

---

## Quick Start

### Raw+DC (recommended starting point)

```python
# db/pool.py
import asyncpg

pool: asyncpg.Pool | None = None

async def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool has not been initialized")
    return pool

# main.py lifespan
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncpg
import db.pool as db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_pool.pool = await asyncpg.create_pool(dsn="postgresql://<user>:<password>@<host>/<db>")
    yield
    await db_pool.pool.close()

app = FastAPI(lifespan=lifespan)
```

```python
# db/models.py — plain dataclasses, no ORM
from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class User:
    id: int
    email: str
    created_at: datetime

def user_from_row(row: asyncpg.Record) -> User:
    return User(id=row["id"], email=row["email"], created_at=row["created_at"])
```

```python
# db/queries/users.py — query functions, not classes
import asyncpg
from db.models import User, user_from_row

async def get_user_by_id(pool: asyncpg.Pool, user_id: int) -> User | None:
    row = await pool.fetchrow(
        "SELECT id, email, created_at FROM users WHERE id = $1", user_id
    )
    return user_from_row(row) if row else None
```

```python
# FastAPI route
@router.get("/{user_id}")
async def get_user(user_id: int, pool: asyncpg.Pool = Depends(get_pool)) -> UserSchema:
    user = await get_user_by_id(pool, user_id)
    if user is None:
        raise HTTPException(404)
    return user
```

See [references/raw-dc-pattern.md](references/raw-dc-pattern.md) for the full pattern.

### SQLAlchemy ORM

```python
# db/engine.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://<user>:<password>@<host>/<db>",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

---

## Instructions

### 1. Engine / Pool Setup

**Raw+DC — asyncpg pool:**
```python
pool = await asyncpg.create_pool(
    dsn="postgresql://<user>:<password>@<host>/<db>",
    min_size=5,
    max_size=20,
    command_timeout=30,
)
```

**SQLAlchemy async engine** — see [references/sqlalchemy-async.md](references/sqlalchemy-async.md).

Driver URL cheatsheet:
```
postgresql+asyncpg://...     # asyncpg (Raw+DC or SQLAlchemy)
postgresql+psycopg://...     # psycopg3 (COPY, LISTEN/NOTIFY, pipeline)
sqlite+aiosqlite:///./db     # SQLite (tests / local)
```

### 2. Data Representation

**Raw+DC — `@dataclass(slots=True)`:**

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class User:
    id: int
    email: str
    is_active: bool
    created_at: datetime

@dataclass(slots=True)
class Address:
    street: str
    city: str
    country: str

@dataclass(slots=True)
class UserWithAddress:
    id: int
    email: str
    address: Address
```

`slots=True` reduces memory usage and speeds up attribute access — always use it for result dataclasses.

**ORM — `Mapped` + `mapped_column`:**

```python
# db/models/base.py
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

```python
# db/models/user.py
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import text
from .base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    posts: Mapped[list["Post"]] = relationship(back_populates="author", lazy="noload")
```

**ORM rules:** always `Mapped[T]` + `mapped_column()` (SQLAlchemy 2.x), `lazy="noload"` on all relationships.

### 3. Mapper Functions (Raw+DC)

Map rows to dataclasses at the data access boundary. Keep mappers close to queries.

```python
# db/queries/users.py
import asyncpg
from db.models import User, Address, UserWithAddress

def _user(row: asyncpg.Record) -> User:
    return User(id=row["id"], email=row["email"],
                is_active=row["is_active"], created_at=row["created_at"])

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

See [references/raw-dc-pattern.md](references/raw-dc-pattern.md) for nested mappers, list results, and JOIN patterns.

### 4. Query Functions (Raw+DC)

Use plain `async def` functions, not classes. Group by domain entity.

```python
async def get_user(pool: asyncpg.Pool, user_id: int) -> User | None:
    row = await pool.fetchrow(
        "SELECT id, email, is_active, created_at FROM users WHERE id = $1",
        user_id,
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

async def create_user(
    pool: asyncpg.Pool, email: str
) -> User:
    row = await pool.fetchrow(
        "INSERT INTO users (email) VALUES ($1)"
        " RETURNING id, email, is_active, created_at",
        email,
    )
    return _user(row)
```

**Always use `$N` placeholders — never f-strings in SQL.**

### 5. Repository Pattern (ORM)

See [references/repository-uow.md](references/repository-uow.md) for the full `BaseRepository[T]` implementation.

```python
class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
```

**Rule:** `flush()` not `commit()` inside repos — commit at the service/route boundary.

### 6. Unit of Work (ORM)

See [references/repository-uow.md](references/repository-uow.md) for full implementation.

```python
async with UnitOfWork(AsyncSessionLocal) as uow:
    user = await uow.users.get_by_email("a@example.com")
    user.email = "b@example.com"
    await uow.commit()
```

### 7. Transactions (Raw+DC)

```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute(
            "UPDATE accounts SET balance = balance - $1 WHERE id = $2",
            amount, from_id,
        )
        await conn.execute(
            "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
            amount, to_id,
        )
        # rolls back automatically on exception
```

See [references/raw-dc-pattern.md](references/raw-dc-pattern.md) for nested transactions and savepoints.

### 8. FastAPI Dependency Injection

**Raw+DC — inject pool:**

```python
# api/dependencies.py
from db.pool import get_pool
import asyncpg

async def pool_dep() -> asyncpg.Pool:
    return await get_pool()

# Route
@router.get("/{id}")
async def get_user(id: int, pool: asyncpg.Pool = Depends(pool_dep)) -> UserSchema:
    user = await queries.get_user(pool, id)
    ...
```

**ORM — inject session or UoW:**

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    async with UnitOfWork(AsyncSessionLocal) as uow:
        yield uow
```

### 9. Relationship Loading (ORM only)

Never rely on implicit lazy loading — raises `MissingGreenlet`.

```python
from sqlalchemy.orm import selectinload, joinedload

# selectinload — separate query, good for collections
stmt = select(User).options(selectinload(User.posts))

# joinedload — single JOIN, good for many-to-one
stmt = select(Post).options(joinedload(Post.author))
result = (await session.execute(stmt)).unique().scalars().all()
```

In Raw+DC, join in SQL and map with a multi-field mapper function.

### 10. Alembic Migrations

Works with both patterns — Alembic operates at the SQL/schema level regardless of Python access pattern.

See [references/alembic.md](references/alembic.md) for full async `env.py` setup.

```bash
alembic revision --autogenerate -m "add users table"  # ORM: reads models
alembic revision -m "add users table"                 # Raw+DC: write manually
alembic upgrade head
alembic downgrade -1
```

> With Raw+DC, `--autogenerate` does not work unless SQLAlchemy `Table` objects are also maintained.
> Write migrations manually or use a schema diffing tool.

---

## Best Practices

### Both patterns
- Parameterized queries always — never f-strings or string concatenation in SQL
- One connection / session per request — never share across requests
- Release connections promptly via context managers

### Raw+DC
- `@dataclass(slots=True)` on all result types
- Keep mapper functions private (prefix `_`) and co-located with queries
- Group query functions by entity in `db/queries/<entity>.py`
- Explicit transaction blocks for multi-statement mutations
- Write Alembic migrations by hand (no autogenerate)

### SQLAlchemy ORM
- `expire_on_commit=False` on `async_sessionmaker`
- `lazy="noload"` on all relationships; use `selectinload`/`joinedload` explicitly
- `flush()` in repos, `commit()` at service/route boundary
- `MetaData` naming conventions for deterministic Alembic autogenerate

---

## Common Errors

| Error | Pattern | Cause | Fix |
|-------|---------|-------|-----|
| `MissingGreenlet` | ORM | Implicit lazy load in async | Add `selectinload` / set `lazy="noload"` |
| `DetachedInstanceError` | ORM | Attribute access after session close | Set `expire_on_commit=False` |
| `InterfaceError: connection already closed` | Both | Pool connection not returned | Use `async with pool.acquire()` or session ctx manager |
| Alembic empty migration | ORM | Models not imported in `env.py` | Import all model modules in `env.py` |
| `$1` placeholder error | Raw+DC | Wrong placeholder syntax | asyncpg uses `$1`, psycopg3 uses `%s` |

---

## Project Layout

### Raw+DC

```
app/
├── db/
│   ├── pool.py            # asyncpg pool, get_pool()
│   ├── models.py          # @dataclass(slots=True) result types
│   └── queries/
│       ├── users.py       # get_user, list_users, create_user, ...
│       └── posts.py
├── api/
│   ├── dependencies.py    # pool_dep()
│   └── routers/
├── alembic/
│   ├── env.py
│   └── versions/
└── alembic.ini
```

### SQLAlchemy ORM

```
app/
├── db/
│   ├── engine.py          # create_async_engine, async_sessionmaker
│   ├── models/
│   │   ├── base.py        # DeclarativeBase with naming convention
│   │   └── user.py
│   ├── repositories/
│   │   ├── base.py        # BaseRepository[T]
│   │   └── user.py
│   └── unit_of_work.py
├── api/
│   ├── dependencies.py    # get_db, get_uow
│   └── routers/
├── alembic/
│   ├── env.py
│   └── versions/
└── alembic.ini
```

---

## Requirements

### Raw+DC
```
asyncpg                  # PostgreSQL
psycopg[binary]          # PostgreSQL alternative (COPY, LISTEN/NOTIFY)
aiosqlite                # SQLite
alembic>=1.13
```

### SQLAlchemy ORM
```
sqlalchemy[asyncio]>=2.0
asyncpg
psycopg[binary]
aiosqlite
alembic>=1.13
```
