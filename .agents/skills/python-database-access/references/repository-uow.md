# Repository Pattern & Unit of Work — Deep Reference

## Why This Architecture

| Concern | Without pattern | With Repository + UoW |
|---------|----------------|----------------------|
| Query logic | Scattered in routes/services | Centralized in repositories |
| Transaction boundary | Ambiguous, often wrong | Explicit in service layer |
| Testing | Must mock SQLAlchemy directly | Mock/stub repositories |
| Session lifetime | Error-prone manual handling | UoW owns session lifecycle |

---

## Base Repository

```python
# db/repositories/base.py
from collections.abc import Sequence
from typing import Any, Generic, TypeVar
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async repository. Subclass and set `model`."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Read ---

    async def get_by_id(self, id: Any) -> ModelT | None:
        """Get single record by primary key. Returns None if missing."""
        return await self.session.get(self.model, id)

    async def get_by_id_or_raise(self, id: Any) -> ModelT:
        """Get single record by primary key. Raises ValueError if missing."""
        obj = await self.session.get(self.model, id)
        if obj is None:
            raise ValueError(f"{self.model.__name__} with id={id!r} not found")
        return obj

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ModelT]:
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def exists(self, id: Any) -> bool:
        obj = await self.session.get(self.model, id)
        return obj is not None

    # --- Write (use flush, not commit) ---

    async def add(self, obj: ModelT) -> ModelT:
        """Persist a new object. Flush to assign ID; caller commits."""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def add_all(self, objs: list[ModelT]) -> list[ModelT]:
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def delete(self, obj: ModelT) -> None:
        """Delete object. Flush immediately; caller commits."""
        await self.session.delete(obj)
        await self.session.flush()

    async def delete_by_id(self, id: Any) -> bool:
        """Delete by primary key. Returns False if not found."""
        obj = await self.session.get(self.model, id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True
```

---

## Concrete Repository Examples

### UserRepository

```python
# db/repositories/user.py
from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models.user import User
from db.models.post import Post
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_with_posts(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.posts))
        )
        return result.scalar_one_or_none()

    async def get_active(self, *, limit: int = 100, offset: int = 0) -> Sequence[User]:
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def email_exists(self, email: str) -> bool:
        from sqlalchemy import exists as sa_exists
        result = await self.session.execute(
            select(sa_exists().where(User.email == email))
        )
        return result.scalar_one()
```

### PostRepository (with FK filtering)

```python
# db/repositories/post.py
from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from db.models.post import Post
from .base import BaseRepository


class PostRepository(BaseRepository[Post]):
    model = Post

    async def get_by_author(
        self, author_id: int, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Post]:
        result = await self.session.execute(
            select(Post)
            .where(Post.author_id == author_id)
            .order_by(Post.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_with_author(self, post_id: int) -> Post | None:
        result = await self.session.execute(
            select(Post)
            .where(Post.id == post_id)
            .options(joinedload(Post.author))
        )
        return result.unique().scalar_one_or_none()
```

---

## Unit of Work

### Implementation

```python
# db/unit_of_work.py
from __future__ import annotations
from types import TracebackType
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from db.repositories.user import UserRepository
from db.repositories.post import PostRepository


class UnitOfWork:
    """
    Manages a single AsyncSession and exposes typed repositories.
    Commit or rollback at the service/route boundary.

    Usage:
        async with UnitOfWork(session_factory) as uow:
            user = await uow.users.get_by_email("a@example.com")
            user.email = "b@example.com"
            await uow.commit()
    """

    session: AsyncSession
    users: UserRepository
    posts: PostRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._factory()
        self.users = UserRepository(self.session)
        self.posts = PostRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        """Flush pending changes without committing the transaction."""
        await self.session.flush()
```

### Wiring into FastAPI

```python
# api/dependencies.py
from collections.abc import AsyncGenerator
from db.engine import AsyncSessionLocal
from db.unit_of_work import UnitOfWork


async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    async with UnitOfWork(AsyncSessionLocal) as uow:
        yield uow
```

```python
# api/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import get_uow
from db.unit_of_work import UnitOfWork
from schemas.user import UserCreate, UserResponse
from db.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    payload: UserCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> User:
    if await uow.users.email_exists(payload.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email, name=payload.name)
    await uow.users.add(user)
    await uow.commit()
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> User:
    user = await uow.users.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

---

## Service Layer (Optional)

For complex business logic, add a service layer between routes and repositories:

```python
# services/user_service.py
from db.unit_of_work import UnitOfWork
from db.models.user import User
from schemas.user import UserCreate


class UserService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def register(self, payload: UserCreate) -> User:
        if await self.uow.users.email_exists(payload.email):
            raise ValueError("Email already registered")
        user = User(email=payload.email, name=payload.name)
        await self.uow.users.add(user)
        await self.uow.commit()
        return user
```

```python
# api/dependencies.py — service dependency
from api.dependencies import get_uow

async def get_user_service(uow: UnitOfWork = Depends(get_uow)) -> UserService:
    return UserService(uow)
```

---

## Testing Repositories

### Unit test with in-memory SQLite

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.models.base import Base
from db.models.user import User
from db.repositories.user import UserRepository

@pytest_asyncio.fixture()
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_by_email(session: AsyncSession) -> None:
    repo = UserRepository(session)
    user = User(email="test@example.com", name="Test")
    await repo.add(user)
    await session.commit()

    found = await repo.get_by_email("test@example.com")
    assert found is not None
    assert found.id == user.id
```

### Integration test with FastAPI TestClient

```python
from httpx import AsyncClient
from fastapi import FastAPI
from api.dependencies import get_uow

async def test_create_user(app: FastAPI, test_uow: UnitOfWork) -> None:
    app.dependency_overrides[get_uow] = lambda: test_uow
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/users/", json={"email": "a@example.com"})
    assert response.status_code == 201
```

---

## Anti-Patterns to Avoid

```python
# BAD: committing inside a repository method
async def add(self, obj: ModelT) -> ModelT:
    self.session.add(obj)
    await self.session.commit()  # Wrong — breaks Unit of Work semantics
    return obj

# BAD: accessing unloaded relationship after session close
user = await session.get(User, 1)
# session closed here
print(user.posts)  # MissingGreenlet!

# BAD: creating a new session inside a repository
async def get_by_email(self, email: str) -> User | None:
    async with AsyncSessionLocal() as session:  # Wrong — ignores current transaction
        ...

# BAD: sharing a session between requests
shared_session = AsyncSessionLocal()  # Module-level — NEVER do this
```
