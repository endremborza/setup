PROFILES ?= shell

PROFILE_FLAGS := $(addprefix --profile ,$(PROFILES))

.PHONY: install install-uv install-dienpy \
        setup-run setup-verify setup-dry-run setup-list \
        test docker-test docker-ci docker-bootstrap

install: install-dienpy

install-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

# DIENPY_EXTRAS='[tts]' adds the speech stack (onnxruntime, ~100MB) on a workstation
install-dienpy:
	uv tool install -e 'dienpy/$(DIENPY_EXTRAS)'

setup-run:
	uv run --directory setup python -m setup run $(PROFILE_FLAGS)

setup-verify:
	uv run --directory setup python -m setup verify $(PROFILE_FLAGS)

setup-dry-run:
	uv run --directory setup python -m setup run $(PROFILE_FLAGS) --dry-run

setup-list:
	uv run --directory setup python -m setup list

test:
	uv run --directory setup pytest

# Full base+shell+dev real build + verify (~30 min)
docker-test:
	docker build --progress=plain -f setup/tests/Dockerfile.full -t diencephalon-setup-test .

# Fast CI gate: base real + base+shell+dev dry-run
docker-ci:
	docker build --progress=plain -f setup/tests/Dockerfile -t diencephalon-setup-ci .

# End-to-end bootstrap: clones diencephalon from a file:// URL and runs bootstrap.sh.
docker-bootstrap:
	docker build --progress=plain -f setup/tests/Dockerfile.bootstrap -t diencephalon-setup-bootstrap .
