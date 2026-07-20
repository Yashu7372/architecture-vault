# SDCourse Daily Learning Builder

This pipeline is designed for learning, not merely indexing.

For each curriculum day it performs two separate operations:

1. Save every curriculum detail, article paragraph, code fragment, link, and architecture image URL that is publicly visible without subscriber access.
2. Produce a new, detailed engineering lesson that explains the topic from first principles and connects it to the previous and next course days.

The generated explanation is original educational material. It does not authenticate, bypass a paywall, inspect hidden subscriber state, or reconstruct subscriber-only course text.

## Public access classifications

- `public` — enough article content is publicly visible.
- `preview` — only an introduction, partial article, or architecture preview is visible.
- `curriculum-only` — only the public day title and expected output are available.

Paywall and subscription UI elements are removed before Markdown conversion. Public images remain as source URLs when the page exposes them.

## Supported tracks

- `sdcourse-python-js` — Python and JavaScript.
- `sdcourse-java-spring` — Java and Spring Boot.

## Recommended: one lesson per scheduled run

Run the next unfinished Python/JavaScript lesson once:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py
```

Run the next Java/Spring lesson:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track java-spring
```

Process three lessons per run:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --lessons-per-run 3
```

Run both tracks:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track all
```

Every invocation resumes from the existing manifest and scheduler state. A lock file prevents overlapping runs.

## Built-in daemon scheduler

Keep the process running and execute one lesson every 24 hours:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --daemon \
  --interval-hours 24
```

For production use, an operating-system scheduler is more reliable than a permanently running terminal.

### Linux cron example

```cron
0 6 * * * cd /path/to/architecture-vault && /path/to/python engineering-knowledge-base/scripts/run_daily_course_learning.py >> engineering-knowledge-base/output/scheduler/cron.log 2>&1
```

### Windows Task Scheduler

Create a daily task whose program is the virtual-environment Python executable and whose arguments are:

```text
engineering-knowledge-base\scripts\run_daily_course_learning.py --track python-js
```

Set the working directory to the repository root.

## Detailed lesson generation

Without an LLM endpoint, the pipeline uses its built-in topic profiles and creates a structured engineering lesson covering architecture, components, flow, implementation, failures, observability, security, trade-offs, tests, and study questions.

For deeper lesson completion, configure any OpenAI-compatible company or local model router:

```bash
export COURSE_LLM_BASE_URL="https://your-company-router.example/v1"
export COURSE_LLM_MODEL="approved-engineering-model"
export COURSE_LLM_API_KEY="your-token"
```

Optional controls:

```bash
export COURSE_LLM_MAX_TOKENS="6500"
export COURSE_LLM_TIMEOUT_SECONDS="180"
export COURSE_LLM_TEMPERATURE="0.25"
export COURSE_LLM_STRICT="false"
```

When the model endpoint fails and strict mode is disabled, the scheduler records the error and uses the deterministic lesson builder instead.

The model prompt explicitly requires original content and forbids reconstructing or imitating subscriber-only text.

## Output for each day

```text
engineering-knowledge-base/output/daily-learning/
└── sdcourse-python-js/
    └── day-001/
        ├── 01-public-source.md
        ├── 02-completed-lesson.md
        └── STATUS.json
```

`01-public-source.md` contains only publicly visible source material and curriculum metadata.

`02-completed-lesson.md` contains the original detailed lesson, including:

- learning objectives and terminology;
- the course position and previous/next-day continuity;
- requirements and invariants;
- first-principles explanation;
- architecture and component responsibilities;
- end-to-end data flow;
- contracts and data models;
- detailed implementation steps;
- Python/JavaScript or Java/Spring-specific notes;
- concurrency, ordering and consistency analysis;
- retries, idempotency, backpressure and recovery;
- scaling and performance considerations;
- metrics, logs and traces;
- security and governance;
- alternatives and trade-offs;
- a hands-on exercise;
- validation and load-testing guidance;
- a Mermaid architecture diagram;
- key takeaways and study questions.

`STATUS.json` records the public access level, source character count, completion mode, model, fallback error, and generation time.

Global progress is stored at:

```text
engineering-knowledge-base/output/scheduler/sdcourse-state.json
```

It records completed days, the next pending day, remaining lessons, the latest collection report, and the artifacts generated by the previous run.

## Bulk ingestion

The bulk command remains available when you want to process many lessons immediately:

```bash
python engineering-knowledge-base/scripts/ingest_substack_system_design_course.py \
  --track all \
  --resume \
  --max-lessons 10
```

The retrieval context database is no longer the primary output. Rebuild it only when needed:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --rebuild-context
```

## Copyright and privacy rule

Keep copied public article fragments, generated learning files, scheduler state, and databases local or in private storage. Do not publish copied article text. Public repositories should contain the collector code, public source links, and original explanations or summaries only.
