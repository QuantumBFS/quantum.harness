.PHONY: setup test clean help install $(addprefix install-,$(INSTALLABLE))

INSTALLABLE := quarto quimb julia itensors

help: ## Show available targets and installable tools
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Installable tools — run 'make install <name>':"
	@for t in $(INSTALLABLE); do echo "  $$t"; done

setup: ## Minimal bootstrap — Ion + skills only
	@command -v ion >/dev/null 2>&1 || { echo "Ion not found. Install: curl -fsSL https://raw.githubusercontent.com/Roger-luo/Ion/main/install.sh | sh"; exit 1; }
	ion add
	@echo ""
	@echo "Base setup complete. Install tools as you need them:"
	@echo "  make install <tool>   (see 'make help' for the list)"

install: ## Install a specific tool on demand. Usage: make install <tool>
	@tool="$(filter-out install,$(MAKECMDGOALS))"; \
	if [ -z "$$tool" ]; then \
	  echo "Usage: make install <tool>"; \
	  echo "Installable: $(INSTALLABLE)"; exit 1; \
	fi; \
	if ! echo " $(INSTALLABLE) " | grep -q " $$tool "; then \
	  echo "Unknown tool '$$tool'. Installable: $(INSTALLABLE)"; exit 1; \
	fi; \
	$(MAKE) install-$$tool

$(INSTALLABLE):
	@:

install-quarto: ## Install Quarto + TinyTeX for content rendering
	@command -v quarto >/dev/null && echo "Quarto already installed" || { echo "Install Quarto: https://quarto.org/docs/get-started/"; exit 1; }
	@quarto install tinytex --no-prompt 2>/dev/null || true

install-quimb: ## Install quimb + numerical deps into .venv (Python fallback stack)
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv venv .venv
	@uv pip install quimb cotengra autoray opt_einsum numpy scipy matplotlib jupyter ipykernel
	@echo "quimb environment ready in .venv"

install-julia: ## Install Julia via juliaup (default harness language)
	@command -v julia >/dev/null && { echo "Julia already installed: $$(julia --version)"; exit 0; } || true
	@command -v juliaup >/dev/null 2>&1 && { juliaup add release; juliaup default release; } || \
	  curl -fsSL https://install.julialang.org -o /tmp/juliaup-install.sh && \
	  sh /tmp/juliaup-install.sh --yes
	@echo "Julia installed. You may need to open a new shell for PATH changes."

install-itensors: ## Install ITensors.jl + ITensorMPS.jl + KrylovKit.jl into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["ITensors", "ITensorMPS", "KrylovKit", "MPSKit"])'
	@echo "Julia/ITensors environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

render: ## Render a markdown file to HTML. Usage: make render FILE=<path.md>
	@if [ -z "$(FILE)" ]; then echo "Usage: make render FILE=<path.md>"; exit 1; fi
	tools/cli/render "$(FILE)"

clean: ## Remove generated HTML artifacts
	find . -name '*.html' -not -path './templates/*' -delete
