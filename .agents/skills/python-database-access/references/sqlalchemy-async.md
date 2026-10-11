# SQLAlchemy Async — Deep Reference

> Use this reference when you've chosen **SQLAlchemy ORM** over the Raw+DC pattern.
> See [raw-dc-pattern.md](raw-dc-pattern.md) if you want raw asyncpg + dataclasses instead.
>
> Choose SQLAlchemy ORM when you need: relationship navigation, change tracking,
> Alembic `--autogenerate`, or an existing SQLAlchemy codebase.

## Engine Creation

### PostgreSQL + asyncpg (default)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://<user>:<password>@<host>:5432/<db>",
    pool_size=10,           # persistent connections
    max_overflow=20,        # burst connections beyond pool_size
    pool_timeout=30,        # seconds to wait for connection from pool
    pool_recycle=1800,      # recycle connections older than 30 min
    pool_pre_ping=True,     # validate connection before use (handles stale connections)
    echo=False,             # set True only in development
)
```

### PostgreSQL + psycopg3

```python
# pip install psycopg[binary]
engine = create_async_engine(
    "postgresql+psycopg://<user>:<password>@<host>:5432/<db>",
    pool_size=10,
    pool_pre_ping=True,
)
```

Use psycopg3 over asyncpg when you need:
- `COPY FROM` / `COPY TO` for bulk loading
- `LISTEN` / `NOTIFY` pub-sub
- Pipeline mode (batch multiple round-trips)

### SQLite + aiosqlite (tests / lightweight)

```python
# pip install aiosqlite
engine = create_async_engine(
    "sqlite+aiosqlite:///./test.db",
    # SQLite has no pool — connect_args disables WAL check_same_thread warning
    connect_args={"check_same_thread": False},
    echo=False,
)
```

For in-memory SQLite in tests:
```python
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
```

---

## Session Factory

```python
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # REQUIRED: prevents DetachedInstanceError in async
    autoflush=False,          # explicit flush control
)
```

**Why `expire_on_commit=False`:**
After `session.commit()`, SQLAlchemy normally expires all loaded attributes.
In async context, accessing an expired attribute would trigger an implicit lazy load,
which raises `MissingGreenlet`. Setting `expire_on_commit=False` keeps attributes
accessible after commit without re-querying.

---

## Session Lifecycle Patterns

### FastAPI dependency (recommended)

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
        # Session is automatically closed after yield completes
        # Rollback is NOT automatic — commit explicitly in route handlers
```

### Manual context manager

```python
async with AsyncSessionLocal() as session:
    result = await session.execute(select(User))
    users = result.scalars().all()
    # session closes automatically at block exit
```

### Explicit transaction

```python
async with AsyncSessionLocal() as session:
    async with session.begin():
        # All operations in this block are in one transaction
        session.add(user)
        # Commits at block exit, rolls back on exception
```

---

## Querying

### Select with filter

```python
from sqlalchemy import select

stmt = select(User).where(User.email == "foo@example.com")
result = await session.execute(stmt)
user = result.scalar_one_or_none()  # None if missing, raises if >1
```

### Multiple rows

```python
result = await session.execute(select(User).order_by(User.created_at.desc()))
users: list[User] = list(result.scalars())
# or: result.scalars().all()
```

### Get by primary key

```python
user = await session.get(User, user_id)  # None if not found
```

### Pagination

```python
stmt = select(User).order_by(User.id).limit(limit).offset(offset)
```

### Count

```python
from sqlalchemy import func, select

stmt = select(func.count()).select_from(User).where(User.is_active == True)
count: int = (await session.execute(stmt)).scalar_one()
```

### Exists check

```python
from sqlalchemy import exists

stmt = select(exists().where(User.email == email))
exists_bool: bool = (await session.execute(stmt)).scalar_one()
```

### Update (ORM style)

```python
user = await session.get(User, user_id)
user.email = "new@example.com"
await session.flush()
```

### Bulk update (Core style — no ORM overhead)

```python
from sqlalchemy import update

stmt = (
    update(User)
    .where(User.is_active == False, User.created_at < cutoff)
    .values(deleted_at=func.now())
    .returning(User.id)
)
result = await session.execute(stmt)
deleted_ids = result.scalars().all()
```

### Insert

```python
from sqlalchemy.dialects.postgresql import insert

stmt = (
    insert(User)
    .values(email="a@example.com", name="Alice")
    .on_conflict_do_nothing(index_elements=["email"])
    .returning(User)
)
user = (await session.execute(stmt)).scalar_one_or_none()
```

---

## Relationship Loading (Async)

**NEVER** rely on the default `lazy="select"` in async code. It raises `MissingGreenlet`.

Set relationships to `lazy="noload"` in models and load explicitly per query.

### selectinload — separate query, good for collections

```python
from sqlalchemy.orm import selectinload

stmt = select(User).options(selectinload(User.posts))
result = await session.execute(stmt)
users = result.scalars().all()
# users[0].posts is fully loaded
```

### joinedload — single JOIN, good for scalar (many-to-one) relationships

```python
from sqlalchemy.orm import joinedload

stmt = select(Post).options(joinedload(Post.author))
result = await session.execute(stmt)
posts = result.unique().scalars().all()  # .unique() required with joinedload
```

### Nested loading

```python
stmt = (
    select(User)
    .options(
        selectinload(User.posts).selectinload(Post.tags)
    )
)
```

---

## Raw asyncpg (without SQLAlchemy ORM)

When you bypass the ORM entirely for performance-critical paths:

```python
import asyncpg

pool = await asyncpg.create_pool(
    dsn="postgresql://<user>:<password>@<host>/<db>",
    min_size=5,
    max_size=20,
)

async with pool.acquire() as conn:
    rows = await conn.fetch("SELECT id, email FROM users WHERE active = $1", True)
    for row in rows:
        print(row["id"], row["email"])
```

### COPY bulk insert (asyncpg)

```python
async with pool.acquire() as conn:
    await conn.copy_records_to_table(
        "users",
        records=[(1, "a@example.com"), (2, "b@example.com")],
        columns=["id", "email"],
    )
```

---

## Connection Pool Sizing

Rule of thumb for PostgreSQL:
- `pool_size` = number of async workers (typically CPU count or concurrency target)
- `max_overflow` = 2x `pool_size` for burst tolerance
- Do NOT set `pool_size` > PostgreSQL `max_connections / num_app_instances`

PgBouncer (transaction mode) in front of PostgreSQL:
- Set SQLAlchemy `pool_size` to match PgBouncer pool size
- Disable `pool_pre_ping` — PgBouncer manages connection health
- Set `prepared_statement_cache_size=0` on asyncpg to avoid prepared statement conflicts in transaction mode:

```python
engine = create_async_engine(
    "postgresql+asyncpg://...",
    connect_args={"prepared_statement_cache_size": 0},
)
```

---

## Testing Patterns

### Fixture with in-memory SQLite

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.models.base import Base

@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

### Override FastAPI dependency in tests

```python
from fastapi.testclient import TestClient  # or httpx AsyncClient
from app.main import app
from api.dependencies import get_db

app.dependency_overrides[get_db] = lambda: db_session_fixture
```
