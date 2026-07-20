# SDCourse Public Curriculum Context

This pipeline collects the publicly accessible curriculum and article text from `sdcourse.substack.com` in curriculum order and turns it into a local learning context.

## Access boundary

The implementation does **not** authenticate, bypass a paywall, inspect hidden page state, or reconstruct subscriber-only lessons.

For each curriculum day it records one of three access levels:

- `public` — enough article content is publicly visible.
- `preview` — only a public preview is visible.
- `curriculum-only` — only the public day title and expected output are available.

Subscriber-only elements detected in the page are removed before Markdown conversion. Each generated note clearly separates public source material from the original stitched study guide.

## Supported tracks

- `sdcourse-python-js` — the Python and JavaScript curriculum.
- `sdcourse-java-spring` — the Java and Spring Boot curriculum.

## One-command ingestion

Python and JavaScript track:

```bash
python engineering-knowledge-base/scripts/ingest_substack_system_design_course.py
```

Java and Spring Boot track:

```bash
python engineering-knowledge-base/scripts/ingest_substack_system_design_course.py \
  --track java-spring
```

Both tracks:

```bash
python engineering-knowledge-base/scripts/ingest_substack_system_design_course.py \
  --track all
```

Resume after an interrupted run:

```bash
python engineering-knowledge-base/scripts/ingest_substack_system_design_course.py \
  --track all \
  --resume
```

Smoke-test the first five lessons from a selected track:

```bash
python engineering-knowledge-base/scripts/ingest_substack_system_design_course.py \
  --max-lessons 5
```

## Generated artifacts

```text
engineering-knowledge-base/output/
├── notes/sdcourse-python-js/
├── notes/sdcourse-java-spring/
├── indexes/
├── reports/
├── courses/
│   ├── sdcourse-python-js/LEARNING_PATH.md
│   └── sdcourse-java-spring/LEARNING_PATH.md
└── context/
    ├── context.sqlite
    ├── chunks.jsonl
    └── graph.json
```

Every daily note includes:

1. Public article text or public preview when available.
2. Curriculum day, module, week, expected output, article URL and access classification.
3. Previous-day and next-day continuity.
4. An original conceptual explanation of why the lesson exists.
5. Reference components and data flow.
6. Implementation and validation guidance.
7. Failure scenarios, observability, security and trade-offs.
8. A Mermaid architecture sketch and study questions.

## Important copyright rule

Keep generated full-text notes and databases local or private. Do not publish copied article text. Public repositories should contain only the collector code, source links, and original analysis or summaries.
