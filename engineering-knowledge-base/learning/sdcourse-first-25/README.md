# SDCourse First 25 Review

Start with [FIRST_25_OVERVIEW.md](FIRST_25_OVERVIEW.md). It explains how Days 1–25 evolve one LogStream system and why each lesson matters.

The GitHub Actions workflow `.github/workflows/sdcourse-first-25.yml` generates the private review artifact containing:

- all 25 `01-public-source.md` captures;
- all 25 `02-completed-lesson.md` original lessons;
- `STATUS.json` access classification for every day;
- the complete 254-day curriculum context;
- `PUBLIC_IMAGE_CATALOG.md`;
- locally downloaded public images when anonymous image download succeeds;
- `REVIEW_PACK_INDEX.md`.

Source bodies and image binaries are kept in the private workflow artifact rather than committed to the public repository. The committed overview is original educational writing.
