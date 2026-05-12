# Telegram Parser Bot

Production-oriented MVP Telegram-бота для парсинга постов из каналов с чистой архитектурой, `aiogram 3`, `Telethon`, `SQLite`, `SQLAlchemy 2` и `Alembic`.

## Архитектура

Проект разделен на 4 слоя:

- `app/domain`: сущности, ошибки и порты.
- `app/application`: use cases, DTO, access policy и прикладные сервисы.
- `app/infrastructure`: SQLAlchemy, конфиг, логирование, Telethon gateway, DI container.
- `app/presentation`: aiogram handlers, callbacks, клавиатуры, FSM states и тексты.

Такое разделение оставляет бизнес-логику вне Telegram handlers и позволяет отдельно менять UI, БД и реализацию Telegram client.

## Что умеет MVP

- owner-only доступ через `BOT_OWNER_IDS`
- добавление каналов по username или `t.me` ссылке
- создание коллекций и связывание каналов с коллекциями
- запуск парсинга по одному каналу, по коллекции или по всем каналам
- выбор лимита и периода через inline-кнопки перед запуском
- отправка фото и видео вместе с постом, если они есть
- ИИ-обработка поста по кнопке: перевод на русский, удаление водяных знаков и перефразирование
- публикация обработанного поста в твой канал напрямую, без пометки пересланного сообщения
- хранение уже обработанных постов и защита от дублей
- конвертация Telegram entities в `parse_mode=HTML`
- Docker и миграции Alembic
- базовые тесты

## Важное ограничение Telethon

Для чтения постов из каналов используется не Bot API, а пользовательский Telegram-клиент через `Telethon`.

Это означает:

- для публичных каналов обычно достаточно валидной Telethon session
- для приватных каналов session должна принадлежать аккаунту, который уже имеет доступ к этим каналам
- самый удобный вариант: один раз создать локальный session-файл и дальше не логиниться каждый запуск
- если видишь ошибку `AuthKeyUnregisteredError`, значит текущая `TELETHON_SESSION_STRING` пустая, протухшая или неавторизованная

В production это корректная схема, потому что Bot API сам по себе не дает надежный доступ к истории произвольных каналов.

## Структура проекта

```text
app/
  application/
  domain/
  infrastructure/
    db/
    telegram/
  presentation/
alembic/
  versions/
tests/
Dockerfile
docker-compose.yml
pyproject.toml
README.md
```

## Переменные окружения

Скопируй шаблон:

```bash
cp .env.example .env
```

Ключевые переменные:

- `BOT_TOKEN`: токен Telegram-бота
- `BOT_OWNER_IDS`: список разрешенных Telegram user id через запятую
- `DATABASE_URL`: строка подключения SQLAlchemy async, по умолчанию SQLite файл
- `TELEGRAM_API_ID`: api_id от Telegram
- `TELEGRAM_API_HASH`: api_hash от Telegram
- `TELETHON_SESSION_STRING`: строка пользовательской Telethon session, если хочешь хранить именно строкой
- `TELETHON_SESSION_FILE`: путь к локальному session-файлу, это основной и самый удобный вариант
- `OPENROUTER_API_KEY`: API ключ OpenRouter для ИИ-обработки постов
- `OPENROUTER_MODEL`: модель OpenRouter, например `openai/gpt-oss-120b:free`
- `OPENROUTER_BASE_URL`: base URL OpenRouter API
- `PUBLISH_CHANNEL_ID`: username или id канала, куда бот будет публиковать готовый пост напрямую

## Локальный запуск

1. Установить зависимости:

```bash
pip install -e .[dev]
```

2. Применить миграции:

```bash
alembic upgrade head
```

3. Один раз авторизовать Telethon session:

```bash
python -m app.scripts.generate_telethon_session
```

4. Запустить бота:

```bash
python -m app.main
```

## Запуск через Docker Compose

```bash
docker compose up --build
```

## Тесты

```bash
pytest
```

## Перед публикацией на GitHub

В репозиторий нельзя коммитить локальные секреты и runtime-данные:

- `.env`
- Telethon session-файлы (`*.session`)
- локальную SQLite базу (`data/*.db`)
- скачанные медиа (`data/media/`)
- Python-кэши и build artifacts

Для публикации используй `.env.example` как безопасный шаблон настроек. Если реальные ключи уже когда-либо попадали в git history, перевыпусти их перед открытой публикацией.

## Дальнейшее развитие

- scheduler для автопарсинга
- фильтры по ключевым словам
- сохранение и отправка медиа
- автопостинг в целевой канал
- более гибкие сценарии ролей и многопользовательский режим

## Юридические и технические замечания

- соблюдай правила Telegram и права на контент
- не используй чужие приватные каналы без разрешения
- учитывай `FloodWait` и лимиты Telegram при массовом парсинге
