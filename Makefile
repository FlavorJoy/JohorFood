all: help

help:
	@echo "Available targets:"
	@echo "  sql   – Generate SQL from CSV."
	@echo "  readme – Generate README from CSV."
	@echo "  ci    – Run CI checks (flake8, black, mypy, tests)."
	@echo "  lint  – Run flake8, black, mypy.
	@echo "  test  – Run tests with pytest."

sql:
	python export_to_sql.py

readme:
	python readme_render.py

lint:
	black --check .
	flake8
	mypy .

test:
	pytest

ci: lint test
