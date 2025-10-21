# ============================================================
# Makefile for Ray Serve Docker Image
# ============================================================

# Variables
IMAGE_NAME ?= ray-serve-vllm
REGISTRY ?= gcr.io/your-project
TAG ?= latest
FULL_IMAGE = $(REGISTRY)/$(IMAGE_NAME):$(TAG)

# Python version
PYTHON_VERSION ?= 3.10

# Ray and VLLM versions
RAY_VERSION ?= 2.9.0
VLLM_VERSION ?= 0.6.1.post2

# Build arguments
BUILD_ARGS = \
	--build-arg PYTHON_VERSION=$(PYTHON_VERSION) \
	--build-arg RAY_VERSION=$(RAY_VERSION) \
	--build-arg VLLM_VERSION=$(VLLM_VERSION)

.PHONY: help
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

.PHONY: build
build: ## Build Docker image
	@echo "Building $(FULL_IMAGE)..."
	docker build \
		$(BUILD_ARGS) \
		-t $(FULL_IMAGE) \
		-t $(REGISTRY)/$(IMAGE_NAME):$(RAY_VERSION) \
		-f Dockerfile \
		.
	@echo "✓ Built: $(FULL_IMAGE)"

.PHONY: build-no-cache
build-no-cache: ## Build Docker image without cache
	@echo "Building $(FULL_IMAGE) (no cache)..."
	docker build \
		$(BUILD_ARGS) \
		--no-cache \
		-t $(FULL_IMAGE) \
		-f Dockerfile \
		.
	@echo "✓ Built: $(FULL_IMAGE)"

.PHONY: push
push: ## Push Docker image to registry
	@echo "Pushing $(FULL_IMAGE)..."
	docker push $(FULL_IMAGE)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(RAY_VERSION)
	@echo "✓ Pushed: $(FULL_IMAGE)"

.PHONY: build-push
build-push: build push ## Build and push image

.PHONY: run
run: ## Run container locally
	docker run -it --rm \
		--gpus all \
		-p 8000:8000 \
		-p 8265:8265 \
		-v $(PWD)/model_config.yaml:/app/model_config.yaml \
		-v $(HOME)/.cache/ray-models:/mnt/models:ro \
		$(FULL_IMAGE)

.PHONY: run-bash
run-bash: ## Run container with bash shell
	docker run -it --rm \
		--gpus all \
		-v $(PWD):/app \
		--entrypoint bash \
		$(FULL_IMAGE)

.PHONY: test
test: ## Test the Docker image
	@echo "Testing $(FULL_IMAGE)..."
	docker run --rm \
		--gpus all \
		$(FULL_IMAGE) \
		python -c "import ray; import vllm; print('✓ Imports successful')"
	@echo "✓ Image test passed"

.PHONY: size
size: ## Show image size
	@docker images $(FULL_IMAGE) --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

.PHONY: clean
clean: ## Remove local Docker images
	docker rmi $(FULL_IMAGE) || true
	docker rmi $(REGISTRY)/$(IMAGE_NAME):$(RAY_VERSION) || true

.PHONY: prune
prune: ## Remove dangling images
	docker image prune -f

.PHONY: scan
scan: ## Scan image for vulnerabilities (requires Docker Scout or Trivy)
	@which trivy > /dev/null && trivy image $(FULL_IMAGE) || \
		echo "Install Trivy: https://github.com/aquasecurity/trivy"

.PHONY: inspect
inspect: ## Inspect Docker image layers
	docker history $(FULL_IMAGE) --no-trunc

.PHONY: shell
shell: ## Open shell in running container
	@CONTAINER_ID=$$(docker ps -q -f ancestor=$(FULL_IMAGE)) && \
	if [ -z "$$CONTAINER_ID" ]; then \
		echo "No running container found for $(FULL_IMAGE)"; \
		exit 1; \
	else \
		docker exec -it $$CONTAINER_ID bash; \
	fi

# ============================================================
# Examples
# ============================================================

.PHONY: example-build
example-build: ## Example: Build with custom registry
	$(MAKE) build REGISTRY=gcr.io/my-project TAG=v1.0.0

.PHONY: example-run-local
example-run-local: ## Example: Run with local model cache
	docker run -it --rm \
		--gpus all \
		-p 8000:8000 \
		-v $(PWD)/model_config.yaml:/app/model_config.yaml \
		-v /path/to/local/models:/mnt/models:ro \
		-e VLLM_USE_V1=1 \
		$(FULL_IMAGE)
