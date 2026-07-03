# Karavay Production Console — технический дизайн-проект

Референс (`DagonRanchi/diplom/abiturients_server`) использован только как источник паттернов: структура папок монорепо, folder manager UX (дерево слева / содержимое справа / breadcrumbs / drag-and-drop), разделение backend router'ов по доменам, набор Render-конфигов. Предметная область полностью заменена: вместо приёмной системы — производственный конфигуратор техкарт и исполнитель заявок.

---

## 1. Краткая фиксация требований

Система — производственный конфигуратор техкарт и исполнитель заявок:

- Ролевая модель с динамическими ролями, правами на вкладки и на папки, назначением пользователей на роли.
- Windows-подобный файловый менеджер с деревом папок, доступ к которым настраивается администратором.
- Три типа конфигов внутри папок: **ингредиенты**, **продукция**, **события**.
- Ингредиенты наследуются вниз по дереву папок.
- Продукция содержит рецептуру — упорядоченный список шагов (ingredient step / event step) с единицами измерения и поддержкой составных величин ("3 л 200 мл").
- События — шаблоны действий (таймер / проверка веса / подтверждение фразой), параметры исполнения задаются в шаге рецепта, а не в шаблоне.
- Загрузка заявки из Excel (продукция / количество / время), просмотр текущей заявки, пошаговое исполнение с пересчётом количества по коэффициенту и кнопкой "Дальше".
- Стек: FastAPI + PostgreSQL + React/Vite/TS, деплой на Render (backend — Docker Web Service, frontend — Static Site, БД — Render Postgres).

---

## 2. Список допущений

1. **Пользователь может иметь несколько ролей одновременно**; итоговые права — объединение (OR) прав всех его ролей.
2. **Права на папку наследуются вниз до ближайшего явного переопределения** (nearest-ancestor-wins), без отдельного флага "запретить" — только наличие/отсутствие разрешающей записи.
3. **Права на вкладку — грубый гейт** (можно ли вообще открыть раздел UI), права на папку/глобальные права — точный гейт на конкретное действие внутри раздела.
4. Есть системная неудаляемая роль **"Administrator"** (`is_system=true`), которая обходит все проверки прав. Создаётся сид-скриптом при первом деплое через env-переменные.
5. **Все PK — UUID**, генерируются в приложении (`uuid.uuid4()`), не в БД — чтобы не зависеть от Postgres-расширений (`pgcrypto`/`ltree`) на управляемом Render Postgres.
6. **Иерархия папок** хранится как adjacency list (`parent_id`) + материализованный текстовый путь (`materialized_path`) для быстрых prefix-запросов — без расширения `ltree`.
7. **Канонические единицы хранения**: вес → граммы (integer), объём → миллилитры (integer), время → секунды (integer), температура → °C (numeric(5,1)). Составные значения ("3 л 200 мл") не хранятся отдельными полями — хранится только каноническое число, UI формирует и разбирает составной ввод/вывод.
8. **Базовое количество продукции** — всегда в штуках (integer).
9. **Удаление папки требует, чтобы она была пустой** (без вложенных папок и конфигов).
10. **Заявка (Excel) не содержит дату** — при загрузке администратор явно указывает "дату исполнения"; время из строки заявки объединяется с этой датой.
11. **Формат Excel в MVP**: один столбец A, без заголовков, данные блоками по 3 строки (название/количество/время) подряд без разделителей. Число строк должно быть кратно 3.
12. **Сопоставление продукции по названию** — точное сравнение без учёта регистра и пробелов по краям. Несовпадения помечаются `unmatched` и решаются вручную.
13. **Исходный Excel-файл не хранится** как бинарник — хранится только распарсенный результат и имя файла.
14. **Execution plan создаётся лениво** (get-or-create при первом открытии позиции заявки) и **снимает снапшот рецепта** на момент создания.
15. **Округление количества** при пересчёте по коэффициенту — half-up до целой канонической единицы.
16. Один часовой пояс — datetime хранится наивным.
17. Frontend получает `VITE_API_BASE_URL` на этапе сборки (build-time Vite env).

---

## 3. Общая архитектура системы

```
┌─────────────────────┐        HTTPS/JSON        ┌──────────────────────────┐
│  React SPA (Vite)    │ ───────────────────────▶ │   FastAPI backend         │
│  Render Static Site   │ ◀─────────────────────── │   Render Docker Web Svc   │
└─────────────────────┘                           │  - REST API /api/*        │
                                                    │  - JWT auth               │
                                                    │  - Permission service     │
                                                    │  - Excel import service   │
                                                    │  - Unit conversion svc    │
                                                    └────────────┬─────────────┘
                                                                 │ asyncpg
                                                                 ▼
                                                    ┌──────────────────────────┐
                                                    │  Render PostgreSQL        │
                                                    └──────────────────────────┘
```

Один backend-процесс, один frontend, одна БД — без микросервисов, без очередей/брокеров в MVP.

---

## 4. Структура монорепозитория

```
karavay/
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/
│  │  │  ├─ config.py
│  │  │  ├─ security.py
│  │  │  ├─ deps.py
│  │  │  └─ permissions.py
│  │  ├─ db/
│  │  │  ├─ base.py
│  │  │  └─ session.py
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  │  ├─ permission_service.py
│  │  │  ├─ folder_service.py
│  │  │  ├─ ingredient_service.py
│  │  │  ├─ recipe_service.py
│  │  │  ├─ unit_conversion.py
│  │  │  ├─ order_import_service.py
│  │  │  └─ execution_service.py
│  │  └─ routers/
│  │     ├─ auth.py, users.py, roles.py, permissions.py, tabs.py,
│  │       folders.py, ingredients.py, products.py, events.py,
│  │       orders.py, execution.py
│  ├─ alembic/
│  │  ├─ env.py
│  │  └─ versions/
│  ├─ scripts/
│  │  └─ seed_admin.py
│  ├─ requirements.txt
│  ├─ alembic.ini
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ main.tsx, App.tsx
│  │  ├─ api/
│  │  ├─ auth/
│  │  ├─ routes/
│  │  ├─ pages/
│  │  ├─ components/
│  │  ├─ hooks/
│  │  └─ types/
│  ├─ index.html
│  ├─ vite.config.ts
│  └─ package.json
├─ docs/
│  └─ design.md
└─ render.yaml
```

---

## 5. Backend architecture (FastAPI)

- **FastAPI + Pydantic v2**, **SQLAlchemy 2.0 async** (`asyncpg`), **Alembic**.
- Auth: JWT access-токен (15 мин, в теле ответа, хранится во фронте в памяти) + refresh-токен (7 дней, httpOnly Secure cookie). Хэш пароля — `passlib[bcrypt]`. JWT — `pyjwt`.
- Роутеры разбиты по доменам, каждый использует `Depends(get_current_user)` и `Depends(require_permission(code, ...))`.
- **PermissionService** — единая точка проверки прав, используется и в API, и через `GET /me/permissions`.
- Ошибки — единый хендлер: `403 permission_denied`, `404 not_found`, `409 conflict`.
- Валидация Excel и unit-конвертации — в сервисном слое.
- Мутирующие операции — в транзакции, особенно `move_folder` и `reorder_steps`.

---

## 6. Frontend architecture (React)

- **React 18 + Vite + TypeScript**, **React Router v6** (требует rewrite-правило на Render Static Site).
- Состояние сервера — **TanStack Query**. Локальный UI-стейт — React state/context, без Redux.
- `AuthContext` хранит access-токен в памяти + профиль + эффективные права (`GET /me/permissions`).
- `PermissionGate` — компонент-обёртка, скрывает/дизейблит UI по коду права (UI-скрытие не заменяет серверную проверку).
- `FolderTree` — рекурсивный компонент, ленивая подгрузка детей, drag-and-drop через `@dnd-kit`.
- Конфиги открываются как маршрутизируемая модальная панель (`/folders/:folderId/ingredients/:id` и т.п.) — deep-link + кнопка "назад".

---

## 7. Модель данных PostgreSQL

### 7.1 Auth / RBAC

```sql
users (
  id UUID PK,
  email CITEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

roles (
  id UUID PK,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  is_system BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

user_roles (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
)

app_tabs (
  id UUID PK,
  key TEXT UNIQUE NOT NULL,
  label TEXT NOT NULL,
  order_index INT NOT NULL
)

permission_defs (
  code TEXT PK,
  label TEXT NOT NULL,
  scope_type TEXT NOT NULL CHECK (scope_type IN ('tab','folder','global'))
)

role_permissions (
  id UUID PK,
  role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
  permission_code TEXT REFERENCES permission_defs(code),
  tab_id UUID REFERENCES app_tabs(id) ON DELETE CASCADE,
  folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
  granted BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT scope_matches_type CHECK (
    (tab_id IS NOT NULL AND folder_id IS NULL) OR
    (tab_id IS NULL AND folder_id IS NOT NULL) OR
    (tab_id IS NULL AND folder_id IS NULL)
  ),
  UNIQUE (role_id, permission_code, tab_id, folder_id)
)
```

Одна таблица `role_permissions` с двумя реальными nullable FK вместо трёх разных таблиц — одна точка правды с реальной ссылочной целостностью (каскадное удаление при удалении папки/вкладки).

### 7.2 Папки

```sql
folders (
  id UUID PK,
  parent_id UUID REFERENCES folders(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  materialized_path TEXT NOT NULL,
  depth INT NOT NULL,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (parent_id, name)
)
CREATE INDEX ON folders (materialized_path text_pattern_ops);
```

`ON DELETE RESTRICT` на `parent_id` физически защищает от удаления непустой папки.

### 7.3 Конфиги

```sql
ingredients (
  id UUID PK,
  folder_id UUID REFERENCES folders(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  measure_type TEXT NOT NULL CHECK (measure_type IN ('weight','volume','time','temperature')),
  description TEXT,
  allowed_container_weights_g INTEGER[],
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

event_templates (
  id UUID PK,
  folder_id UUID REFERENCES folders(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  description TEXT,
  event_type TEXT NOT NULL CHECK (event_type IN ('timer','weight_check','phrase_confirmation')),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

products (
  id UUID PK,
  folder_id UUID REFERENCES folders(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  base_quantity INTEGER NOT NULL CHECK (base_quantity > 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

Событийные шаблоны — такие же папко-центричные конфиги, как ингредиенты, и подчиняются той же логике наследования.

### 7.4 Рецептура

```sql
recipe_steps (
  id UUID PK,
  product_id UUID REFERENCES products(id) ON DELETE CASCADE,
  order_index INT NOT NULL,
  step_type TEXT NOT NULL CHECK (step_type IN ('ingredient','event')),

  ingredient_id UUID REFERENCES ingredients(id) ON DELETE RESTRICT,
  quantity_canonical INTEGER,

  event_template_id UUID REFERENCES event_templates(id) ON DELETE RESTRICT,
  event_params JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT step_shape CHECK (
    (step_type = 'ingredient' AND ingredient_id IS NOT NULL AND event_template_id IS NULL AND quantity_canonical IS NOT NULL)
    OR
    (step_type = 'event' AND event_template_id IS NOT NULL AND ingredient_id IS NULL)
  ),
  UNIQUE (product_id, order_index)
)
```

Единая таблица шагов вместо двух подтаблиц — шаги всегда читаются и переупорядочиваются как один список.

### 7.5 Заявки и исполнение

```sql
orders (
  id UUID PK,
  uploaded_by UUID REFERENCES users(id),
  source_filename TEXT NOT NULL,
  execution_date DATE NOT NULL,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

order_lines (
  id UUID PK,
  order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
  row_group_index INT NOT NULL,
  product_name_raw TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  due_time TIME NOT NULL,
  matched_product_id UUID REFERENCES products(id),
  match_status TEXT NOT NULL CHECK (match_status IN ('matched','unmatched')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

execution_plans (
  id UUID PK,
  order_line_id UUID UNIQUE REFERENCES order_lines(id) ON DELETE CASCADE,
  product_id UUID REFERENCES products(id),
  multiplier NUMERIC(10,4) NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('not_started','in_progress','completed')) DEFAULT 'not_started',
  current_step_index INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

execution_plan_steps (
  id UUID PK,
  execution_plan_id UUID REFERENCES execution_plans(id) ON DELETE CASCADE,
  order_index INT NOT NULL,
  step_type TEXT NOT NULL CHECK (step_type IN ('ingredient','event')),
  ingredient_name_snapshot TEXT,
  measure_type_snapshot TEXT,
  quantity_canonical_computed INTEGER,
  event_name_snapshot TEXT,
  event_type_snapshot TEXT,
  event_params_snapshot JSONB,
  status TEXT NOT NULL CHECK (status IN ('pending','done')) DEFAULT 'pending',
  completed_at TIMESTAMPTZ,
  UNIQUE (execution_plan_id, order_index)
)
```

---

## 8. ER-диаграмма (Mermaid)

```mermaid
erDiagram
    USERS ||--o{ USER_ROLES : has
    ROLES ||--o{ USER_ROLES : assigned_to
    ROLES ||--o{ ROLE_PERMISSIONS : grants
    PERMISSION_DEFS ||--o{ ROLE_PERMISSIONS : type_of
    APP_TABS ||--o{ ROLE_PERMISSIONS : scoped_to_tab
    FOLDERS ||--o{ ROLE_PERMISSIONS : scoped_to_folder

    FOLDERS ||--o{ FOLDERS : parent_of
    FOLDERS ||--o{ INGREDIENTS : contains
    FOLDERS ||--o{ EVENT_TEMPLATES : contains
    FOLDERS ||--o{ PRODUCTS : contains

    PRODUCTS ||--o{ RECIPE_STEPS : has_steps
    INGREDIENTS ||--o{ RECIPE_STEPS : used_in
    EVENT_TEMPLATES ||--o{ RECIPE_STEPS : used_in

    ORDERS ||--o{ ORDER_LINES : contains
    ORDER_LINES ||--o| EXECUTION_PLANS : produces
    PRODUCTS ||--o{ ORDER_LINES : matched_to
    EXECUTION_PLANS ||--o{ EXECUTION_PLAN_STEPS : snapshot_of

    USERS {
        uuid id PK
        citext email
        text password_hash
        text full_name
        bool is_active
    }
    ROLES {
        uuid id PK
        text name
        bool is_system
    }
    PERMISSION_DEFS {
        text code PK
        text scope_type
    }
    APP_TABS {
        uuid id PK
        text key
        text label
    }
    ROLE_PERMISSIONS {
        uuid id PK
        uuid role_id FK
        text permission_code FK
        uuid tab_id FK
        uuid folder_id FK
    }
    FOLDERS {
        uuid id PK
        uuid parent_id FK
        text name
        text materialized_path
        int depth
    }
    INGREDIENTS {
        uuid id PK
        uuid folder_id FK
        text name
        text measure_type
        int[] allowed_container_weights_g
        bool is_active
    }
    EVENT_TEMPLATES {
        uuid id PK
        uuid folder_id FK
        text name
        text event_type
        bool is_active
    }
    PRODUCTS {
        uuid id PK
        uuid folder_id FK
        text name
        int base_quantity
    }
    RECIPE_STEPS {
        uuid id PK
        uuid product_id FK
        int order_index
        text step_type
        uuid ingredient_id FK
        int quantity_canonical
        uuid event_template_id FK
        jsonb event_params
    }
    ORDERS {
        uuid id PK
        text source_filename
        date execution_date
    }
    ORDER_LINES {
        uuid id PK
        uuid order_id FK
        text product_name_raw
        int quantity
        time due_time
        uuid matched_product_id FK
        text match_status
    }
    EXECUTION_PLANS {
        uuid id PK
        uuid order_line_id FK
        uuid product_id FK
        numeric multiplier
        text status
        int current_step_index
    }
    EXECUTION_PLAN_STEPS {
        uuid id PK
        uuid execution_plan_id FK
        int order_index
        text step_type
        int quantity_canonical_computed
        text status
    }
```

---

## 9. Схема ролей и прав доступа

### 9.1 Каталог прав (`permission_defs`, сидируется миграцией)

| code | label | scope_type |
|---|---|---|
| `tab.view` | Просмотр вкладки | tab |
| `tab.edit` | Редактирование вкладки | tab |
| `folder.view` | Просмотр папки | folder |
| `folder.create` | Создание внутри папки | folder |
| `folder.edit` | Редактирование внутри папки | folder |
| `order.execute` | Исполнение заявок/планов | global |
| `admin.manage` | Управление пользователями и ролями | global |

### 9.2 Двухуровневая модель

Вкладка — грубый гейт (доступен ли раздел UI). Папка/глобальное право — точный гейт на конкретное действие.

### 9.3 Резолвинг прав на папку (nearest-ancestor-wins)

```python
async def has_folder_permission(user, code: str, folder: Folder) -> bool:
    if user.has_system_role():
        return True
    ancestor_ids = folder.ancestor_ids_incl_self()
    role_ids = user.role_ids()
    rows = await db.execute(
        select(RolePermission)
        .where(RolePermission.role_id.in_(role_ids))
        .where(RolePermission.permission_code == code)
        .where(RolePermission.folder_id.in_(ancestor_ids))
    )
    rows = rows.scalars().all()
    if not rows:
        return False
    deepest = max(rows, key=lambda r: folder_depth[r.folder_id])
    return deepest.granted
```

Отсутствие любой строки на всём пути от корня = запрет по умолчанию.

### 9.4 FastAPI dependency

```python
def require_permission(code: str, folder_param: str | None = None, tab_key: str | None = None):
    async def checker(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        if folder_param:
            folder = await folder_service.get(db, request.path_params[folder_param])
            ok = await permission_service.has_folder_permission(db, user, code, folder)
        elif tab_key:
            ok = await permission_service.has_tab_permission(db, user, code, tab_key)
        else:
            ok = await permission_service.has_global_permission(db, user, code)
        if not ok:
            raise HTTPException(403, detail="permission_denied")
    return checker
```

### 9.5 Пример ролей (иллюстративно)

| Роль | Права |
|---|---|
| Administrator (`is_system`) | Все права, обход проверок |
| Технолог | `tab.view/edit` на "Файлы"; `folder.edit` на "Рецептуры" (+потомки); `tab.view` на "Текущая заявка" |
| Оператор цеха | `tab.view` только на "Текущая заявка"; `order.execute` (global) |
| Наблюдатель | `tab.view` на "Файлы"; `folder.view` на конкретный цех |

---

## 10. Схема папок и наследования ингредиентов

### 10.1 Хранение дерева

`parent_id` — для операций дерева. `materialized_path` — текст `/<root_id>/.../<self_id>/`, обновляется при создании и перемещении поддерева.

### 10.2 Правило видимости ингредиента (и event_template)

Ингредиент, созданный в папке `F`, доступен в `F` и во всех вложенных подпапках.

```sql
SELECT i.*
FROM ingredients i
JOIN folders f_ing ON f_ing.id = i.folder_id
JOIN folders f_target ON f_target.id = :target_folder_id
WHERE f_target.materialized_path LIKE f_ing.materialized_path || '%'
  AND i.is_active = TRUE;
```

Путь папки ингредиента — префикс пути целевой папки → папка ингредиента является предком (или собой). Индекс `text_pattern_ops` делает `LIKE 'prefix%'` дешёвым. Тот же SQL применяется к `event_templates`.

### 10.3 Перемещение папки (drag-and-drop)

`move_folder(folder_id, new_parent_id)`:
1. Проверить, что `new_parent_id` не потомок `folder_id` (иначе цикл).
2. В транзакции обновить `parent_id`.
3. Массово пересчитать `materialized_path`/`depth` у самой папки и всех потомков.
4. Требуется `folder.edit` и на исходной, и на целевой папке.

### 10.4 Обратная связь "где используется"

```sql
SELECT p.id, p.name, f.materialized_path
FROM recipe_steps rs
JOIN products p ON p.id = rs.product_id
JOIN folders f ON f.id = p.folder_id
WHERE rs.ingredient_id = :ingredient_id
ORDER BY f.materialized_path, p.name;
```

Плоский список, сгруппированный по пути папки — проще дерева, для MVP достаточно.

### 10.5 Удаление

Папку нельзя удалить, если есть дочерние папки/конфиги (`ON DELETE RESTRICT`). Ингредиент/шаблон события нельзя удалить, если на него ссылается `recipe_step` — предлагается деактивация (`is_active=false`).

---

## 11. Подробная схема конфигов

### 11.1 Ingredient config

| Поле | Тип | Комментарий |
|---|---|---|
| name | text | |
| measure_type | enum(weight, volume, time, temperature) | определяет каноническую единицу |
| description | text | |
| allowed_container_weights_g | int[] | из строки "500, 1000, 5000" |
| is_active | bool | soft-toggle |
| used_in (derived) | — | вычисляется запросом 10.4 |

### 11.2 Event config (шаблон)

| Поле | Тип | Комментарий |
|---|---|---|
| name | text | например "Отправить на тестомес" |
| description | text | |
| event_type | enum(timer, weight_check, phrase_confirmation) | форма `event_params` в шаге рецепта |
| is_active | bool | |

Шаблон не содержит длительности/веса/фразы — параметры конкретизируются в шаге рецепта.

### 11.3 Product config

| Поле | Тип | Комментарий |
|---|---|---|
| name | text | например "Белый хлеб" |
| base_quantity | int | базовое количество в штуках |
| is_active | bool | |
| recipe_steps | RecipeStep[] | редактируется отдельными эндпоинтами |

---

## 12. Подробная схема recipe steps

### 12.1 Общая структура

Упорядоченный список `recipe_steps`, каждый с `order_index` (0..N-1, плотная последовательность, переиндексируется целиком при reorder).

### 12.2 Ingredient step

`ingredient_id` — только из набора, видимого в папке продукта. `quantity_canonical` — целое число в канонической единице. Единица ввода/отображения в UI не хранится.

### 12.3 Event step

`event_template_id` — из видимых шаблонов. `event_params` (JSONB) зависит от `event_template.event_type`:

| event_type | event_params |
|---|---|
| `timer` | `{ "duration_seconds": 600 }` |
| `weight_check` | `{ "target_weight_g": 2000, "tolerance_g": 20 }` |
| `phrase_confirmation` | `{ "phrase": "Смесь готова" }` |

Валидация — дискриминированный Pydantic-union по `event_type`, подгруженному на бэкенде из `event_template_id`.

### 12.4 Единицы измерения и составные величины

Канонические единицы хранения:

| measure_type | canonical unit | тип поля |
|---|---|---|
| weight | грамм | INTEGER |
| volume | миллилитр | INTEGER |
| time | секунда | INTEGER |
| temperature | °C | NUMERIC(5,1) |

Единицы отображения:

| measure_type | доступные единицы | коэффициент к канонической |
|---|---|---|
| weight | г, кг, т | 1, 1000, 1 000 000 |
| volume | мл, л | 1, 1000 |
| time | сек, мин, ч | 1, 60, 3600 |
| temperature | °C | 1 (без составных) |

Составной ввод реализуется компонентом `UnitQuantityInput`: пара [значение]+[единица] по умолчанию, кнопка "+ добавить единицу" открывает вторую пару меньшего порядка; на сохранении фронт суммирует в каноническую единицу, на бэкенд уходит только итоговое целое число.

Отображение — чистая функция форматирования:

```python
def format_compound(value_canonical: int, measure_type: str) -> str:
    if measure_type == "weight":
        kg, g = divmod(value_canonical, 1000)
        return f"{kg} кг {g} г" if kg else f"{g} г"
    if measure_type == "volume":
        l, ml = divmod(value_canonical, 1000)
        return f"{l} л {ml} мл" if l else f"{ml} мл"
    if measure_type == "time":
        h, rem = divmod(value_canonical, 3600)
        m, s = divmod(rem, 60)
        parts = [p for p in [f"{h} ч" if h else "", f"{m} мин" if m else "", f"{s} сек" if s else ""] if p]
        return " ".join(parts)
    if measure_type == "temperature":
        return f"{value_canonical:.1f} °C"
```

Расчёты всегда идут в канонической целочисленной единице; отображение — производная, не источник истины.

### 12.5 Reorder

`PATCH /products/{id}/steps/reorder` принимает полный упорядоченный список `step_id[]`, бэкенд в одной транзакции проставляет `order_index = position` для всех.

---

## 13. Подробная схема загрузки заявок из Excel

### 13.1 Формат (MVP)

Один столбец A, без заголовков, блоки по 3 строки подряд:

```
Row 1: белый хлеб
Row 2: 150
Row 3: 8:30
Row 4: батон нарезной
Row 5: 80
Row 6: 9:00
```

Валидация: `count(rows) % 3 == 0`.

### 13.2 Форма загрузки

Файл (`.xlsx`) + обязательное поле "дата исполнения".

### 13.3 Парсинг (openpyxl, без pandas)

```python
def parse_order_file(wb_bytes: bytes, execution_date: date) -> list[ParsedLine]:
    wb = openpyxl.load_workbook(io.BytesIO(wb_bytes), data_only=True)
    ws = wb.active
    values = [row[0].value for row in ws.iter_rows(min_col=1, max_col=1) if row[0].value is not None]
    if len(values) % 3 != 0:
        raise OrderParseError("row_count_not_multiple_of_3")
    lines = []
    for i in range(0, len(values), 3):
        name_raw, qty_raw, time_raw = values[i:i+3]
        lines.append(ParsedLine(
            row_group_index=i // 3,
            product_name_raw=str(name_raw).strip(),
            quantity=int(qty_raw),
            due_time=_parse_time(time_raw),
        ))
    return lines

def _parse_time(raw) -> time:
    if isinstance(raw, datetime.time):
        return raw
    if isinstance(raw, datetime.datetime):
        return raw.time()
    return datetime.strptime(str(raw).strip(), "%H:%M").time()
```

### 13.4 Сопоставление продукции

```sql
SELECT id FROM products
WHERE lower(trim(name)) = lower(trim(:product_name_raw)) AND is_active = TRUE
LIMIT 1;
```

Найдено → `matched_product_id`, `match_status='matched'`. Не найдено → `unmatched`, строка сохраняется с ручным resolver'ом (`PATCH /order-lines/{id}/match`).

### 13.5 Результат

`POST /orders/upload` создаёт `orders` + все `order_lines` одной транзакцией, возвращает сводку: всего строк, matched, unmatched.

---

## 14. Подробная схема execution plan

### 14.1 Генерация (get-or-create, лениво)

```python
async def get_or_create_execution_plan(order_line_id: UUID) -> ExecutionPlan:
    existing = await db.get(ExecutionPlan, by=order_line_id)
    if existing:
        return existing

    order_line = await load(order_line_id)
    product = await load(order_line.matched_product_id)
    steps = await load_ordered_steps(product.id)

    multiplier = Decimal(order_line.quantity) / Decimal(product.base_quantity)

    plan = ExecutionPlan(order_line_id=order_line.id, product_id=product.id, multiplier=multiplier)
    db.add(plan)

    for step in steps:
        if step.step_type == "ingredient":
            computed = round_half_up(step.quantity_canonical * multiplier)
            db.add(ExecutionPlanStep(
                execution_plan=plan, order_index=step.order_index, step_type="ingredient",
                ingredient_name_snapshot=step.ingredient.name,
                measure_type_snapshot=step.ingredient.measure_type,
                quantity_canonical_computed=computed,
            ))
        else:
            db.add(ExecutionPlanStep(
                execution_plan=plan, order_index=step.order_index, step_type="event",
                event_name_snapshot=step.event_template.name,
                event_type_snapshot=step.event_template.event_type,
                event_params_snapshot=step.event_params,
            ))
    await db.commit()
    return plan
```

Снапшот (копирование, а не ссылка на живой `recipe_step`) — чтобы редактирование рецептуры не искажало уже выданный план.

### 14.2 Округление

`round_half_up(x) = floor(x + 0.5)` — целые граммы/мл/секунды.

### 14.3 Advance step

`POST /execution-plans/{id}/advance`:
1. Пометить шаг с `order_index = current_step_index` как `status='done', completed_at=now()`.
2. `current_step_index += 1`.
3. Если это был последний шаг → `status='completed'`, иначе `in_progress`.
4. Возвращает обновлённый план + текущий (следующий) шаг.

Расширяемость на будущее: `event_params_snapshot` уже несёт всё нужное для автоматизации (`timer` → реальный обратный отсчёт с авто-advance; `weight_check` → интеграция с весами; `phrase_confirmation` → голосовое распознавание). Потребуется только добавить `started_at`/`actual_value` в `execution_plan_steps` и WebSocket/поллинг — без изменения остальной модели данных.

---

## 15. API contract (обзор)

| Домен | Эндпоинты |
|---|---|
| Auth | `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/me`, `GET /api/me/permissions` |
| Users | `GET/POST /api/users`, `GET/PATCH/DELETE /api/users/{id}`, `PUT /api/users/{id}/roles` |
| Roles | `GET/POST /api/roles`, `PATCH/DELETE /api/roles/{id}` |
| Permissions | `GET /api/permission-defs`, `GET /api/tabs`, `GET /api/roles/{id}/permissions`, `PUT /api/roles/{id}/permissions` |
| Folders | `GET /api/folders/tree`, `GET /api/folders/{id}/content`, `POST /api/folders`, `PATCH /api/folders/{id}`, `DELETE /api/folders/{id}` |
| Ingredients | `GET/POST /api/folders/{folderId}/ingredients`, `GET/PATCH/DELETE /api/ingredients/{id}`, `GET /api/ingredients/{id}/used-in` |
| Products | `GET/POST /api/folders/{folderId}/products`, `GET/PATCH/DELETE /api/products/{id}`, `GET/POST /api/products/{id}/steps`, `PATCH/DELETE /api/products/{id}/steps/{stepId}`, `PATCH /api/products/{id}/steps/reorder` |
| Events | `GET/POST /api/folders/{folderId}/events`, `GET/PATCH/DELETE /api/events/{id}` |
| Orders | `POST /api/orders/upload`, `GET /api/orders/current`, `PATCH /api/order-lines/{id}/match` |
| Execution | `GET /api/order-lines/{id}/execution-plan` (get-or-create), `POST /api/execution-plans/{id}/advance` |

Все эндпоинты, кроме `/auth/*`, требуют `Authorization: Bearer <access_token>` и проходят `require_permission`.

---

## 16. Ключевые backend endpoints — примеры

### 16.1 `POST /api/auth/login`

```json
{ "email": "admin@karavay.app", "password": "********" }
```
Ответ `200`:
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "id": "6a8e...", "email": "admin@karavay.app", "full_name": "Админ" }
}
```
Refresh-токен уходит в `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax`.

### 16.2 `GET /api/me/permissions`

```json
{
  "tabs": {
    "file_manager": { "view": true, "edit": true },
    "current_order": { "view": true, "edit": false }
  },
  "global": { "order.execute": true, "admin.manage": false },
  "system_role": false
}
```

### 16.3 `GET /api/folders/{id}/content`

```json
{
  "folder": { "id": "f-9", "name": "Хлебобулочные", "parent_id": "f-2", "breadcrumbs": [
    { "id": "f-1", "name": "Цех 1" }, { "id": "f-2", "name": "Производство" }, { "id": "f-9", "name": "Хлебобулочные" }
  ]},
  "permissions": { "view": true, "create": true, "edit": true },
  "subfolders": [ { "id": "f-10", "name": "Ржаные" } ],
  "ingredients": [ { "id": "i-1", "name": "Мука пшеничная", "measure_type": "weight", "is_active": true } ],
  "products": [ { "id": "p-1", "name": "Белый хлеб", "base_quantity": 100 } ],
  "events": [ { "id": "e-1", "name": "Отправить в печь", "event_type": "timer" } ]
}
```

### 16.4 `POST /api/products/{id}/steps` — ingredient step

```json
{
  "step_type": "ingredient",
  "ingredient_id": "i-1",
  "quantity_canonical": 2000,
  "order_index": 0
}
```

### 16.5 `POST /api/products/{id}/steps` — event step

```json
{
  "step_type": "event",
  "event_template_id": "e-1",
  "event_params": { "duration_seconds": 600 },
  "order_index": 2
}
```
Ответ `201`:
```json
{
  "id": "rs-3", "product_id": "p-1", "order_index": 2, "step_type": "event",
  "event_template": { "id": "e-1", "name": "Отправить в печь", "event_type": "timer" },
  "event_params": { "duration_seconds": 600 }
}
```

### 16.6 `POST /api/orders/upload`

`multipart/form-data`: `file=order.xlsx`, `execution_date=2026-07-05`.

```json
{
  "order_id": "o-1",
  "total_lines": 2,
  "matched": 1,
  "unmatched": 1,
  "lines": [
    { "id": "ol-1", "product_name_raw": "белый хлеб", "quantity": 150, "due_time": "08:30", "match_status": "matched", "matched_product_id": "p-1" },
    { "id": "ol-2", "product_name_raw": "батон нарезнйо", "quantity": 80, "due_time": "09:00", "match_status": "unmatched", "matched_product_id": null }
  ]
}
```

### 16.7 `GET /api/order-lines/{id}/execution-plan`

```json
{
  "id": "ep-1", "order_line_id": "ol-1", "product_id": "p-1",
  "multiplier": 1.5, "status": "in_progress", "current_step_index": 1,
  "steps": [
    { "order_index": 0, "step_type": "ingredient", "ingredient_name_snapshot": "Мука пшеничная",
      "measure_type_snapshot": "weight", "quantity_canonical_computed": 3000, "status": "done" },
    { "order_index": 1, "step_type": "ingredient", "ingredient_name_snapshot": "Вода",
      "measure_type_snapshot": "volume", "quantity_canonical_computed": 1500, "status": "pending" },
    { "order_index": 2, "step_type": "event", "event_name_snapshot": "Отправить в печь",
      "event_type_snapshot": "timer", "event_params_snapshot": { "duration_seconds": 600 }, "status": "pending" }
  ]
}
```

### 16.8 `POST /api/execution-plans/{id}/advance`

```json
{ "id": "ep-1", "status": "in_progress", "current_step_index": 2 }
```

---

## 17. React routes и страницы

| Route | Страница | Права |
|---|---|---|
| `/login` | Login | публичный |
| `/` | Dashboard | любой авторизованный |
| `/files` и `/files/:folderId` | FileManager | `tab.view(file_manager)` + `folder.view` |
| `/files/:folderId/ingredients/:configId` | IngredientEditor (модалка) | `folder.edit` |
| `/files/:folderId/products/:configId` | ProductEditor (модалка) | `folder.edit` |
| `/files/:folderId/events/:configId` | EventEditor (модалка) | `folder.edit` |
| `/admin/roles` | RolesPermissions | `admin.manage` |
| `/admin/users` | Users | `admin.manage` |
| `/orders/upload` | UploadOrder | `tab.view(upload_order)` |
| `/orders/current` | CurrentOrder | `tab.view(current_order)` |
| `/orders/current/:orderLineId/execute` | ExecutionView | `order.execute` |

Маршруты оборачиваются `<ProtectedRoute permission="...">`, при отсутствии прав рендерит "нет доступа" (403), без молчаливого редиректа.

---

## 18. UI/UX главных экранов

**Login** — email + пароль, кнопка "Войти", инлайн-ошибка при 401.

**Dashboard** — карточки только тех разделов, куда есть `tab.view`.

**Roles & Permissions** — список ролей слева; справа редактор: (1) чекбоксы по вкладкам (view/edit), (2) дерево папок с чекбоксами (view/create/edit) с индикацией "унаследовано/явно задано" и возможностью вернуться к наследованию, (3) глобальные права.

**Users** — таблица (email, имя, статус, роли), клик открывает панель с мультиселектом ролей и `is_active`.

**File Manager** — слева дерево папок, справа сетка содержимого (сначала подпапки, затем ингредиенты/продукты/события разными иконками). Двойной клик по папке — переход внутрь. Двойной клик по конфигу — открывает редактор. Правый клик — контекстное меню. Drag-and-drop — перемещение с блокировкой при отсутствии `folder.edit` на цели.

**Ingredient Editor** — форма (название, мера измерения, описание, тары — chip-input, активен), ниже — "Используется в продукции" (плоский список, кликабельно).

**Product Editor** — название + базовое количество; секция "Рецептура" — список шагов с drag-handle для порядка, кнопки "Добавить ингредиент"/"Добавить событие".

**Event Editor** — форма (название, описание, тип), явная подсказка: "Параметры (время, вес, фраза) задаются в шаге рецептуры продукции".

**Upload Order** — drag-drop зона `.xlsx` + обязательная "Дата исполнения" → загрузка → сводка + таблица строк с inline-резолвером для unmatched.

**Current Order** — таблица заявки на дату (продукция, количество, время, статус). Клик по matched-строке → ExecutionView.

**Execution View** — карточка текущего шага (крупно количество в составном формате или параметры события), кнопка "Дальше" на всю ширину, трек прогресса по шагам.

---

## 19. Текстовые wireframes

```
LOGIN
+-------------------------------+
|           Karavay              |
|  Email    [____________]       |
|  Пароль   [____________]       |
|           [   Войти   ]        |
+-------------------------------+

FILE MANAGER
+---------------+-----------------------------------------------+
| Цех 1 / Производство / Хлебобулочные                            |
+---------------+-----------------------------------------------+
| > Цех 1       |  [+Папка]                                       |
|  v Производство|  +---------+ +---------+ +---------+            |
|   v Хлебобул.  |  | Ржаные  | | Мука П. | | Белый   |            |
|    > Ржаные    |  | (папка) | |(ингред.)| | хлеб    |            |
|   > Кондитерка |  +---------+ +---------+ |(продукт)|            |
|               |                            +---------+            |
+---------------+-----------------------------------------------+

PRODUCT EDITOR
+-----------------------------------------------------+
| Название: [Белый хлеб]   Базовое кол-во: [100] шт      |
+-----------------------------------------------------+
| Рецептура                [+Ингредиент] [+Событие]       |
| 1. = Мука пшеничная         2 кг 0 г        [edit][x]   |
| 2. = Вода                    1 л 0 мл        [edit][x]   |
| 3. = (timer) Отправить в печь  таймер 10 мин [edit][x]   |
+-----------------------------------------------------+

EXECUTION VIEW
+-----------------------------------------------------+
| Белый хлеб * заявка 150 шт (x1.5)     Шаг 2 из 3         |
| [done] --- [done] --- [ ]                                |
+-----------------------------------------------------+
|                                                       |
|              Вода                                    |
|              1 л 500 мл                               |
|                                                       |
+-----------------------------------------------------+
|                [        Дальше        ]              |
+-----------------------------------------------------+
```

---

## 20. Деплой на Render

- **Postgres** — Render managed Postgres, отдельный сервис (`DATABASE_URL` через `fromDatabase`).
- **Backend** — Docker Web Service: `dockerfilePath: backend/Dockerfile`, health-check `/health`, старт прогоняет `alembic upgrade head` перед `uvicorn`.
- **Frontend** — Static Site: `buildCommand: npm ci && npm run build`, `staticPublishPath: dist`, обязательное rewrite-правило `/* → /index.html` (иначе прямой заход на `/orders/current` даст 404).
- **Env vars**: `DATABASE_URL` (авто), `JWT_SECRET` (`generateValue: true`), `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`, `FRONTEND_ORIGIN`, `INITIAL_ADMIN_EMAIL`/`INITIAL_ADMIN_PASSWORD` (`sync: false`); фронт — `VITE_API_BASE_URL` на этапе сборки.
- Первичный админ — через `scripts/seed_admin.py`, запускаемый один раз после первого деплоя.

---

## 21. Пример `render.yaml`

```yaml
databases:
  - name: karavay-db
    databaseName: karavay
    plan: free
    postgresMajorVersion: 16

services:
  - type: web
    name: karavay-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    plan: free
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: karavay-db
          property: connectionString
      - key: JWT_SECRET
        generateValue: true
      - key: JWT_ACCESS_TTL_MINUTES
        value: "15"
      - key: JWT_REFRESH_TTL_DAYS
        value: "7"
      - key: FRONTEND_ORIGIN
        value: https://karavay-frontend.onrender.com
      - key: INITIAL_ADMIN_EMAIL
        sync: false
      - key: INITIAL_ADMIN_PASSWORD
        sync: false

  - type: web
    name: karavay-frontend
    runtime: static
    rootDir: frontend
    buildCommand: npm ci && npm run build
    staticPublishPath: ./dist
    envVars:
      - key: VITE_API_BASE_URL
        value: https://karavay-backend.onrender.com/api
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

---

## 22. Примеры `.env`

**backend/.env.example**
```
DATABASE_URL=postgresql+asyncpg://karavay:karavay@localhost:5432/karavay
JWT_SECRET=change-me-local-dev
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
FRONTEND_ORIGIN=http://localhost:5173
INITIAL_ADMIN_EMAIL=admin@karavay.app
INITIAL_ADMIN_PASSWORD=change-me-now
```

**frontend/.env.example**
```
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## 23. Roadmap по этапам MVP

| Этап | Содержание | Оценка |
|---|---|---|
| 0. Bootstrap | Скелет backend/frontend, docker-compose с Postgres, render.yaml черновик, ранний деплой | 0.5–1 нед |
| 1. Auth & RBAC core | users/roles/user_roles/permission_defs/app_tabs, PermissionService, login/refresh, страницы Roles&Permissions и Users | 1–1.5 нед |
| 2. Folder manager | folders CRUD/move/rename/delete, materialized_path, enforcement, FileManager UI | 1 нед |
| 3. Ingredient & Event configs | CRUD, inheritance-запрос, "используется в", редакторы | 1 нед |
| 4. Product & recipe steps | products CRUD, recipe_steps CRUD/reorder, unit_conversion, составной ввод, ProductEditor | 1–1.5 нед |
| 5. Orders & execution | Excel-парсер, orders/order_lines, execution_plans (get-or-create+snapshot), advance, UI | 1.5 нед |
| 6. Deploy hardening | финальный render.yaml, логирование, обработка ошибок, seed_admin, smoke-тесты | 0.5–1 нед |

Итого ориентировочно **6.5–8 недель** для одного full-stack инженера.

---

## 24. Риски и узкие места

1. Перемещение поддерева папок — массовый пересчёт `materialized_path` должен быть транзакционным и протестирован на глубоких деревьях.
2. Удаление непустой папки/используемого ингредиента заблокировано на уровне БД — сообщение "что мешает удалить" нужно строить явным запросом.
3. Хрупкость формата Excel (три строки без заголовков) — любое отклонение ломает парсинг; митигируется построчной валидацией.
4. Округление количества при коэффициенте — предсказуемое, но не идеально точное для большого числа ингредиентов; приемлемо для граммов.
5. Render free tier: backend "засыпает" при простое; free Postgres — ограничение соединений, пул SQLAlchemy должен быть небольшим.
6. Отсутствие кэша прав — каждая проверка идёт в БД; кандидат на кэширование при росте масштаба.
7. Снапшот execution plan не подхватывает правку рецепта после создания плана — если нежелательно, нужна ручная регенерация (не предусмотрена в MVP).
8. Один часовой пояс, наивные даты/время — ревизия нужна при мультилокационном производстве.
9. Конкурентное редактирование рецептуры — "последний сохранивший побеждает" при reorder, приемлемо для MVP.

---

## 25. Acceptance criteria для MVP

- [ ] Администратор создаёт роль, настраивает `tab.view/edit` и `folder.view/edit` с наследованием, назначает роль пользователю — этот пользователь видит ровно разрешённые вкладки/папки (проверено в UI и прямым вызовом API без прав → 403).
- [ ] Ингредиент из папки `A` доступен в `A/B/C`, недоступен в соседней ветке `D`.
- [ ] Событие-шаблон подчиняется тому же правилу наследования.
- [ ] Продукт "Белый хлеб" (`base_quantity=100`) с шагами (2 кг муки, 1 л воды, таймер 10 мин) сохраняется и читается в заданном порядке.
- [ ] Составной ввод "3 л 200 мл" даёт `quantity_canonical=3200` и обратно отображается как "3 л 200 мл".
- [ ] Загрузка корректного `.xlsx` с 2 позициями создаёт заявку с двумя строками, верно парсит время `8:30`.
- [ ] Несовпадающее название помечается `unmatched` и решается вручную, не блокируя остальные строки.
- [ ] Открытие matched-позиции на 150 шт при `base_quantity=100` создаёт план с `multiplier=1.5`, шаг "мука 2000 г" показывает `3000 г`.
- [ ] Кнопка "Дальше" продвигает `current_step_index`, финальный шаг переводит план в `completed`.
- [ ] Удаление непустой папки или используемого ингредиента возвращает `409` с понятным сообщением.
- [ ] Backend задеплоен как Docker Web Service на Render с Render Postgres; frontend — Static Site; прямой переход по URL не даёт 404.
- [ ] Все проверки прав дублируются на backend — прямой вызов без прав возвращает `403`.
