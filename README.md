# AI Course Generator

A  toolkit for turning technical source material into a full training course with the help of large language models, image generation, and automated slide production. The repository bundles the orchestration scripts, supporting services, and observability utilities that power the workflow.

## Overview

The project grew out of building Cisco-branded enablement content. It now generalises into a pipeline that can:

* Ingest reference PDFs into a Retrieval-Augmented Generation (RAG) store.
* Generate structured outlines, speaker notes, quizzes, flashcards, and exams from course requirement briefs.
* Render PowerPoint decks, slide snapshots, audio narration, and stitched videos.
* Wrap everything in resilient infrastructure with caching, health checks, metrics, and rate limiting.

You can drive the system with interactive menus (`app.py`, `run_app.py`), individual stage scripts (`a01`-`a11`), or a lightweight Flask web demo (`web_app.py`).

## Key Capabilities

**Course production pipeline**
- `a01_RAG_DB_Creation_PDF.py` builds a Chroma vector store from PDF source material.
- `a04_CREATE_OUTLINE.py` turns requirements in `_Cisco_Course_Requirements/` into a four-level outline using the shared LLM client.
- `a05_CREATE_POWERPOINT.py` renders decks with consistent branding, inserts generated imagery, and exports auxiliary Markdown.
- `a06_Image_Generation.py` (+ `arunware_image_generator.py`) manages prompt engineering, batching, caching, and download of Runware images.
- `a06-Student_Notes_Student_Handbook.py`, `a07_QUIZ_Per_Module.py`, `a08_Final_Exam.py`, `a09_Flash_Card.py` round out learner handouts and assessments.
- `a10_Audio_Generation_for_Slides.py` and `a11_Video_Generation_for_slides.py` convert slide notes into narrated video assets.

**Platform services**
- Resilient API access via `llm_client.py`, `image_client.py`, `circuit_breaker.py`, and `rate_limiter.py`.
- Persistent caching (`cache_manager.py`), telemetry (`metrics.py`), and health checks (`health_check.py`).
- Centralised configuration and validation primitives in `config.py`, `validation.py`, and `exceptions.py`.

**Developer tooling**
- CLI demo and smoke tests (`demo.py`, `run_app.py`) that run without external services.
- Comprehensive regression suites (`test_basic.py`, `test_improvements.py`, `enhanced_test_suite.py`).
- Migration notes in `MIGRATION_GUIDE.md` describing the architecture overhaul.

## Repository Layout

```text
.
|- app.py                       # Full-featured console menu for ops and diagnostics
|- run_app.py                   # Lightweight runner showcasing the new components
|- web_app.py                   # Flask demo for generating outlines over HTTP
|- a01_RAG_DB_Creation_PDF.py   # PDF -> text -> Chroma ingestion
|- a04_CREATE_OUTLINE.py        # Outline generator (drives current_directory.txt)
|- a05_CREATE_POWERPOINT.py     # Deck builder with image + notes integration
|- a06_Image_Generation.py      # Slide image prompts + orchestration
|- a06-Student_Notes_Student_Handbook.py
|- a07_QUIZ_Per_Module.py       # Per-module MCQ authoring
|- a07_Slide_Snapshot_Generator.py
|- a08_Final_Exam.py            # Cumulative assessment generator
|- a09_Flash_Card.py            # Flashcards for spaced repetition
|- a10_Audio_Generation_for_Slides.py
|- a11_Video_Generation_for_slides.py
|- llm_client.py / image_client.py
|- cache_manager.py / utils.py / validation.py
|- metrics.py / health_check.py / circuit_breaker.py / rate_limiter.py
`- tests (test_basic.py, test_improvements.py, enhanced_test_suite.py)
```

Supporting resources live alongside the code:

- `_Cisco_Course_Requirements/`: requirement briefs for outline generation.
- `_Cisco_AI_PDFs/` and `_Cisco_AI_TXTs/`: source material for RAG ingestion.
- `_output/`: per-course artefacts (presentations, quizzes, media).
- `rag/`: Chroma database files.
- `course_generator.log`: aggregated logging output.

## Getting Started

### Prerequisites

- Python 3.10+ (tested with CPython).
- `pip` or `uv` for dependency management.
- `ffmpeg` on your PATH if you plan to render video (`a11_Video_Generation_for_slides.py`).
- Google Cloud Text-to-Speech credentials when generating narration (`a10_Audio_Generation_for_Slides.py`).
- Runware API access for image generation.

### Installation

```bash
git clone https://github.com/<your-org>/jupyter_brand_kilo.git
cd jupyter_brand_kilo
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# Optional / stage-specific dependencies
pip install chromadb pypdf python-pptx moviepy google-cloud-texttospeech
```

### Configuration

`config.py` reads from environment variables (via `python-dotenv` if a `.env` file is present). Set the following before running network-enabled stages:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key
RUNWARE_API_KEY=your-runware-key

# Optional overrides
CACHE_ENABLED=true
RATE_LIMIT_REQUESTS=60
ENABLE_METRICS=true
```

You can place these in a `.env` file at the repository root or export them in your shell. Some scripts also expect:

- `gcp-service-account.json` for Google Cloud Text-to-Speech.
- `current_directory.txt`, which is populated automatically by the outline builder and runners to coordinate downstream output paths.

## Usage

### Interactive consoles

- `python app.py` launches the main operations console (health checks, metrics, cache management, quick LLM/image tests, and full regression run).
- `python run_app.py` offers a simplified menu highlighting core resilience and validation features.
- `python demo.py` showcases the security, rate limiting, and circuit breaker utilities without making external API calls.

### Web demo

```
python web_app.py
```

Browse to `http://127.0.0.1:5000/` and submit a topic to receive a generated outline (requires valid LLM credentials).

### Course build pipeline

1. **Prepare source material**
   - Drop requirement briefs (`.txt`) into `_Cisco_Course_Requirements/`.
   - Place reference PDFs in `_Cisco_AI_PDFs/`; the ingestion script will emit companion `.txt` files in `_Cisco_AI_TXTs/`.

2. **Create or refresh the RAG store**
   ```bash
   python a01_RAG_DB_Creation_PDF.py
   ```
   This script extracts text, chunks it, and loads embeddings into Chroma (`rag/`).

3. **Generate the outline**
   ```bash
   python a04_CREATE_OUTLINE.py
   ```
   Pick a requirements file when prompted. The script writes the outline to `course_outline.txt`, updates `current_directory.txt`, and mirrors output under `_output/<course-name>/`.

4. **Produce the slide deck**
   ```bash
   python a05_CREATE_POWERPOINT.py
   ```
   The builder reads the outline, prompts the Runware image client where needed, and emits:
   - `course_presentation.pptx`
   - `course_presentation.md`
   - Slide imagery under `_output/<course-name>/slide_images/`

5. **Supplementary assets (optional)**
   - `python a06-Student_Notes_Student_Handbook.py` -> student handbook plus enhanced speaker notes.
   - `python a07_QUIZ_Per_Module.py` -> 10-question quizzes per module (+ answer keys).
   - `python a07_Slide_Snapshot_Generator.py` -> exports slide thumbnails for audio/video pipelines.
   - `python a08_Final_Exam.py` -> capstone assessment.
   - `python a09_Flash_Card.py` -> spaced repetition deck.

6. **Media generation**
   - `python a10_Audio_Generation_for_Slides.py` uses Google Cloud TTS to narrate notes and stitches audio with slide snapshots.
   - `python a11_Video_Generation_for_slides.py` compiles the narrated slides into a course video (requires `ffmpeg` or MoviePy/OpenCV).

Each stage respects `current_directory.txt` so downstream scripts stay in sync with the chosen course.

### Helper scripts & utilities

- `cache_manager.py` / `cache_manager_simplified.py`: manage `.cache/`, expose decorators for memoising expensive calls.
- `metrics.py`: collect counters and histograms; export to Prometheus if `ENABLE_METRICS=true`.
- `health_check.py`: register service probes; `check_health()` returns a consolidated snapshot.
- `utils.py` / `utils_simplified.py`: file helpers, validation utilities, retry decorators, and central logging setup.
- `rename_files.py`, `do.sh`, and `docs_praxis/`: project-specific automation and documentation.

## Outputs & Storage

- `_output/<course>/` houses the generated artefacts (PPTX, Markdown, quizzes, exams, media).
- `slide_images/`, `audio/`, `video/`, `quizzes/`, `exams/` directories are created as needed beneath the course folder.
- `rag/` holds persistent Chroma state so you can reuse embeddings across runs.
- `course_generator.log` captures logs for debugging; rotate or truncate as needed for long sessions.

## Testing

Run the full regression suite (skips live API calls with mocking where possible):

```bash
python enhanced_test_suite.py
```

Targeted checks:

```bash
pytest                 # Discovers test_*.py
python test_basic.py   # Smoke tests for config, cache, and validation
python test_improvements.py
```

The interactive console (`app.py`) also exposes an option to execute the comprehensive suite from the menu.

## Monitoring & Maintenance

- **Health checks**: `from health_check import check_health; print(check_health())`
- **Metrics snapshot**: `from metrics import get_metrics; print(get_metrics())`
- **Cache operations**: `from cache_manager import cache_manager; cache_manager.clear()`
- **Rate limiting**: centralised via `llm_rate_limiter` and `image_rate_limiter` to avoid surprise throttling.

Enable Prometheus metrics by installing `prometheus-client` (already in `requirements.txt`) and setting `ENABLE_METRICS=true`.

## Optional Integrations

- **Runware**: used for imagery; make sure the `runware` package is installed and the API key is valid (validated through `image_client.validate_api_key()`).
- **Google Cloud Text-to-Speech**: store credentials in `gcp-service-account.json` and set `GOOGLE_APPLICATION_CREDENTIALS` if needed.
- **ChromaDB**: persistent embeddings stored under `rag/`; clear the directory to reset the vector store.
- **OpenRouter**: `llm_client.py` targets OpenRouter endpoints by default. Override `config.DEFAULT_MODEL` or pass `model=` directly.

## Troubleshooting Tips

- If a stage cannot find output directories, confirm `current_directory.txt` contains the intended `_output/<course>` path. Run `a04_CREATE_OUTLINE.py` or either runner to refresh it.
- Image and LLM tests will fail fast without API keys; use the simplified demo or mocked tests when offline.
- Clear `.cache/` if old responses linger after prompt changes: `from cache_manager import cache_manager; cache_manager.clear()`.
- Some optional packages (e.g., `moviepy`, `chromadb`) are not pinned in `requirements.txt`. Install them explicitly when enabling those workflows.

---

For background on the refactor and rationale behind the abstractions, see `MIGRATION_GUIDE.md`.
