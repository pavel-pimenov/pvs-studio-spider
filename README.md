# PVS-Studio Spider

Автоматический «паук» для статического анализа открытых C/C++ проектов с помощью
[PVS-Studio](https://pvs-studio.com/). Всё работает в Docker:

1. находит (или берёт из конфига) открытые проекты на C++;
2. клонирует их исходники;
3. собирает проект через CMake и получает `compile_commands.json`;
4. запускает `pvs-studio-analyzer`;
5. конвертирует отчёт в интерактивный HTML (`plog-converter -t fullhtml`);
6. сохраняет отчёты локально и поднимает HTTP-сервер;
7. формирует ссылки на отчёты, которые можно отправить разработчику проекта.

## Как это работает

```
проекты.yaml ──► spider (Docker) ──► /data/src    клонированные репозитории
                 clone ─ build ─ analyze          /data/work  сборки (compile_commands.json)
                                   │              /data/reports  .plog, .json, fullhtml/, index.html, links.txt
                                   ▼
                    report-server (Docker) ──► http://localhost:8000
```

Оба сервиса делят каталог `./data` на хосте. Отчёты лежат локально и одновременно
доступны по HTTP, поэтому ссылку из `data/reports/links.txt` можно отправить
поддерживающему проект разработчику — в отчёте уже есть код, файлы и описания
проблем.

## Быстрый старт

### 1. Получите лицензию PVS-Studio

Для open-source проектов PVS-Studio бесплатен — оформите заявку:
https://pvs-studio.com/en/order/open-source-license/
После одобрения придут логин и ключ. Если у вас готовый файл лицензии
(`*.lic`) — тоже подойдёт.

### 2. Настройте окружение

```bash
cp .env.example .env
# впишите PVS_USERNAME / PVS_KEY (или PVS_STUDIO_LICENSE=путь/к/файлу.lic)
```

### 3. Запустите анализ

```bash
docker compose up --build spider     # один раз: собрать образ и провести анализ
```

Или только анализ без сборки образа:
```bash
docker compose run --rm spider analyze
```

### 4. Смотрите отчёты

```bash
docker compose up -d report-server   # поднимает сервер на :8000
```

- Landing-страница со сводкой: http://localhost:8000/
- Интерактивный отчёт по проекту: http://localhost:8000/<проект>/
- Готовые ссылки для рассылки: `data/reports/links.txt`

## Команды

| Команда | Что делает |
| --- | --- |
| `analyze` | клонирует, собирает и анализирует все проекты из конфига |
| `serve` | раздаёт HTML-отчёты по HTTP |
| `discover` | ищет популярные open-source C/C++ репозитории через GitHub API |
| `list` | показывает проекты из конфига |

Примеры запуска без Docker (нужны `python3`, зависимости из `requirements.txt`,
`pvs-studio-analyzer`, `plog-converter`, `cmake`, `git`):

```bash
python3 -m app.cli list
python3 -m app.cli analyze
python3 -m app.cli serve --port 8080
python3 -m app.cli discover --top 5 --output candidates.json
```

## Конфигурация

Проекты и параметры задаются в `projects.yaml`:

```yaml
jobs: 4                                  # параллельность сборки и анализа
convert_groups: "GA:1,2,3"               # какие диагностики оставлять в отчёте
base_url: "http://localhost:8000"        # base для ссылок в links.txt

projects:
  - name: fmt                            # имя = имя каталога и отчёта
    repo: https://github.com/fmtlib/fmt.git
    ref: main                            # ветка / тег / коммит
    description: "Modern formatting library for C++"
    cmake_options:                       # дополнительные ключи CMake
      - -DFMT_DOC=OFF
    enabled: true
```

В конфиге по умолчанию — пять проверенных проектов: **fmt**, **spdlog**,
**benchmark**, **libzmq**, **Catch2**.

### Как работает сборка и анализ

Для каждого проекта Spider делает примерно следующее:

```bash
git clone --depth 1 --branch <ref> <repo> /data/src/<name>

cmake -S <src> -B <build> -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=OFF <cmake_options...>
cmake --build <build>

pvs-studio-analyzer analyze -f <build>/compile_commands.json -o report.plog -j<jobs>
plog-converter -a GA:1,2,3 -t fullhtml -o <reports>/<name> report.plog
plog-converter -a GA:1,2,3 -t json     -o <reports>/<name>.json report.plog
```

Используется режим JSON Compilation Database, поэтому контейнеру не нужен
`ptrace`/`strace` (в отличие от режима трассировки сборки).

## Отправка ссылки разработчику

1. Поднимите сервер так, чтобы он был доступен снаружи (порт из `SPIDER_PORT`,
   при необходимости проброс через reverse-proxy) либо зальте каталог
   `data/reports` на любой статический хостинг.
2. Возьмите ссылку из `data/reports/links.txt`:
   ```
   fmt  http://localhost:8000/fmt/
   ```
3. Пришлите разработчику ссылку и, при желании, готовый текст. Отчёт самодостаточен:
   это папка `fullhtml`, в которой есть и код, и описания предупреждений.

> Совет: следуйте правилам лицензии PVS-Studio — для бесплатной open-source
> лицензии упомяните в коммитах/PR, что ошибки найдены с помощью PVS-Studio.

## Поиск новых проектов

```bash
docker compose run --rm spider discover --top 10 --output candidates.json
cat candidates.json     # или откройте на хосте
```

Команда ищет на GitHub репозитории `language:C++` с сортировкой по звёздам
(токен `GITHUB_TOKEN` в `.env` поднимет лимиты API). Затем подходящие строки
можно вставить в `projects.yaml` — поля `name`, `repo`, `ref`, `description`.

## Структура репозитория

```
├── Dockerfile            # образ с Ubuntu 24.04 + PVS-Studio + toolchain
├── docker-compose.yml    # сервисы spider (анализ) и report-server (раздача)
├── projects.yaml         # список проектов и параметров анализа
├── .env.example          # шаблон переменных окружения (лицензия и пр.)
├── requirements.txt      # Python-зависимости (requests, PyYAML, Jinja2)
└── app/
    ├── cli.py            # точка входа: analyze / serve / discover / list
    ├── config.py         # загрузка projects.yaml
    ├── clone.py          # git clone / update
    ├── analyze.py        # CMake-сборка + pvs-studio-analyzer + лицензия
    ├── report.py         # конвертация в HTML/JSON, index.html, links.txt
    ├── discover.py       # GitHub API поиск проектов
    ├── server.py         # HTTP-раздача отчётов
    └── templates/        # шаблон landing-страницы (Jinja2)
```

## Устранение проблем

- **`No compilation units found`** — проект не собрался или `compile_commands.json`
  пуст. Смотрите лог сборки (`--verbose`). Убедитесь, что проект собирается на
  Ubuntu 24.04 и не требует дополнительных системных пакетов (в этом случае
  добавьте их в `Dockerfile`).
- **`pvs-studio-analyzer` не находит лицензию** — проверьте `PVS_USERNAME`/`PVS_KEY`
  в `.env`. Если используется файл лицензии, укажите `PVS_STUDIO_LICENSE`.
- **Нет `ptrace`** — нам он не нужен (режим compile_commands.json), это нормально.
- **Медленный первый запуск** — клонируются и собираются 5 проектов; последующие
  запуски используют `git pull` и пересобирают только изменённое.

## Ограничения

- PVS-Studio — проприетарный анализатор; для корректного анализа нужна лицензия.
- Spider ориентирован на CMake-проекты. Для прочих сборщиков потребуется доработка
  (генерация `compile_commands.json` через `bear` уже предусмотрена как fallback).
- Контейнер собирает проекты «как есть»; проекты с тяжёлыми внешними зависимостями
  могут требовать правки `Dockerfile`.
