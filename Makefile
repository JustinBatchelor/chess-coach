PODMAN ?= podman
IMAGE_NAME ?= chess-coach
QUAY_NAMESPACE ?= jbatchel
VERSION ?= 0.1.0
GIT_SHA ?= $(shell git rev-parse --short HEAD)
PLATFORM ?= linux/amd64
BUILD_PLATFORM ?= linux/$(shell $(PODMAN) info --format '{{.Host.Arch}}')
DIGEST ?=
SYFT_IMAGE ?= ghcr.io/anchore/syft:v1.49.0
LOCAL_IMAGE := localhost/$(IMAGE_NAME):$(VERSION)
QUAY_IMAGE := quay.io/$(QUAY_NAMESPACE)/$(IMAGE_NAME)

.PHONY: build up down test backend-test frontend-test lint login push inspect sbom helm-check

build:
	$(PODMAN) build --platform $(PLATFORM) \
		--build-arg APP_VERSION=$(VERSION) \
		--build-arg VCS_REF=$(GIT_SHA) \
		--build-arg FRONTEND_PLATFORM=$(BUILD_PLATFORM) \
		-t $(LOCAL_IMAGE) -f Containerfile .

up:
	$(PODMAN) compose up --build

down:
	$(PODMAN) compose down

backend-test:
	python -m pytest

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test

lint:
	ruff check app tests
	cd frontend && npm run build

login:
	$(PODMAN) login quay.io

push: build
	$(PODMAN) tag $(LOCAL_IMAGE) $(QUAY_IMAGE):$(VERSION)
	$(PODMAN) tag $(LOCAL_IMAGE) $(QUAY_IMAGE):sha-$(GIT_SHA)
	$(PODMAN) push $(QUAY_IMAGE):$(VERSION)
	$(PODMAN) push $(QUAY_IMAGE):sha-$(GIT_SHA)

inspect:
	skopeo inspect docker://$(QUAY_IMAGE):$(VERSION)

sbom:
	test -n "$(DIGEST)"
	mkdir -p build
	$(PODMAN) run --rm \
		-v "$(CURDIR)/build:/output:Z" \
		$(SYFT_IMAGE) scan \
		"registry:$(QUAY_IMAGE)@$(DIGEST)" \
		-o "spdx-json=/output/sbom-$(VERSION).spdx.json"

helm-check:
	helm lint charts/chess-coach
	helm template chess-coach charts/chess-coach -f charts/chess-coach/values-openshift.yaml
