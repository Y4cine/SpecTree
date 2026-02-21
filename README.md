# SpecTree MVP

A Windows-friendly desktop app for editing a hierarchical text tree and exporting deterministic Markdown.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run app

```bash
python -m app.main
```

## Run tests

```bash
pytest
```

## Assumptions

- The spec source is `ProjectSpecs/Specs_2.md`.
- Expand accepts one top-level heading root in the source node content.
- Flatten/Expand on root are blocked because result insertion must be as sibling after source.
- Markdown export always starts from the tree root and includes root heading/content unless filtered out by `printable_only`.
- JSON loader tolerates missing optional keys by using spec defaults.
- Multi-instance protection uses an exclusive OS lock on `<document>.lock`; instances without the lock open in read-only mode and cannot execute model-changing actions or save.
