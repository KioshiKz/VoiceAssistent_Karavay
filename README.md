# «Каравай» — установка и локальный запуск

Веб-приложение производственного учёта: FastAPI/PostgreSQL на backend, React/Vite на frontend, офлайн-распознавание русской речи через Vosk и опциональный серверный синтез речи через Silero TTS.

Ниже описана установка из чистого клона со всеми зависимостями, моделями и локальными файлами, которые не попадают в Git.

## Системные требования

| Компонент | Версия | Для чего нужен |
|---|---:|---|
| Python x64 | 3.12 | Backend, Vosk и Silero TTS. Эта же версия используется в `backend/Dockerfile` |
| Node.js | 22.12+ или 20.19+ | Frontend на Vite 8 |
| npm | поставляется с Node.js | Установка frontend-зависимостей |
| PostgreSQL | 16+ | Основная БД; `docker-compose.yml` использует PostgreSQL 16 |
| Docker Desktop | актуальная версия | Рекомендуемый способ запустить только PostgreSQL локально |
| Git | актуальная версия | Клонирование проекта |

Windows 10/11 и PowerShell — основной локальный сценарий. На Linux/macOS команды те же по смыслу, но виртуальное окружение активируется командой `source backend/.venv/bin/activate`, а копирование выполняется через `cp`.

Для микрофона Vosk использует `sounddevice`. На Windows дополнительная системная библиотека обычно не нужна. На Debian/Ubuntu при ошибке PortAudio установите её:

```bash
sudo apt-get update
sudo apt-get install -y libportaudio2
```

## 1. Клонирование

```powershell
git clone https://github.com/KioshiKz/VoiceAssistent_Karavay.git
cd VoiceAssistent_Karavay
```

Все дальнейшие команды, если не указано иное, выполняются из корня репозитория.

## 2. Backend и все Python-зависимости

Создайте изолированное окружение именно в `backend/.venv` — этот путь ожидают `run_server.py` и `start.bat`:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-tts.txt
backend\.venv\Scripts\python.exe -m pip install -r backend\model\text_to_speach\requirements.txt
```

Что устанавливается:

- `backend/requirements.txt` — FastAPI, Uvicorn, SQLAlchemy, asyncpg, Alembic, JWT, Excel, serial-порт весов и остальные обязательные пакеты;
- `backend/requirements-tts.txt` — предыдущий файл плюс CPU-сборки PyTorch и NumPy для Silero TTS;
- `backend/model/text_to_speach/requirements.txt` — Vosk и `sounddevice` для распознавания речи с микрофона.

Если серверный Silero TTS не нужен, достаточно `backend/requirements.txt`: приложение сможет использовать голос, доступный в браузере. Для полной установки используйте команды выше.

## 3. Frontend

`npm ci` устанавливает точные версии из `frontend/package-lock.json` и создаёт игнорируемый каталог `frontend/node_modules`:

```powershell
Set-Location frontend
npm ci
Set-Location ..
```

## 4. Переменные окружения

Создайте локальные конфиги из отслеживаемых шаблонов:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
```

Минимальный `backend/.env` для PostgreSQL из Docker Compose:

```dotenv
DATABASE_URL=postgresql+asyncpg://karavay:karavay@localhost:5432/karavay
JWT_SECRET=replace-with-a-long-random-string
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
FRONTEND_ORIGIN=http://localhost:5173
INITIAL_ADMIN_EMAIL=admin@karavay.app
INITIAL_ADMIN_PASSWORD=replace-with-a-strong-password
SCALE_PORT=auto
SCALE_BAUDRATE=9600
```

Сгенерировать случайный `JWT_SECRET` в PowerShell можно так:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

`frontend/.env.local`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api
```

Не коммитьте `.env` и `.env.local`: в них находятся пароли и секреты.

## 5. PostgreSQL

### Рекомендуемый вариант: Docker

Запустите только БД — backend и frontend будут работать на хосте:

```powershell
docker compose up -d db
docker compose ps
```

Контейнер публикует PostgreSQL на `localhost:5432`, поэтому подходит стандартный `backend/.env.example`. Данные сохраняются в именованном Docker volume `postgres-data`.

Остановить БД без удаления данных:

```powershell
docker compose stop db
```

Команда `docker compose down -v` удаляет БД без возможности восстановления; используйте её только для осознанного полного сброса.

### Альтернатива: локальный PostgreSQL 18 для `run_server.py`

`run_server.py` и `start.bat` рассчитаны на Windows, `C:\Program Files\PostgreSQL\18\bin`, порт `5433` и уже созданный кластер `.devdata/pgdata`. Один раз инициализируйте его:

```powershell
New-Item -ItemType Directory -Force .devdata | Out-Null
& "C:\Program Files\PostgreSQL\18\bin\initdb.exe" `
  -D "$PWD\.devdata\pgdata" -U postgres -A scram-sha-256 --pwprompt

& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" `
  -D "$PWD\.devdata\pgdata" -l "$PWD\.devdata\pg.log" `
  -o "-p 5433 -h 127.0.0.1" start

& "C:\Program Files\PostgreSQL\18\bin\createuser.exe" `
  -h 127.0.0.1 -p 5433 -U postgres --login --pwprompt karavay

& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" `
  -h 127.0.0.1 -p 5433 -U postgres --owner=karavay karavay
```

В `backend/.env` укажите пароль, введённый для роли `karavay`, и порт `5433`:

```dotenv
DATABASE_URL=postgresql+asyncpg://karavay:<ПАРОЛЬ>@127.0.0.1:5433/karavay
```

Если PostgreSQL установлен в другой каталог или другой версии, измените константу `PG_CTL` в `run_server.py` и `PGBIN` в `start.bat`.

## 6. Голосовые модели

### Vosk: распознавание речи

Малая русская модель `backend/model/text_to_speach/vosk-model-small-ru-0.22` уже находится в репозитории. После `git clone` отдельно скачивать её не нужно. Она загружается по умолчанию и лучше подходит текущему коду с динамической грамматикой команд.

Большая модель `vosk-model-ru-0.42` опциональна: архив занимает около 1,8 ГБ, распакованная модель — примерно 3,44 GiB, а для работы может потребоваться значительно больше оперативной памяти. Скачать её можно с официального сайта Vosk:

```powershell
$archive = Join-Path $env:TEMP "vosk-model-ru-0.42.zip"
curl.exe -L "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip" -o $archive
Expand-Archive -LiteralPath $archive `
  -DestinationPath backend\model\text_to_speach -Force
```

Ожидаемый результат:

```text
backend/model/text_to_speach/vosk-model-ru-0.42/
├── am/
├── conf/
├── graph/
├── ivector/
└── ...
```

Код всегда предпочитает малую модель, если путь не указан явно. Чтобы запустить большую модель в текущем сеансе PowerShell:

```powershell
$env:VOSK_MODEL_PATH = (Resolve-Path `
  "backend\model\text_to_speach\vosk-model-ru-0.42").Path
```

Чтобы вернуться к модели из репозитория:

```powershell
Remove-Item Env:VOSK_MODEL_PATH -ErrorAction SilentlyContinue
```

Важно: большие Vosk-модели рассчитаны на серверное распознавание и могут не поддерживать динамическое ограничение словаря так же, как малые. Если `KaldiRecognizer` не создаётся с грамматикой проекта, используйте включённую `vosk-model-small-ru-0.22`.

Полный каталог официальных моделей: <https://alphacephei.com/vosk/models>.

### Silero TTS: синтез речи

Вес модели не хранится в Git. После установки `backend/requirements-tts.txt` скачайте его заранее:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\download_tts_model.py
```

Будет создан файл:

```text
backend/.models/silero_tts/v4_ru.pt
```

Его размер — около 40 МБ. Источник модели задан в `backend/app/services/tts_service.py`: `https://models.silero.ai/models/tts/ru/v4_ru.pt`. Если предварительное скачивание пропустить, backend попробует получить файл при первом запуске/первом запросе синтеза.

## 7. Миграции и первый администратор

При запущенной БД выполните:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_admin
Set-Location ..
```

Вход выполняется через `INITIAL_ADMIN_EMAIL` и `INITIAL_ADMIN_PASSWORD` из `backend/.env`. Скрипт `seed_admin` идемпотентен, но не меняет пароль существующего пользователя. Для принудительного обновления пароля:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m scripts.reset_admin_password
Set-Location ..
```

## 8. Запуск

### С Docker PostgreSQL

Терминал 1 — backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app `
  --host 127.0.0.1 --port 8000 --reload
```

Терминал 2 — frontend:

```powershell
Set-Location frontend
npm run dev
```

Терминал 3 — офлайн-распознавание с микрофона:

```powershell
backend\.venv\Scripts\python.exe `
  backend\model\text_to_speach\test.py
```

Откройте <http://127.0.0.1:5173>. API доступен на <http://127.0.0.1:8000/api>, health-check — <http://127.0.0.1:8000/health>.

### Единая команда на Windows

После настройки нативного PostgreSQL в `.devdata`:

```powershell
python run_server.py --voice
```

Скрипт запускает PostgreSQL на `5433`, применяет миграции, поднимает backend и frontend, затем запускает Vosk. Без распознавания речи используйте `python run_server.py`. `start.bat` запускает БД, миграции, backend и frontend, но не Vosk.

## 9. Проверка установки

```powershell
backend\.venv\Scripts\python.exe -m pip check

Set-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Set-Location ..\frontend
npm run lint
npm run build
Set-Location ..
```

Проверить наличие локальных моделей:

```powershell
Test-Path backend\model\text_to_speach\vosk-model-small-ru-0.22\am\final.mdl
Test-Path backend\.models\silero_tts\v4_ru.pt
```

Обе команды должны вернуть `True` для полной установки. Большая Vosk-модель вместо малой не обязательна.

## Что именно исключено из Git

| Путь или шаблон | Как появляется | Нужно восстанавливать после клонирования |
|---|---|---|
| `backend/.venv/`, `.venv/`, `venv/` | `python -m venv` и `pip install` | Да, создать окружение и поставить requirements |
| `frontend/node_modules/` | `npm ci` | Да |
| `backend/.env`, `frontend/.env.local`, `.env`, `*.env.local`, `*.local` | Копирование `.env.example` и ручная настройка | Да, нужные приложению env-файлы |
| `backend/.models/` | `backend/scripts/download_tts_model.py` | Да для серверного Silero TTS |
| `backend/model/text_to_speach/vosk-model-ru-0.42/` | Ручная загрузка и распаковка | Только если нужна большая Vosk-модель |
| `.devdata/` | Нативный локальный кластер PostgreSQL | Только для `run_server.py`/`start.bat`; не нужен при Docker |
| `postgres-data/` | Зарезервировано для локальных файлов БД | Обычно нет: Compose использует именованный Docker volume вне репозитория |
| `frontend/dist/`, `frontend/dist-ssr/`, `.vite/` | `npm run build` и кэш Vite | Нет, генерируются автоматически |
| `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/` | Python, pytest и упаковочные инструменты | Нет, это кэши/метаданные |
| `logs/`, `*.log`, `npm-debug.log*`, `yarn-debug.log*`, `yarn-error.log*`, `pnpm-debug.log*`, `lerna-debug.log*` | Инструменты разработки | Нет |
| `.claude/settings.local.json` | Персональные настройки локального помощника | Нет |
| `.vscode/*` кроме `extensions.json`, `.idea/`, `*.suo`, `*.ntvs*`, `*.njsproj`, `*.sln`, `*.sw?` | IDE/редактор | Нет |
| `.DS_Store`, `Thumbs.db` | macOS/Windows | Нет |

Ничего из кэшей, сборок, локальных БД, моделей из игнорируемых каталогов и файлов с секретами добавлять в Git не нужно.

## Весы

Backend поддерживает MERTECH M-ER 326 через USB–RS232 (CAS-M, 9600 baud, 8N1). По умолчанию `SCALE_PORT=auto`; COM1 автоматически не выбирается. Инструкции по драйверу CH340, диагностике порта и протоколу находятся в [`docs/scales.md`](docs/scales.md).

