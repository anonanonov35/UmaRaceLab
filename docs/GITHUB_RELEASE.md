# Публикация Uma Race Lab на GitHub

## Готовые файлы

- `UmaRaceLab-0.4.1-source.zip` — исходники для нового репозитория, включая Rust-исходники WASM, лицензии, тесты и GitHub Actions. Без `.git`, личной истории, билдов пользователя, файлов игры и исследовательских папок.
- `UmaRaceLab-0.4.1-windows-x64.zip` — распаковываемая Windows x64 сборка. Содержит Python/Tk, Node.js и библиотеки чтения ресурсов; отдельные Python/Node не нужны.
- `SHA256SUMS.txt` — контрольные суммы обоих архивов.

Игру нужно установить отдельно и загрузить её ресурсы. Сборка читает собственную установку пользователя. База, игровые ассеты и извлечённые трассы не распространяются.

## Создать репозиторий

1. На GitHub нажмите **New repository**, задайте имя, например `uma-race-lab`, и выберите видимость. Оставьте автоматическое создание README и лицензии выключенным: они уже есть в исходниках.
2. Распакуйте **source.zip**. Загрузите содержимое его внутренней папки, включая `.github`, `.gitignore` и `.gitattributes`, через **uploading an existing file** либо GitHub Desktop. Не загружайте Windows-архив в дерево исходников.
3. Альтернативно выполните в распакованной папке команды, подставив свой URL:

```powershell
git init -b main
git add .
git commit -m "Initial release"
git remote add origin https://github.com/YOUR_NAME/uma-race-lab.git
git push -u origin main
```

Адрес и аккаунт не зашиты в проект. Подготовка архивов не создаёт репозиторий и не загружает файлы в сеть.

## GitHub Actions и Release

Вкладка **Actions → Windows build and tests** запускает проверки и сборку на Windows при push/PR, а также вручную через **Run workflow**. Результат находится в артефакте `UmaRaceLab-windows-release-candidate`. Автоматической публикации Release нет.

Для выпуска откройте **Releases → Draft a new release**, создайте тег `v0.4.1`, приложите Windows-архив, соответствующий архив исходников и `SHA256SUMS.txt`, затем опубликуйте. GPL-исходники включённого движка находятся в source.zip; распространяйте его вместе с бинарной сборкой.

Краткое описание релиза: «Uma Race Lab 0.4.1 — неофициальный локальный симулятор гонок Umamusume Global для Windows. RU/EN, светлая/тёмная тема, варианты ум и закреплённые уникальные навыки, полная таблица пригодностей и две схемы трассы. Игра требуется отдельно. Точное совпадение нативной физики ещё не подтверждено».

## Собрать самостоятельно

Windows 10/11 x64, Python **3.12 x64 с Tk**, Git, доступ к официальным серверам зависимостей при подготовке:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/prepare_release_deps.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/check_release.py
.\.venv\Scripts\python.exe tools/build_windows.py
```

Скрипты собирают файлы в `build/` и `dist/`. Git должен содержать все исходные файлы (`git add` новых файлов до сборки). Node.js и SQLite3MultipleCiphers скачиваются с официальных серверов по закреплённым версиям с проверкой SHA256. `requirements-build.txt` закрепляет проверенные версии Python-пакетов. Рецепт PyInstaller: `packaging/UmaRaceLab.spec`; особенности путей основаны на [документации PyInstaller](https://pyinstaller.org/en/stable/runtime-information.html).

Проверка собранного EXE без установленной игры выполняется автоматически при сборке: Tk, локализация и Node/WASM с системным PATH без Python/Node. Проверка с собственной игрой и отдельным пустым кэшем:

```powershell
$env:UMA_LAB_CACHE_DIR = Join-Path $PWD 'build\cold-cache'
.\build\frozen\UmaRaceLab\UmaRaceLab.exe --self-test --game 'D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby' --report '.\build\game-self-test.json'
```

Личная информация в отчётах остаётся в игнорируемой папке build/. Перед обновлением зависимостей повторите холодное извлечение трасс и GUI-проверку. Бинарная сборка без цифровой подписи; Windows может показать стандартное предупреждение о неизвестном издателе.

На сборке 0.4.1 локально пройдены 60 тестов, health check без системных Python/Node и холодное чтение 119 доступных геометрий с расчётом Kyoto #10804. `tools/smoke_frozen_ui.py --game <папка игры>` открывает только свой тестовый процесс EXE, сохраняет снимок его окна в build/frozen-ui.png и закрывает этот процесс. Пользовательские билды остаются отдельно. GitHub Actions не запускался на сервере, поскольку репозитория ещё нет.

Настройки релизной сборки: `%LOCALAPPDATA%/UmaRaceLab`. Старые билды импортируются кнопкой «Загрузить билды» из `local/autosave-builds.json` прежнего проекта. Обновление выполняется распаковкой новой версии в отдельную папку; настройки хранятся вне неё.
