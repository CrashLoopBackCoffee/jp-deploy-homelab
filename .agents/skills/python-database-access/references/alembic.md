# Alembic — Deep Reference

## Initial Setup

### Install

```bash
pip install alembic
alembic init alembic
```

This creates:
```
alembic/
├── env.py
├── script.py.mako
└── versions/
alembic.ini
```

---

## env.py — Async Configuration

The default `env.py` is sync. Replace it entirely for async SQLAlchemy:

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# --- Import ALL models so autogenerate sees them ---
from db.models.base import Base  # noqa: F401
from db.models.user import User  # noqa: F401  # import each model module
from db.models.post import Post  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live database connection (generates SQL only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,        # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool for migrations — no persistent connections
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

## alembic.ini

Set the database URL. Prefer environment variable injection over hardcoding:

```ini
# alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://<user>:<password>@<host>/<db>

# Use env variable override in env.py (see below)
```

### Override URL from environment variable

Add to the top of `env.py` before `target_metadata`:

```python
import os

# Override sqlalchemy.url from environment variable if set
db_url = os.getenv("DATABASE_URL")
if db_url:
    # asyncpg prefix required for async engine
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    config.set_main_option("sqlalchemy.url", db_url)
```

---

## Common Commands

### Generate a migration

```bash
# Autogenerate from model diff (requires running DB)
alembic revision --autogenerate -m "add users table"

# Empty migration (write manually)
alembic revision -m "add custom index"
```

### Apply migrations

```bash
alembic upgrade head          # Apply all pending migrations
alembic upgrade +1            # Apply next migration only
alembic upgrade <rev_id>      # Apply to specific revision
```

### Downgrade

```bash
alembic downgrade -1          # Undo last migration
alembic downgrade base        # Undo all migrations
alembic downgrade <rev_id>    # Downgrade to specific revision
```

### Inspect state

```bash
alembic current               # Show current revision of DB
alembic history --verbose     # Show all revisions
alembic heads                 # Show head revisions
alembic show <rev_id>         # Show specific revision diff
```

### Generate SQL without running (offline mode)

```bash
alembic upgrade head --sql > migration.sql
```

---

## Migration File Anatomy

```python
# alembic/versions/20240101_abc123_add_users_table.py
"""add users table

Revision ID: abc123
Revises: prev_rev_id
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "abc123"
down_revision = "prev_rev_id"  # None for first migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

---

## Common Migration Operations

### Add column

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.Text(), nullable=True))
    # Backfill existing rows if making it non-nullable
    op.execute("UPDATE users SET name = 'Unknown' WHERE name IS NULL")
    op.alter_column("users", "name", nullable=False)
```

### Rename column (safe, multi-step)

```python
# Step 1: Add new column
def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.Text()))
    op.execute("UPDATE users SET full_name = username")
    # Remove old column in a separate later migration after code is deployed

# Step 2 (separate migration, after code deployed):
def upgrade() -> None:
    op.drop_column("users", "username")
```

### Add index

```python
def upgrade() -> None:
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
```

### Add FK constraint

```python
def upgrade() -> None:
    op.add_column("posts", sa.Column("author_id", sa.BigInteger(), nullable=False))
    op.create_foreign_key(
        "fk_posts_author_id_users",
        "posts", "users",
        ["author_id"], ["id"],
        ondelete="CASCADE",
    )
```

### Enum type (PostgreSQL)

```python
from sqlalchemy.dialects.postgresql import ENUM

user_status = ENUM("active", "suspended", "deleted", name="user_status")

def upgrade() -> None:
    user_status.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("status", user_status, nullable=False))

def downgrade() -> None:
    op.drop_column("users", "status")
    user_status.drop(op.get_bind(), checkfirst=True)
```

---

## Autogenerate Pitfalls

Alembic autogenerate **does not detect**:
- `CHECK` constraints written outside `Column()`
- Partial indexes (`CREATE INDEX ... WHERE ...`)
- Sequences (unless tied to a column)
- Custom SQL-level objects (triggers, stored procedures, views)

These must be written manually in migration files.

**Models must be imported in `env.py`** before `target_metadata` is set.
Alembic only sees models that are actually imported at inspection time.

**Use naming conventions** (set on `MetaData`) to keep autogenerate output consistent:
```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    ...
}
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

---

## Programmatic Migration (on app startup)

Run migrations automatically when the app starts — useful for containerized deployments:

```python
# db/migrate.py
import asyncio
from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    """Run Alembic migrations synchronously (called from async context via thread)."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def apply_migrations() -> None:
    """Apply pending migrations asynchronously without blocking the event loop."""
    import anyio
    await anyio.to_thread.run_sync(run_migrations)
```

```python
# main.py (FastAPI lifespan)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from db.migrate import apply_migrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    await apply_migrations()
    yield

app = FastAPI(lifespan=lifespan)
```

---

## CI/CD Checklist

- [ ] `DATABASE_URL` set in CI environment
- [ ] `alembic upgrade head` runs before tests
- [ ] Migration check: `alembic check` (exits non-zero if unapplied migrations exist)
- [ ] Downgrade tested: `alembic downgrade -1 && alembic upgrade head`
- [ ] No model changes without a matching migration file
- [ ] Production: run migrations before deploying new app version (blue/green safe if backward compatible)
