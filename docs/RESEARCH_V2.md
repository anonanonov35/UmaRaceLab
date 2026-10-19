# Локальный анализ, 18 октября 2026

Установка: Steam 3224770, Global build 25384634, Unity 2022.3.62f2, IL2CPP 31.1.

## Ресурсный индекс и трассы

`Persistent/meta` читается в режиме read-only через официальный SQLite3MultipleCiphers (ChaCha20) с публичными параметрами совместимости формата из UmaViewer. Таблица `a`: `n` — логическое имя, `h` — имя по хешу, `e` — параметр преобразования bundle. Бинарные ресурсы остаются в `Persistent/dat/<first-two-hash-chars>/<hash>`.

Из `race/courseeventparam/<course>/pfb_prm_race<course>` читается `courseParams`:

- type 0: поворот, `_values` содержит номер и длину;
- type 2: начало/конец прямой и её frontType;
- type 7: точка разрешения движения по полосам;
- type 11: уклон, `_values` содержит исходную крутизну и длину.

Из соответствующего `race/course/<track>/pos/an_pos_race...` читается CourseLaneAnim: Distance и 1001 равномерный по дистанции sample valueX/valueZ/valueY. X/Z дают настоящий вид сверху, Y — профиль высот. Локальные courseParams задают игровые уклоны отдельно от визуального пути.

Проверено 119/121 записей. 11201: нет точной lane animation; 11202: нет courseeventparam. Совпадение имени ресурса и дистанции обязательно; соседняя трасса не подставляется.

Пример Tokyo 2400, course 10606: повороты 325+250, 575+325, 1350+275, 1625+250 м; последняя прямая 1875–2400 м. Уклоны: 0–40 +1.5%, 1125–1200 +2%, 1250–1500 −1.5%, 1950–2100 +1.5%.

## Параметры и метаданные

`race/racemain/ast_race_paramdefine` содержит дерево Global/Speed/Slope/Hp/PositionKeep/Temptation/ConservePower/Skill и другие группы. Локально сохранены исходные float32-значения. Использованы таблицы уровней/масштабирования навыков, HP-duration, ограничения дополнительных срабатываний и FinishTimeCoef (1.1799999475).

В стандартной metadata прочитаны:

- `RaceManagerSimulate.SIMULATE_ELAPSED_TIME`: байты `95 65 88 3d`, float32 0.066600002348423;
- `HorseRaceInfoSimulate.ORDER_IN_CHECK_TIME` и `ORDER_OUT_CHECK_TIME`: 5 с;
- enum ability types: 8 VisibleDistance; 501–503 ChallengeMatchBonus*;
- usage 11: MultiplyOrderUpCountCornerPhaseEndAfter;
- duration usage: Direct, MultiplyDistanceDiffTop, MultiplyRemainHp1, IncrementOrderUp, MultiplyRemainHp2;
- additional activation: OrderUp и ActivateAnySkill 1/2.

## Нативный код

Статический PE-анализ GameAssembly показывает крупные виртуальные секции с очень малым/пустым raw-представлением и большой overlay. Это объясняет ограниченность обычного статического поиска, но не даёт тел расчётных функций. Il2CppDumper и Cpp2IL ранее не нашли code/metadata registrations. Инъекции, чтение защищённого процесса и изменение клиента не использовались.

Отчёты: `%TEMP%/uma-race-lab-build25384634/`; кэш геометрии — отдельная временная папка. SHA256 master.mdb: `4ff8f53b4446adc922f74dadd14a238ac6fef430425be40776da8331f5ecae6c`. Сравнение хеша до/после интеграционных проверок обязательно.

Дальнейшее исследование должно дать эталоны известной гонки и установить порядок операций/RNG. Наличие всех файлов само по себе не означает, что нативная логика уже восстановлена.
