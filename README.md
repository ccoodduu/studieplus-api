# studieplus-api

Python-klient til [Studie+](https://studieplus.dk), den danske skoleplatform. Den taler GWT-RPC direkte med `requests` og kræver ingen browser. Den kører fint på en Raspberry Pi (Python 3.9+, ~30 MB RAM).

Bruges af:
- [studieplus-mcp](https://github.com/ccoodduu/studieplus-mcp): MCP-server til Claude Desktop
- [studieplus-calendar](https://github.com/ccoodduu/studieplus-calendar): skemaet som ICS-feed til Google Kalender

## Installation

```bash
pip install "studieplus-api @ git+https://github.com/ccoodduu/studieplus-api"
```

## Brug

```python
from datetime import datetime, timedelta
from studieplus_api import StudiePlusRequestsScraper

scraper = StudiePlusRequestsScraper(username="...", password="...", school="DIN_SKOLE")
# eller sæt STUDIEPLUS_USERNAME / STUDIEPLUS_PASSWORD / STUDIEPLUS_SCHOOL som environment variables
scraper.login()

start = datetime(2026, 9, 28)
for lesson in scraper.get_lessons_in_range(start, start + timedelta(days=6)):
    print(lesson.start_time, lesson.subject, lesson.rooms, lesson.homework)
```

`get_lessons_in_range` parser *strict*. Hvis Studie+ har ændret deres GWT-struktur, rejser den en fejl i stedet for stille og roligt at returnere forkerte eller manglende timer.

Andre metoder: `parse_schedule(week_offset)`, `get_homework(only_open)`, `get_assignment_details(...)`, `get_lesson_files_with_urls(lesson_id)` m.fl. Se `requests_scraper.py`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

`tests/test_gwt_deserializer.py` kører offline. `tests/test_live.py` logger ind med credentials fra `.env` (se `.env.example`) og tjekker formen på de rigtige data. Uden credentials bliver live-testene sprunget over.

Se `GWT_REVERSE_ENGINEERING.md` og `CLAUDE.md` for, hvordan GWT-formatet parses, og hvordan man tilføjer nye typer.

## Licens

MIT
