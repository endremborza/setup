LEVEL ?= 1

.PHONY: install install-uv install-dienpy \
        setup-run setup-verify setup-dry-run setup-list \
        test docker-test docker-level1

install: install-dienpy

install-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

install-dienpy:
	uv tool install -e dienpy/

setup-run:
	uv run --directory setup python -m setup run --level $(LEVEL)

setup-verify:
	uv run --directory setup python -m setup verify --level $(LEVEL)

setup-dry-run:
	uv run --directory setup python -m setup run --level $(LEVEL) --dry-run

setup-list:
	uv run --directory setup python -m setup list

test:
	uv run --directory setup pytest

# Level 0 for real, level 1 dry-run — fast CI gate
docker-test:
	docker build -f setup/tests/Dockerfile -t diencephalon-setup-test .

# Full level 0+1 real build + verify — slow (~30 min)
docker-level1:
	docker build -f setup/tests/Dockerfile.level1 -t diencephalon-setup-level1 .
