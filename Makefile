.PHONY: test install dev
install:
	python -m pip install -e .

dev:
	python -m pip install -e ".[dev]"

test:
	pytest
