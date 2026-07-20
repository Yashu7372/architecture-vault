# SDCourse Day-by-Day Learning System

This pipeline turns the public curriculum and anonymously visible lesson material at `sdcourse.substack.com` into a personal day-by-day learning workflow.

## Main goal

The primary output is not merely a retrieval database. For every curriculum day, the workflow:

1. discovers the lesson in Day 1..N curriculum order;
2. captures material available without subscriber authentication;
3. saves the captured material separately;
4. generates an original, standalone technical lesson that completes the topic;
5. records progress so the next run continues from the next unfinished day.

## Access boundary

The implementation does not log in, bypass paid access, inspect hidden subscriber state, or treat reader/crawler output as automatically public.

For the Python/JavaScript curriculum, the publication explicitly advertises the first three lessons as free. The source configuration therefore allows full anonymous capture only through Day 3. Later lessons are reduced to their anonymous introductory section, public diagrams/image links, curriculum title, expected output, and article URL.

Each daily lesson is classified as:

- `public` — verified anonymously available lesson content;
- `preview` — only the anonymous introductory section is retained;
- `curriculum-only` — only the public curriculum record is available.

## Complete curriculum context

Every run discovers the full curriculum before applying the per-run lesson limit. It generates:

```text
output/courses/sdcourse-python-js/
├── CURRICULUM_CONTEXT.md
├── CURRICULUM_CONTEXT.json
└── LEARNING_PATH.md
```

The curriculum context contains public metadata only:

- module;
- week;
- day and order;
- lesson title;
- expected output;
- article URL.

The parser maps the roadmap's nine module ranges and forty week entries to the 254 sequential lesson rows. Weekly groups are identified by the curriculum list ordinal resetting to `1`.

## First five review pack

Original review documents are committed under:

```text
learning/sdcourse-python-js/module-01/week-01/
├── README.md
├── day-001-development-environment.md
├── day-002-configurable-log-generator.md
├── day-003-local-log-collector.md
├── day-004-log-parsing.md
└── day-005-flat-file-storage.md
```

They form one local vertical slice:

```text
reproducible environment
  -> controlled log generator
  -> reliable file collector
  -> canonical parser
  -> append-only rotated storage
```

The committed exploration documents are original writing. Runtime article captures stay under the Git-ignored `output` directory or a private workflow artifact.

## Daily generated files

```text
output/daily-learning/sdcourse-python-js/day-001/
├── 01-public-source.md
├── 02-completed-lesson.md
└── STATUS.json
```

`01-public-source.md` contains the public source boundary. `02-completed-lesson.md` contains the original technical expansion. The detailed exploration documents in `learning/` are the curated review versions.

## Run the next Python/JavaScript lesson

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track python-js
```

Process the first or next five unfinished lessons:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track python-js \
  --lessons-per-run 5
```

Java/Spring Boot track:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track java-spring
```

Run continuously:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track python-js \
  --daemon \
  --interval-hours 24
```

## Progress and resume

Progress is stored at:

```text
output/scheduler/sdcourse-state.json
```

The scheduler:

- prevents overlapping executions;
- marks each day completed or failed;
- records collection and completion modes;
- resumes at the next unfinished day;
- writes state atomically.

## Optional model-backed completion

Without a configured model, the workflow uses deterministic topic-specific engineering templates.

For an approved OpenAI-compatible model endpoint:

```bash
export COURSE_LLM_BASE_URL="https://router.example/v1"
export COURSE_LLM_MODEL="approved-engineering-model"
export COURSE_LLM_API_KEY="token"
```

Optional settings:

```bash
export COURSE_LLM_MAX_TOKENS="6500"
export COURSE_LLM_TIMEOUT_SECONDS="180"
export COURSE_LLM_TEMPERATURE="0.25"
export COURSE_LLM_STRICT="false"
```

## Optional retrieval context

Context rebuilding is not the primary workflow, but it remains available:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track python-js \
  --rebuild-context
```

## Validation

Two workflows validate the branch:

1. `Engineering Knowledge Base CI`
   - installs dependencies;
   - compiles Python sources;
   - runs all unit tests.

2. `SDCourse First Five Lessons`
   - executes a real anonymous scrape;
   - discovers exactly 254 curriculum lessons;
   - generates Days 1–5;
   - verifies Module 1 / Week 1 mapping;
   - verifies access levels are exactly `public, public, public, preview, preview`;
   - uploads a private review artifact.

## Publishing rule

Do not commit runtime source captures or generated article bodies. Keep them local or private. Public repository content should be limited to collector code, source links, public curriculum metadata when appropriate, and original analysis/explanations.
