# Project Context: Aquinoz_Bot

**Analysis Date:** 2026-08-07 22:45:22

## Project Statistics
- Total files analyzed: 26
- Total lines of code (estimated): 2297
- Total size of analyzed files: 0.09 MB

## Detected Languages
- Python: 19 files
- Markdown: 1 file
- HTML: 1 file

## Detected Technologies
No specific technologies/frameworks detected.

## Directory Structure
```text
├── .devdbrc
├── .env
├── .env.example
├── .gitignore
├── README.md
├── app.py
├── config.py
├── controllers/
│   └── telegram_handler.py
├── core/
│   ├── auth.py
│   └── telemetry.py
├── database.db-wal
├── models.py
├── services/
│   ├── ai_assistant.py
│   ├── chunker.py
│   ├── image_reader.py
│   ├── pdf_reader.py
│   ├── scraper.py
│   ├── stt.py
│   ├── telegram.py
│   └── tts.py
├── site/
│   └── index.html
├── tasks/
│   ├── ingestion.py
│   ├── media.py
│   └── study.py
└── utils/
    ├── menus.py
    └── text_helpers.py
```

## Latest Commits
- **e64ee26** - feat: adição da função de pedir comandos com a voz
  - Author: Elliton-Luis
  - Date: 2026-05-22 17:19:31 -0300
    - `database.db-shm`
    - `database.db-wal`
    - `services/stt.py`

- **195f52b** - feat: adição da função de transformar audio em texto
  - Author: Elliton-Luis
  - Date: 2026-05-22 17:18:09 -0300
    - `controllers/telegram_handler.py`
    - `services/image_reader.py`
    - `services/stt.py`
    - `services/tts.py`
    - `tasks/media.py`
    - `tasks/study.py`

- **d72cb67** - fix: otimização da UX e correção de bugs
  - Author: Elliton-Luis
  - Date: 2026-05-17 23:25:55 -0300
    - `controllers/telegram_handler.py`
    - `core/telemetry.py`
    - `database.db-shm`
    - `database.db-wal`
    - `deactivate_telemetry.md`
    - `tasks/study.py`
    - `utils/menus.py`

- **6ddb606** - Merge pull request #10 from ArthurThuko/thuko
  - Author: Arthur_Thuko
  - Date: 2026-05-17 21:36:38 -0300

- **663d83c** - fix: atualizar descrição dos resumos automáticos no README
  - Author: ArthurThuko
  - Date: 2026-05-17 21:32:27 -0300
    - `README.md`

- **5ea95ac** - Merge pull request #9 from ArthurThuko/thuko
  - Author: Arthur_Thuko
  - Date: 2026-05-17 20:54:45 -0300

- **00baa80** - fix: aprimorar captura de gabarito com regex flexível e adicionar fallback
  - Author: ArthurThuko
  - Date: 2026-05-17 20:53:22 -0300
    - `tasks/study.py`

- **d18e4b3** - feat: criação do site para facilitar o acesso ao bot
  - Author: Elliton-Luis
  - Date: 2026-05-17 17:07:59 -0300
    - `.gitignore`
    - `database.db-shm`
    - `database.db-wal`
    - `site/index.html`
    - `tasks/study.py`
    - `utils/text_helpers.py`

- **f9fd822** - Merge pull request #8 from ArthurThuko/thuko
  - Author: Arthur_Thuko
  - Date: 2026-05-17 16:30:21 -0300

- **ec9a872** - fix: atualizar arquivos de banco de dados para refletir as últimas alterações
  - Author: ArthurThuko
  - Date: 2026-05-17 16:28:49 -0300
    - `database.db-shm`
    - `database.db-wal`


## Recently Modified Files
- `database.db-shm`
- `database.db-wal`
- `services/stt.py`
- `controllers/telegram_handler.py`
- `services/image_reader.py`
- `services/tts.py`
- `tasks/media.py`
- `tasks/study.py`
- `core/telemetry.py`
- `deactivate_telemetry.md`
- `utils/menus.py`
- `README.md`
- `.gitignore`
- `site/index.html`
- `utils/text_helpers.py`