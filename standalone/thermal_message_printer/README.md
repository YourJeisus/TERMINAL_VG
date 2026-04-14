# Thermal Message Printer

Автономная утилита для печати короткого сообщения на том же термопринтере, который использует `TerminalVG`.

Что использует:

- прямую печать через Windows GDI, как в [`server.py`](/Users/aleksandrbaranov/Documents/Work/SKUD/TERMINAL_VG/server.py:59)
- ширину чека `576px`, как в [`ticket-service.js`](/Users/aleksandrbaranov/Documents/Work/SKUD/TERMINAL_VG/ticket-service.js:255)

## Файлы

- `print_message.py` — основной скрипт
- `message.txt` — текст, который сейчас будет напечатан
- `requirements.txt` — минимальные зависимости

## Быстрый запуск на терминале Windows

```bash
cd standalone/thermal_message_printer
python -m pip install -r requirements.txt
python print_message.py --dry-run
python print_message.py
```

Или просто из проводника:

- `preview_message.bat` — собрать и открыть превью
- `print_message.bat` — сразу отправить на принтер
- `rollback_local.bat` — удалить эту временную папку после печати

## Если уже поднят локальный сервер проекта

Можно отправить тот же PNG в существующий `/print`:

```bash
python print_message.py --server-url http://localhost:9999/print
```

## Полезные команды

Показать доступные принтеры:

```bash
python print_message.py --list-printers
```

Сохранить превью в явный файл:

```bash
python print_message.py --dry-run --save-preview preview.png
```

Печать в конкретный принтер:

```bash
python print_message.py --printer-name "Имя принтера"
```

## Замечания

- По умолчанию чек разворачивается на `180°`, потому что в основном проекте билеты тоже печатаются в таком виде.
- Emoji `👀 ❤️` рендерятся как изображение, но итоговый вид зависит от доступных Windows-шрифтов.
- Изменение добавляет только новую папку `standalone/thermal_message_printer` и не меняет существующую логику терминала. Если нужно быстро убрать изменение локально, достаточно удалить эту папку.
