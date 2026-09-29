#!/usr/bin/env bash
# Quarto post-render hook: applies the UANL front matter and layout to the thesis docx.
# Runs with the thesis/ directory as cwd; Quarto sets QUARTO_PROJECT_OUTPUT_FILES.
set -euo pipefail
exec uv run --project .. python ../scripts/postprocess_docx.py --from-quarto-env
