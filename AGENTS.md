# AGENTS.md

Руководство для AI-агентов и разработчиков, работающих с этим репозиторием.

## Что это

Docker-проект, который автоматизирует статический анализ открытых C/C++ проектов
с помощью PVS-Studio: клонирует репозитории, собирает их CMake-ом, запускает
`pvs-studio-analyzer`, конвертирует отчёт в HTML и раздаёт по HTTP.

## Язык и окружение

- Оркестрация — **Python 3** (пакет `app/`), без стороннего фреймворка.
- Зависимости: `requests`, `PyYAML`, `Jinja2` (`requirements.txt`).
- Основной runtime — Docker (`Dockerfile` на базе `ubuntu:26.04`). PVS-Studio
  ставится из официального репозитория viva64.
- Исходники, сборки и отчёты живут в каталоге `./data` (bind-mount в `/data`).

## Как запускать

```bash
# анализ всех проектов из projects.yaml
docker compose run --rm spider analyze

# раздача отчётов
docker compose up -d report-server

# без Docker (нужны инструменты: cmake, git, pvs-studio-analyzer, plog-converter)
python3 -m app.cli analyze --verbose
```

## Структура

- `app/cli.py` — точка входа (`analyze` / `serve` / `discover` / `list`).
- `app/config.py` — загрузка `projects.yaml` в dataclass'ы `Config`/`Project`.
- `app/clone.py` — `git clone`/`pull`.
- `app/analyze.py` — настройка лицензии, CMake-сборка, запуск анализа.
- `app/state.py` — хранение проанализированных ревизий в `revisions.txt`
  (slug → commit), чтобы не переанализировать неизменённые проекты.
- `app/report.py` — конвертация `.plog` → `fullhtml`/`json`, генерация
  `index.html` (портал) и `links.txt`.
- `app/status.py` — прогресс анализа: пишет `reports_dir/status.json`,
  который портал опрашивает каждые 3 секунды.
- `reports_dir/metrics.json` — метрики на проект (диск/CPU/время), показывает
  портал; `analyze` также удаляет артефакты проектов, которых больше нет в
  `projects.yaml` (прунинг осиротевших отчётов/клонов).
- `app/discover.py` — поиск проектов через GitHub API.
- `app/server.py` — `http.server` для раздачи отчётов.
- `app/templates/index.html.j2` — Jinja2-шаблон landing-страницы.
- `revisions.txt` — коммитится в git; проект с той же HEAD-ревнзией,
  что и в файле, пропускается (`analyze --force` для полного прогона,
  `--only SLUG ...` для выборочного анализа).

## Конвенции

- Без комментариев в коде, кроме docstring'ов в начале функций/модулей (когда они
  уместны).
- Типизация через `from __future__ import annotations` и аннотации `Path`/`list`/`dict`.
- Один проект = один элемент в `projects.yaml`; `name` обязателен и должен быть
  валидным именем каталога (используется и как slug).
- Все внешние команды запускаются через `app.util.run()`, логирующий команду и вывод.
- Не коммитьте секреты (лицензию PVS-Studio, `GITHUB_TOKEN`) — только `.env.example`.
- `data/` и `candidates.json` игнорируются git-ом.

## Проверка изменений

1. Линтера/форматтера в репозитории нет; придерживайтесь стиля стандартной библиотеки.
2. Smoke-тест без Docker:
   ```bash
   python3 -c "from app.cli import build_parser; build_parser().parse_args(['list'])"
   python3 -m app.cli list
   python3 -m app.cli --help
   python3 -m py_compile app/*.py
   ```
3. Проверка конфига: `python3 -m app.cli list` должен вывести проекты из
   `projects.yaml`.
4. Юнит-тест парсера отчётов (не требует PVS-Studio):
   ```bash
   python3 -c "
   from pathlib import Path
   from app.report import parse_json
   p = Path('/tmp/r.json'); p.write_text('[{\"Code\":\"V501\",\"Level\":1}]')
   assert parse_json(p)['total'] == 1
   print('ok')
   "
   ```

## Типичные доработки

- **Новый проект** — добавьте запись в `projects.yaml`; для не-CMake сборщиков
  предусмотрен fallback через `bear` в `app/analyze.py`.
- **Новые системные зависимости для анализа** — добавляйте в `Dockerfile`
  (один слой `apt-get install`), чтобы не раздувать образ слоями.
- **Смена формата отчёта** — редактируйте `report_mod.convert` (например,
  `-t html` для простого одностраничного отчёта вместо `fullhtml`).
- **Смена порога поиска проектов** — флаги `discover --top/--min-stars`.
