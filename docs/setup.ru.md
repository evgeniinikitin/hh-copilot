# HH Copilot

Локальный помощник для избранных вакансий HeadHunter. Вы ставите ❤️ в HH на телефоне
или Mac, а расширение при следующем открытии hh.ru синхронизирует текущее избранное.
Backend получает карточки через публичный API HH, локальный Codex CLI оценивает совпадение
с профилем и пишет персональное сопроводительное, после чего результат приходит в Telegram.

Система не использует applicant OAuth, не хранит пароль или cookies HH, не требует отдельного
OpenAI API key и не отправляет отклики работодателю.

## Что понадобится

- macOS;
- Python 3.12–3.14;
- Google Chrome;
- установленный и авторизованный Codex CLI (`codex --version`);
- Telegram bot token и chat ID.

## 1. Установка backend

В Terminal откройте папку проекта и выполните:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

Откройте `.env` и заполните:

```env
TELEGRAM_BOT_TOKEN=123456:your-token
TELEGRAM_CHAT_ID=123456789
HH_USER_AGENT=HH-Copilot/0.1 (your-real-email@example.org)
```

HH требует реальный контактный email в `User-Agent`; замените пример своим адресом. Остальные
настройки уже имеют безопасные значения. Backend по умолчанию слушает только `127.0.0.1:8765`.

Скопируйте `data/candidate_profile.example.md` в `data/candidate_profile.md`. Перед первым анализом проверьте и
отредактируйте его: Codex имеет право использовать только факты из этого файла.

## 2. Проверка и запуск

```bash
source .venv/bin/activate
python -m app.main doctor
python -m app.main run
```

Health check: [http://127.0.0.1:8765/health](http://127.0.0.1:8765/health).

Полезные ручные проверки:

```bash
python scripts/test_codex.py
python scripts/test_telegram.py
python scripts/test_backend.py
python scripts/test_hh_public.py
```

В последнюю команду при желании можно передать ID конкретной активной вакансии.

## 3. Telegram bot

1. Откройте `@BotFather` в Telegram и создайте бота командой `/newbot`.
2. Скопируйте token в `TELEGRAM_BOT_TOKEN`.
3. Напишите созданному боту любое сообщение.
4. Получите свой `chat_id` через `https://api.telegram.org/bot<TOKEN>/getUpdates` и добавьте его
   в `TELEGRAM_CHAT_ID`.
5. Запустите `python scripts/test_telegram.py`.

Не публикуйте `.env`: файл исключён из Git.

## 4. Установка Chrome Extension

1. Откройте `chrome://extensions`.
2. Включите **Developer mode**.
3. Нажмите **Load unpacked**.
4. Выберите папку `extension` внутри проекта.
5. Закрепите HH Copilot на панели Chrome.

Расширение работает только на `hh.ru` и обращается только к HH и локальному backend.

## Первый запуск и mobile catch-up

Первая успешная полная синхронизация создаёт baseline: все уже существующие вакансии
сохраняются локально, но не отправляются в Codex и Telegram. Это защищает от обработки сотен
старых вакансий после установки.

Если нужны старые вакансии, в popup нажмите **Обработать последние 5** или **Последние 10**.

После baseline сценарий такой:

1. Добавьте вакансии в избранное HH на телефоне, даже когда Mac выключен.
2. Позже включите Mac и откройте любую страницу hh.ru в Chrome.
3. Расширение найдёт страницу избранного в авторизованной сессии, сравнит IDs с SQLite и
   поставит только новые вакансии в очередь.
4. Одновременно выполняется не более двух анализов. Результаты приходят отдельными сообщениями.

Если authenticated HTML fetch HH не возвращает карточки, расширение открывает страницу
избранного в неактивной вкладке и читает уже отрисованный DOM. Это основной fallback для
изменений клиентского рендеринга HH.

## Автозапуск macOS

После успешного ручного запуска:

```bash
chmod +x scripts/install_launchd.sh
./scripts/install_launchd.sh
```

Скрипт создаёт `~/Library/LaunchAgents/com.hhcopilot.backend.plist`, запускает сервис и проверяет
`/health`. Логи находятся в `runtime/logs/`.

## CLI

```bash
python -m app.main analyze 123456789
python -m app.main analyze-url 'https://hh.ru/vacancy/123456789'
python -m app.main process-baseline --limit 5
```

## Проверка качества

```bash
ruff check .
mypy app
pytest
```

## Как устроена надёжность

- `hh_vacancy_id` уникален: instant mode и sync не создадут второй анализ.
- Первый full sync отмечается отдельным флагом в SQLite, даже если раньше был instant event.
- `queued` продолжает работу после рестарта.
- Зависший `processing` и прерванный `fetched` возвращаются в очередь с ограничением retries.
- Если Codex завершился, а Telegram недоступен, сохраняется `analyzed`; Codex повторно не запускается.
- За один sync автоматически ставятся в очередь максимум 30 новых вакансий; остальные остаются
  в статусе `detected` и видны в локальной базе.

## Troubleshooting

- **Backend offline в popup:** запустите `python -m app.main run`, затем нажмите
  «Синхронизировать».
- **Не найдены вакансии с телефона:** откройте страницу избранного HH и нажмите sync вручную.
  Убедитесь, что Chrome авторизован в том же аккаунте.
- **Codex CLI not found:** проверьте `codex --version` в том же Terminal; при необходимости укажите
  абсолютный путь в `CODEX_BINARY`.
- **Telegram не приходит:** запустите `python scripts/test_telegram.py`; проверьте, что вы сначала
  написали боту.
- **HH 400:** задайте корректный `HH_USER_AGENT` с названием приложения и контактом.
- **Диагностика:** `python -m app.main doctor` и `runtime/logs/hh_copilot.log`.

## Privacy

Cookies и пароль HH остаются внутри Chrome. Расширение передаёт backend только vacancy IDs.
Backend хранит локально карточку вакансии, анализ и статусы. Codex запускается в отдельной
временной папке с read-only sandbox и получает только профиль, нормализованную вакансию и
инструкции. Telegram token не включается в prompt и не логируется.
