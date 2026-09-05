.PHONY: help install lint format check test run

help:
	@echo "make install  - install runtime + dev dependencies"
	@echo "make lint      - ruff lint (report issues)"
	@echo "make format    - black + ruff --fix (auto-format & fix)"
	@echo "make check     - lint + format-check without modifying (CI gate)"
	@echo "make test      - run the test suite"
	@echo "make run       - run the dev API server"

install:
	pip install -r requirements.txt
	pip install ruff==0.8.4 black==24.10.0

lint:
	ruff check app tests

format:
	black app tests
	ruff check --fix app tests

check:
	ruff check app tests
	black --check app tests

test:
	pytest -q

run:
	uvicorn app.main:app --reload --port 8000
