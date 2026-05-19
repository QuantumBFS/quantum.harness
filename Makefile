# Zulip bridge for the quantum many-body harness - connects to ManyBodyHarness
# on https://zulip.hkust-gz.edu.cn. Archive lands under .zulip/ in the repo and is
# gitignored locally so it never round-trips to GitHub.
#
# On a fresh clone this directory does not exist. The onboard skill creates it
# after the user downloads zuliprc from https://zulip.hkust-gz.edu.cn. Override
# ZULIP_CONFIG_DIR only if you keep that private API key file somewhere else.

ZULIP_STREAM            := ManyBodyHarness
ZULIP_SITE              := https://zulip.hkust-gz.edu.cn
ZULIP_CONFIG_DIR_DEFAULT := $(HOME)/.config/zlp-harness/hkust-gz
ZULIP_CONFIG_DIR         ?= $(ZULIP_CONFIG_DIR_DEFAULT)
ZULIP_LOCAL             := $(CURDIR)/.zulip

export ZULIP_CONFIG_FILE := $(ZULIP_CONFIG_DIR)/zuliprc
export ZLP_ARCHIVE_ROOT  := $(ZULIP_LOCAL)
export ZLP_RUN_ROOT      := $(ZULIP_LOCAL)/.run

ZLP := zlp

.PHONY: setup core core-setup skills doctor install-flow test test-flow clean help install $(addprefix install-,$(INSTALLABLE))
.PHONY: zulip-whoami zulip-pull zulip-send zulip-topics zulip-messages zulip-config

INSTALLABLE := quarto quimb quspin julia itensors xdiag jax tensorcircuit-ng netket netket-gpu sse pepskit classical-repro

help: ## Show available targets and installable tools
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Installable tools — run 'make install <name>':"
	@for t in $(INSTALLABLE); do echo "  $$t"; done

setup: core ## Minimal bootstrap — core CLI tools only

core: install-flow ## Build core harness CLI tools

core-setup: core ## Backward-compatible alias for core

skills: ## Install or sync Ion-managed skills
	@set -e; \
	if ! command -v ion >/dev/null 2>&1; then \
	  command -v curl >/dev/null 2>&1 || { echo "curl not found. Install Ion, then rerun: make skills"; exit 1; }; \
	  echo "Ion not found. Installing Ion."; \
	  curl -fsSL https://raw.githubusercontent.com/Roger-luo/Ion/main/install.sh | sh; \
	  export PATH="$$HOME/.local/bin:$$PATH"; \
	fi; \
	ion add

doctor: ## Check core harness readiness without installing domain stacks
	@missing=0; \
	if tools/cli/flow help >/dev/null 2>&1; then echo "flow	ok"; else echo "flow	missing"; missing=1; fi; \
	if cargo --version >/dev/null 2>&1; then echo "cargo	ok"; elif command -v cargo >/dev/null 2>&1; then echo "cargo	broken"; else echo "cargo	missing"; fi; \
	if command -v ion >/dev/null 2>&1; then echo "ion	ok"; else echo "ion	missing"; fi; \
	exit $$missing

install-flow: ## Build the generic workflow gate ledger CLI
	@set -e; \
	. "$$HOME/.cargo/env" 2>/dev/null || true; \
	if ! cargo --version >/dev/null 2>&1; then \
	  command -v curl >/dev/null 2>&1 || { echo "curl not found. Install Rust/Cargo, then rerun: make setup"; exit 1; }; \
	  echo "Cargo not usable. Installing Rust/Cargo via rustup."; \
	  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y; \
	  . "$$HOME/.cargo/env"; \
	fi; \
	cargo build --release --manifest-path tools/flow/Cargo.toml; \
	tools/cli/flow help >/dev/null; \
	echo "flow CLI ready: tools/cli/flow"

# Stable KEY=VALUE contract for the zlp-harness plugin's zlp-onboard skill.
# Adding new keys is additive; older skill versions ignore unknown lines.
zulip-config: ## Show Zulip bridge configuration
	@echo "ZULIP_SITE=$(ZULIP_SITE)"
	@echo "ZULIP_STREAM=$(ZULIP_STREAM)"
	@echo "ZULIP_CONFIG_DIR_DEFAULT=$(ZULIP_CONFIG_DIR_DEFAULT)"

zulip-whoami: ## Verify Zulip credentials for this harness
	$(ZLP) whoami

zulip-topics: ## List topics in the configured Zulip stream
	$(ZLP) topics --stream "$(ZULIP_STREAM)"

zulip-messages: ## Show Zulip messages. Optional: TOPIC=<name> LIMIT=50 FORMAT=md
	$(ZLP) messages --stream "$(ZULIP_STREAM)" $(if $(TOPIC),--topic "$(TOPIC)") --limit "$(or $(LIMIT),50)" --format "$(or $(FORMAT),md)"

zulip-pull: ## Mirror Zulip messages into .zulip/. Optional: TOPIC=<name> IMPORT_HISTORY=1
	$(ZLP) pull --stream "$(ZULIP_STREAM)" $(if $(TOPIC),--topic "$(TOPIC)") $(if $(IMPORT_HISTORY),--import-history)

zulip-send: ## Send a Zulip message. Required: TOPIC=<name> and MSG=... or MSG_FILE=...
	@test -n "$(TOPIC)" || { echo "TOPIC=... required"; exit 1; }
	@test -n "$(MSG)$(MSG_FILE)" || { echo "MSG=... or MSG_FILE=... required"; exit 1; }
	$(ZLP) send --stream "$(ZULIP_STREAM)" --topic "$(TOPIC)" \
	  $(if $(MSG),--msg "$(MSG)") $(if $(MSG_FILE),--msg-file "$(MSG_FILE)")

DOMAIN_TOOLS := julia itensors

domain-setup: ## Install the full domain stack (Julia + ITensors ecosystem)
	@for tool in $(DOMAIN_TOOLS); do $(MAKE) install-$$tool; done
	@echo ""
	@echo "Domain stack ready."

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

install-quspin: ## Install QuSpin exact diagonalization fallback stack into .venv
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv venv .venv
	@uv pip install quspin numpy scipy matplotlib
	@.venv/bin/python -c 'import quspin; print(quspin.__version__)'
	@echo "QuSpin environment ready in .venv"

install-julia: ## Install Julia via juliaup (default harness language)
	@command -v julia >/dev/null && { echo "Julia already installed: $$(julia --version)"; exit 0; } || true
	@command -v juliaup >/dev/null 2>&1 && { juliaup add release; juliaup default release; } || \
	  curl -fsSL https://install.julialang.org -o /tmp/juliaup-install.sh && \
	  sh /tmp/juliaup-install.sh --yes
	@echo "Julia installed. You may need to open a new shell for PATH changes."

install-itensors: ## Install ITensors.jl + ITensorMPS.jl + KrylovKit.jl into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["ITensors", "ITensorMPS", "KrylovKit", "MPSKit", "Plots"])'
	@echo "Julia/ITensors environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

install-xdiag: ## Install XDiag.jl exact diagonalization stack into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@julia --project=julia-env -e 'using XDiag' >/dev/null 2>&1 || { cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["XDiag"])'; }
	@julia --project=julia-env -e 'using XDiag'
	@echo "XDiag environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

install-jax: ## Install JAX into .venv. Optional: EXTRA=cpu|cuda12|cuda13|cuda12-local|cuda13-local
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@[ -d .venv ] || uv venv .venv
	@extra="$(or $(EXTRA),cpu)"; \
	if [ "$$extra" = "cpu" ]; then \
	  .venv/bin/python -c 'import jax' >/dev/null 2>&1 || uv pip install jax; \
	else \
	  uv pip install "jax[$$extra]"; \
	fi
	@.venv/bin/python -c 'import jax; print(jax.devices())'
	@echo "JAX environment ready in .venv"
	@echo "For GPU extras, run the GPU smoke inside a compute allocation: JAX_PLATFORM_NAME=gpu .venv/bin/python -c 'import jax; print(jax.devices())'"

install-tensorcircuit-ng: ## Install TensorCircuit-NG after JAX has been installed and smoke-tested
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@.venv/bin/python -c 'import jax; print(jax.devices())' || { echo "JAX is required first. Run: make install jax EXTRA=cpu"; exit 1; }
	@.venv/bin/python -c 'import tensorcircuit, cotengra, psutil, matplotlib' >/dev/null 2>&1 || uv pip install tensorcircuit-ng cotengra psutil matplotlib
	@.venv/bin/python -c 'import tensorcircuit as tc; tc.set_backend("jax"); tc.about()'
	@echo "TensorCircuit-NG environment ready in .venv"

install-netket: ## Install NetKet + JAX for VMC / neural quantum states into .venv
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@[ -d .venv ] || uv venv .venv
	@uv pip install netket jax jaxlib flax optax matplotlib
	@echo "NetKet environment ready in .venv"
	@echo "Activate with: source .venv/bin/activate"

install-netket-gpu: ## Install NetKet with CUDA-enabled JAX wheels into .venv (Linux GPU nodes)
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@[ -d .venv ] || uv venv .venv
	@uv pip install 'netket[cuda]' matplotlib
	@echo "NetKet GPU environment ready in .venv"
	@echo "Smoke test inside a GPU allocation: JAX_PLATFORM_NAME=gpu python -c 'import jax; print(jax.devices())'"

install-sse: ## Install Julia SSE QMC stack into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["Carlo", "StochasticSeriesExpansion", "DataFrames", "Plots", "JSON"])'
	@echo "Julia SSE QMC environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

install-pepskit: ## Install PEPSKit.jl + TensorKit.jl CTMRG stack into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["PEPSKit", "TensorKit", "QuadGK", "Plots"])'
	@echo "Julia PEPSKit/CTMRG environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

install-classical-repro: ## Install stacks for DMRG, QMC/SSE, and CTMRG reproduction targets
	@for tool in itensors sse pepskit; do $(MAKE) install-$$tool; done
	@echo "Classical reproduction stacks ready."

render: ## Render a markdown file to HTML. Usage: make render FILE=<path.md>
	@if [ -z "$(FILE)" ]; then echo "Usage: make render FILE=<path.md>"; exit 1; fi
	tools/cli/render "$(FILE)"

test-flow: ## Test the generic workflow gate ledger
	cargo test --manifest-path tools/flow/Cargo.toml

clean: ## Remove generated HTML artifacts
	find . -name '*.html' -not -path './tools/templates/*' -delete
