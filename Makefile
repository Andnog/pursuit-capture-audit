.PHONY: help install lint format test verify recompute numbers results check-results check site serve

help:            ## List the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | expand -t 18

install:         ## Create the environment of the library
	uv sync

lint:            ## Check style and common errors (ruff)
	uv run ruff check src tests tools
	uv run ruff format --check src tests tools

format:          ## Format the library, its tests and the tools
	uv run ruff format src tests tools

test:            ## Run the tests of the library, including the equivalence tests
	uv run pytest

verify:          ## Level 0: compare every sealed file with its checksum
	uv run pursuit-audit verify

recompute:       ## Level 1: recompute the headline results from the per-episode records
	uv run pursuit-audit recompute

numbers:         ## Level 1: rewrite the table of every number of the article
	uv run python tools/build_results.py

results: numbers ## Regenerate the catalogue of studies and the tables of results/
	uv run python tools/build_catalogue.py
	uv run python tools/build_results.py

check-results:   ## Fail if the committed tables are out of date
	uv run python tools/build_results.py --check

check: lint test verify recompute check-results  ## Everything that needs no simulator

site:            ## Build the web site into site/
	uv run --group docs mkdocs build --strict

serve:           ## Preview the web site at http://127.0.0.1:8000
	uv run --group docs mkdocs serve
