# Hellcat Sandbox — Dodge Challenger Hellcat crash sandbox

🇷🇺 [Русский](#-русский) · 🇬🇧 [English](#-english)

![Showcase](docs/images/showcase.jpg)

---

## 🇷🇺 Русский

Играбельная песочница: вы водите **Dodge Challenger SRT Hellcat Widebody** по полигону и разбиваете его об препятствия.
Кузов **не анимация**: это настоящая мягкая физика (узлы и балки, как в BeamNG), 2 000 шагов в секунду.
Машина мнётся, ломается, теряет детали — всё зависит от скорости и угла удара.

### Как запустить (5 минут, ничего устанавливать не нужно)

#### 🪟 Windows 10 / 11

1. Скачайте файл **[Play-Windows.bat](Play-Windows.bat)**: откройте его по ссылке и нажмите кнопку **«Download raw file»** (значок ⬇ справа вверху).
2. Дважды щёлкните по скачанному файлу.
3. Если Windows пишет *«Windows защитила ваш компьютер»* — нажмите **«Подробнее» → «Выполнить в любом случае»**. Это нормально: файл не подписан.
4. При первом запуске файл сам скачает игру (около 80 МБ) — подождите пару минут. Потом игра откроется.
   В следующие разы запуск будет мгновенным.

#### 🍎 Mac (лучше всего Apple Silicon: M1 / M2 / M3 / M4)

Самый простой способ — одна строка в Терминале:

1. Откройте **Терминал** (Cmd + Пробел → наберите «Терминал» → Enter).
2. Вставьте эту строку и нажмите Enter:

   ```bash
   bash <(curl -fsSL https://raw.githubusercontent.com/Prokopiy8247/Opus55-Dodge-Challenger-3DModel/main/Play-Mac.command)
   ```
3. При первом запуске игра скачается (около 80 МБ) и откроется сама.

Другой способ: скачайте **[Play-Mac.command](Play-Mac.command)**, нажмите на нём **правой кнопкой → «Открыть» → «Открыть»**.
Если пишет «нет прав» — в Терминале выполните `chmod +x ~/Downloads/Play-Mac.command` и откройте файл снова.

> ⚠️ Версия для Mac собрана из того же проекта, но автор мог проверить игру только на Windows.
> Если на Mac что-то не заработало — напишите в [Issues](../../issues), приложите модель Mac и текст ошибки.

### Управление

| Клавиша | Что делает |
|---|---|
| **W / S** | газ / тормоз (удерживайте S на месте — задний ход) |
| **A / D** | руль |
| **Пробел** | ручник |
| **C** | камера: сзади, бампер, **из салона**, свободная |
| **Esc** | меню: **телепорт к любому препятствию** на выбранной скорости |
| **R** | вернуть машину целой на последнее безопасное место |
| **Shift + R** | починить на месте |
| **T** | замедленное время (удобно смотреть, как мнётся кузов) |
| **N / H** | показать «скелет» машины / карту напряжений |
| **F5 / F6** | записать заезд / воспроизвести (повтор точный до бита) |

Геймпад тоже работает. Все клавиши: [docs/controls.md](docs/controls.md).

**Что попробовать:** нажмите **Esc**, выберите «O1 — бетонная стена», скорость 56 км/ч — и посмотрите удар
с разных камер, потом **T** (замедление) и **Shift + H** (карта деформаций).

### Если не работает

| Проблема | Что делать |
|---|---|
| Игра тормозит, в углу «SLOW-DOWN» | Слабый процессор: физика считается 2 000 раз в секунду. Закройте браузер и другие программы |
| Скачивание не началось / ошибка | Проверьте интернет и запустите файл ещё раз |
| Антивирус ругается на `.bat` | Файл только скачивает архив с этого репозитория и запускает игру — его текст можно открыть блокнотом |
| Хочу удалить игру | Удалите папку `HellcatSandbox` в вашей домашней папке (`C:\Users\<user>\HellcatSandbox` / `~/HellcatSandbox`) |

Требования: Windows 10/11 64-bit с видеокартой DirectX 12 (или Mac с Metal), процессор от 6 ядер, 8 ГБ ОЗУ.

### Для разработчиков

Блендер (модель и скелет) → Unity 6000.6 (собственный физический движок на Burst/Jobs). Всё воспроизводимо:
подробно в **[docs/README.md](docs/README.md)** (сборка из исходников, настройка физики, тесты и гейты качества),
отчёты по фазам — `docs/P0_report.md … P7_report.md`, решения — `docs/decisions.md`.
Фотографии-референсы и тяжёлые видео в репозиторий не входят.

---

## 🇬🇧 English

A playable sandbox: drive a **Dodge Challenger SRT Hellcat Widebody** around a test ground and crash it into obstacles.
The damage is **not an animation** — it is a real soft-body simulation (nodes and beams, BeamNG style) running at 2,000 steps per second.

### How to run (5 minutes, nothing to install)

**Windows 10 / 11**

1. Download **[Play-Windows.bat](Play-Windows.bat)** (open it, click **Download raw file** ⬇).
2. Double-click it. If Windows says *"Windows protected your PC"* → **More info → Run anyway** (the file is unsigned).
3. On the first start it downloads the game (~80 MB) and launches it. Next time it starts instantly.

**Mac** (Apple Silicon recommended)

Open **Terminal** and paste:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Prokopiy8247/Opus55-Dodge-Challenger-3DModel/main/Play-Mac.command)
```

Or download **[Play-Mac.command](Play-Mac.command)** and right-click → **Open**. If it says "permission denied", run `chmod +x ~/Downloads/Play-Mac.command`.

> ⚠️ The Mac build comes from the same project, but the author could only test on Windows. Please open an [Issue](../../issues) if it fails.

### Controls

W/S throttle/brake · A/D steer · Space handbrake · **C** cameras (incl. cockpit) · **Esc** menu (teleport to any obstacle at a chosen speed) ·
**R** reset · **Shift+R** repair · **T** slow motion · **N/H** skeleton / stress view · **F5/F6** record / replay. Full list: [docs/controls.md](docs/controls.md).

Try it: **Esc** → "O1 wall" → 56 km/h, then **T** and **Shift+H** to watch the crush.

### For developers

Blender (model, skeleton) → Unity 6000.6 with a custom Burst/Jobs solver. See **[docs/README.md](docs/README.md)** for building from source, tuning,
tests and quality gates; phase reports in `docs/P*_report.md`, all design decisions in `docs/decisions.md`.
Reference photos and heavy videos are not part of the repository.

![Crash scenarios](docs/images/crash_scenarios.jpg)
