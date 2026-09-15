# FastAPI Boilerplate — Clean Architecture

Boilerplate FastAPI được tổ chức theo **Clean Architecture** (hay còn gọi là
hexagonal/ports & adapters): dễ test, dễ thay thế technology, business logic
không bị pha trộn với framework.

```
┌───────────────────────────────────────────────────────────┐
│                     API (FastAPI)                         │
│        routers • schemas (DTO) • deps • error handlers    │  Interface Adapter
├───────────────────────────────────────────────────────────┤
│                    Application                            │
│           use cases • input/output DTOs (Page)            │  Business Orchestration
├───────────────────────────────────────────────────────────┤
│                      Domain                               │
│      entities • business rules • ports • exceptions       │  Enterprise Core
└──────────────────────────────┬────────────────────────────┘
                               ▲ implements ports
┌──────────────────────────────┴────────────────────────────┐
│                   Infrastructure                          │
│   SQLAlchemy models • repositories • JWT • bcrypt         │  Adapters
└───────────────────────────────────────────────────────────┘
```

**Dependency rule:** mũi tên chỉ về trong. `domain` không import bất kỳ layer
nào khác; `application` chỉ phụ thuộc vào `domain`; `infrastructure` implement
các port của `domain`; `api` là nơi duy nhất "kết nối" các phần lại với nhau
(composition root).

## Tính năng

- ⚡ **FastAPI** + **Pydantic v2** + **SQLAlchemy 2.0 (async)** + **Alembic**
- 🏛️ Clean Architecture 4 layer, dependency injection qua `Depends`
- 🔐 **Auth JWT** (register / login / `Authorization: Bearer`) + **bcrypt**
- 🚦 **Rate limiting Redis-backed** (fixed window, fail-open, per client IP)
- 🛠️ **Code generator**: `make crud name=x` — sinh 1 resource CRUD đầy đủ (4 layer + tests)
- ✅ Example resource **Tasks** (CRUD đầy đủ, scoped theo user) để làm mẫu
- 🧪 **49 tests**: unit (fake in-memory qua `Protocol`) + integration (API thật, SQLite)
- 🔍 **mypy strict** + **ruff** (lint + format) + **pre-commit** + **CI (GitHub Actions)**
- 🐳 **Docker** + **docker-compose** (api + PostgreSQL)
- ⚙️ Config tập trung bằng `pydantic-settings` (`.env`)

## Cấu trúc thư mục

```
src/app/
├── main.py                     # App factory (create_app) + lifespan
├── api/                        # ── Interface Adapter (biết về HTTP) ──
│   ├── deps.py                 #    DI: session (UoW), repositories, current user, rate limit
│   ├── errors.py               #    Domain error → HTTP envelope
│   ├── schemas/                #    Pydantic request/response (DTO)
│   └── v1/endpoints/           #    Routers: health, auth, users, tasks
├── application/                # ── Use cases (chỉ phụ thuộc domain) ──
│   ├── common.py               #    Page[T], UNSET sentinel
│   ├── tasks/                  #    create / get / list / update / delete
│   └── auth/                   #    register / authenticate
├── domain/                     # ── Enterprise core (thuần Python) ──
│   ├── entities/               #    User, Task + business rules
│   ├── exceptions.py           #    DomainError, NotFound, Conflict, ...
│   └── ports/                  #    Protocol: repositories, PasswordHasher, TokenService
├── infrastructure/             # ── Adapters (implement các port) ──
│   ├── database/               #    engine/session, ORM models, mappers
│   ├── repositories/           #    SqlAlchemy*Repository
│   └── security/               #    BcryptPasswordHasher, JwtTokenService
└── core/                       # ── Shared kernel ──
    ├── config.py               #    Settings (pydantic-settings)
    ├── exceptions.py           #    InvalidTokenError
    └── logging.py
```

## Yêu cầu

- Python **3.11+**
- SQLite (mặc định, zero-setup) — hoặc PostgreSQL cho production

## Chạy local (5 phút)

```bash
# 1. Tạo venv + cài đặt
make install            # hoặc: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 2. Tạo file env (mặc định dùng SQLite tại ./app.db, auto-create tables)
cp .env.example .env

# 3. Chạy server (dev, có reload)
make run                # hoặc: .venv/bin/uvicorn app.main:app --reload
```

Mở [http://localhost:8000/docs](http://localhost:8000/docs) để xem Swagger UI.

### Chạy thử bằng curl

```bash
# Register
curl -s -X POST localhost:8000/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "password": "supersecret1", "full_name": "Alice"}'

# Login → nhận token
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "alice@example.com", "password": "supersecret1"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Tạo task
curl -s -X POST localhost:8000/v1/tasks \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title": "Học clean architecture", "description": "Đọc + thực hành"}'

# List tasks (phân trang + filter)
curl -s "localhost:8000/v1/tasks?limit=10&status=pending" -H "Authorization: Bearer $TOKEN"
```

## API

| Method | Đường dẫn            | Mô tả                                    | Auth |
|--------|----------------------|------------------------------------------|------|
| GET    | `/health`            | Liveness                                 | ❌   |
| GET    | `/v1/health`         | Readiness (check DB)                     | ❌   |
| POST   | `/v1/auth/register`  | Đăng ký tài khoản mới                    | ❌   |
| POST   | `/v1/auth/login`     | Đổi email+password lấy JWT               | ❌   |
| GET    | `/v1/users/me`       | Thông tin user đang đăng nhập            | ✅   |
| POST   | `/v1/tasks`          | Tạo task                                 | ✅   |
| GET    | `/v1/tasks`          | List + phân trang (`offset`, `limit`, `status`) | ✅ |
| GET    | `/v1/tasks/{id}`     | Chi tiết 1 task                          | ✅   |
| PATCH  | `/v1/tasks/{id}`     | Cập nhật một phần (`title`/`description`/`status`) | ✅ |
| DELETE | `/v1/tasks/{id}`     | Xóa task                                 | ✅   |

Mọi lỗi trả về cùng một hình dạng:

```json
{ "error": { "code": "NOT_FOUND", "message": "Task ... not found", "details": null } }
```

## Rate limiting (Redis)

Cơ chế **fixed-window counter** lưu trên Redis (1 Lua script atomic
`INCR + EXPIRE + TTL`), key theo **client IP**:

| Scope | Áp dụng | Limit mặc định |
|-------|---------|----------------|
| `global` | Mọi endpoint `/v1/*` (router-level dependency) | `RATE_LIMIT_GLOBAL` / `RATE_LIMIT_WINDOW_SECONDS` (100/60s) |
| `auth` | `/v1/auth/register` + `/v1/auth/login` (chống brute-force) | 10/60s (`AUTH_LIMIT_PER_MINUTE` trong `auth.py`) |

Hai scope **độc lập** với nhau: hết budget `auth` không ảnh hưởng budget
`global` và ngược lại. Khi bị limit, API trả về `429` cùng envelope chuẩn +
header `Retry-After`:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 30

{"error": {"code": "RATE_LIMITED", "message": "Too many requests, please slow down", "details": null}}
```

Thiết kế:

- **Port `RateLimiter`** (`domain/ports/rate_limiter.py`) + 2 implementation:
  `RedisRateLimiter` và `NoopRateLimiter` (chọn tự động theo config trong
  `infrastructure/rate_limit/__init__.py`).
- **Fail-open**: Redis sập → log lỗi và **cho phép request qua** (limiter hỏng
  không được kéo sập API).
- **Zero-setup**: `REDIS_URL` để trống → rate limiting tắt, chạy dev không cần
  Redis (docker-compose bật sẵn khi deploy).

Tăng giảm limit: sửa `RATE_LIMIT_GLOBAL` / `RATE_LIMIT_WINDOW_SECONDS` trong
`.env` (global), hoặc hằng số trong `api/v1/endpoints/auth.py` (auth), hoặc
dùng `rate_limit(...)` dependency cho endpoint bất kỳ:

```python
@router.post("/export", dependencies=[Depends(rate_limit("export", limit=5, window_seconds=3600))])
```

> Lưu ý: IP client lấy từ `request.client.host`. Sau reverse proxy (nginx,
> Cloudflare...), cần cấu hình proxy trust và cân nhắc dùng header
> `X-Forwarded-For` (tự viết thêm middleware nếu cần) để limit theo IP thật.

## Migrations (Alembic)

```bash
make migrate                                # áp dụng migrations đã có
make revision m="add notes column"          # autogenerate migration mới sau khi sửa ORM model
```

- Development (SQLite): bật `AUTO_CREATE_TABLES=true` để tự tạo bảng khi start
  (tiện, không cần chạy migration).
- Production: `AUTO_CREATE_TABLES=false` + `alembic upgrade head` (docker-compose
  đã chạy sẵn bước này trước khi khởi động uvicorn).

## Docker (PostgreSQL)

```bash
make docker-up        # build + chạy api (8000) + postgres (5432)
make docker-down
```

## Tests & chất lượng code

```bash
make test             # pytest (unit + integration)
make lint             # ruff check + ruff format --check
make format           # ruff fix + format
make typecheck        # mypy (strict)
```

Unit test use case chạy trên **fake in-memory** — vì port là `typing.Protocol`,
fake không cần kế thừa gì:

```python
class InMemoryTaskRepository:   # implement TaskRepository
    async def add(self, task: Task) -> Task: ...
```

## Thêm resource mới

### Cách nhanh: `make crud` (tự sinh toàn bộ 4 layer)

```bash
make crud name=projects
```

Tương tự `nest generate resource` — script `scripts/generate_crud.py` sinh
**14 file** cho 1 resource CRUD hoàn chỉnh theo đúng kiến trúc của boilerplate:

| Layer | Files sinh ra (ví dụ `projects`) |
|---|---|
| Domain | `entities/projects.py` (entity + validate), `ports/projects_repository.py` (Protocol) |
| Application | `application/projects/{create,get,list,update,delete}_project.py` (5 use cases) |
| Infrastructure | `database/models/projects.py` (ORM), `repositories/projects_repository.py` + mappers |
| API | `schemas/projects.py`, `v1/endpoints/projects.py` + dependency + đăng ký router |
| Tests | `test_projects_usecases.py` (fake in-memory) + `test_projects.py` (integration HTTP) |

Resource sinh ra có 2 field tổng quát `title` (required) + `body` (optional),
bắt buộc auth (`CurrentUser`) nhưng **chưa** scoped theo user — muốn scoped
như tasks thì xem `tasks.py` làm mẫu. Sau khi sinh:

```bash
make revision m="create projects table"   # autogenerate migration
make migrate
make test
```

> Mẹo: muốn xoá resource thử nghiệm, xoá 14 files trên + các dòng đã patch
> (`mappers.py`, `deps.py`, `router.py`, `models/__init__.py`) + file migration.

### Tự viết (để hiểu pattern)

1. **Domain**: entity (dataclass + rules) trong `domain/entities/`, port
   (`Protocol`) trong `domain/ports/`.
2. **Application**: mỗi use case 1 class nhỏ với `execute(...)`, nhận **port**
   qua constructor.
3. **Infrastructure**: ORM model + repository implement port bằng SQLAlchemy.
   Sửa ORM xong → `make revision m="..."` → `make migrate`.
4. **API**: schemas (Pydantic DTO) + router mỏng — gọi use case, trả entity.
   Đăng ký router trong `api/v1/router.py`.
5. **Tests**: unit (fake repo qua `Protocol`) + integration (flow qua HTTP).

Use case mới chỉ cần **1 dependency duy nhất** (repository port) nên test
không cần database, không cần FastAPI.

## Cấu hình (env)

| Biến                        | Mặc định                        | Ý nghĩa                                  |
|-----------------------------|---------------------------------|------------------------------------------|
| `APP_NAME`                  | `FastAPI Boilerplate`           | Tên app (hiện trên /docs)                |
| `DEBUG`                     | `false`                         | Chồng traceback khi có lỗi               |
| `LOG_LEVEL`                 | `INFO`                          | Level log                                 |
| `API_V1_PREFIX`             | `/v1`                           | Prefix API v1                             |
| `DATABASE_URL`              | `sqlite+aiosqlite:///./app.db`  | URL SQLAlchemy (async)                   |
| `AUTO_CREATE_TABLES`        | `false`                         | Tự `create_all` khi start (dev only)     |
| `SECRET_KEY`                | —                               | **Bắt buộc đổi** (JWT signing key)       |
| `REDIS_URL`                 | `` (trống = tắt rate limit)     | Ví dụ `redis://localhost:6379/0`         |
| `RATE_LIMIT_ENABLED`        | `true`                          | `false` để tắt hoàn toàn                 |
| `RATE_LIMIT_GLOBAL`         | `100`                           | Request/IP/window cho mọi endpoint v1    |
| `RATE_LIMIT_WINDOW_SECONDS` | `60`                            | Cửa sổ tính limit (giây)                 |
| `JWT_ALGORITHM`             | `HS256`                         | Algorithm JWT                             |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `1440`                          | Thời hạn token (phút)                    |
| `CORS_ORIGINS`              | `["*"]`                         | List origins được phép                   |
| `DEFAULT_PAGE_SIZE`         | `20`                            | `limit` mặc định của list                |
| `MAX_PAGE_SIZE`             | `100`                           | `limit` tối đa                           |

## License

MIT
