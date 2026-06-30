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

INSTALLABLE := quimb quspin julia itensors xdiag jax tensorcircuit-ng netket netket-gpu mpskit tenpy sse pepskit nctssos qmbcertify cpmc-lab classical-repro pdf-render node

.PHONY: skills clean help install test serve $(addprefix install-,$(INSTALLABLE))
.PHONY: zulip-whoami zulip-pull zulip-send zulip-topics zulip-messages zulip-config

help: ## Show available targets and installable tools
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Installable tools — run 'make install <name>':"
	@for t in $(INSTALLABLE); do echo "  $$t"; done

test: ## Run the Python script test suite with coverage
	python3 -m pytest scripts/tests/ -q \
		--cov=cluster_profile --cov=cluster_guardrail --cov=cluster_probe \
		--cov=parameter_scan --cov=scaling_fit \
		--cov-report=term-missing

skills: ## Install or sync Ion-managed skills
	@set -e; \
	if ! command -v ion >/dev/null 2>&1; then \
	  command -v curl >/dev/null 2>&1 || { echo "curl not found. Install Ion, then rerun: make skills"; exit 1; }; \
	  echo "Ion not found. Installing Ion."; \
	  curl -fsSL https://raw.githubusercontent.com/Roger-luo/Ion/main/install.sh | sh; \
	  export PATH="$$HOME/.local/bin:$$PATH"; \
	fi; \
	ion add

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

install-node: ## Install Node.js 18+ and npm for Context7 CLI lookups
	@set -e; \
	if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then \
	  major="$$(node -p 'Number(process.versions.node.split(".")[0])')"; \
	  if [ "$$major" -ge 18 ]; then \
	    echo "Node.js/npm already installed: $$(node --version), npm $$(npm --version)"; \
	    exit 0; \
	  fi; \
	  echo "Node.js $$(node --version) is too old; installing Node.js 18+."; \
	fi; \
	os="$$(uname -s 2>/dev/null || echo unknown)"; \
	case "$$os" in MINGW*|MSYS*|CYGWIN*) \
	  echo "Native Windows is not supported by this Makefile target. Use WSL, or install Node.js 18+ manually: https://nodejs.org/en/download"; \
	  exit 1; \
	  ;; \
	esac; \
	if command -v brew >/dev/null 2>&1; then \
	  brew install node; \
	else \
	  command -v curl >/dev/null 2>&1 || { echo "curl not found. Install Node.js 18+ manually: https://nodejs.org/en/download"; exit 1; }; \
	  command -v bash >/dev/null 2>&1 || { echo "bash not found. Install Node.js 18+ manually: https://nodejs.org/en/download"; exit 1; }; \
	  export NVM_DIR="$$HOME/.nvm"; \
	  if [ ! -s "$$NVM_DIR/nvm.sh" ]; then \
	    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh -o /tmp/nvm-install.sh; \
	    bash /tmp/nvm-install.sh; \
	  fi; \
	  . "$$NVM_DIR/nvm.sh"; \
	  nvm install --lts; \
	  nvm alias default 'lts/*'; \
	  echo "If node is not on PATH in a new shell, run: source $$NVM_DIR/nvm.sh"; \
	fi; \
	major="$$(node -p 'Number(process.versions.node.split(".")[0])')"; \
	[ "$$major" -ge 18 ] || { echo "Node.js $$(node --version) is still below 18; install Node.js 18+ manually: https://nodejs.org/en/download"; exit 1; }; \
	echo "Node.js/npm ready: $$(node --version), npm $$(npm --version)"

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
	@julia --project=julia-env -e 'using ITensors, ITensorMPS, KrylovKit, MPSKit'
	@echo "Julia/ITensors environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

install-mpskit: ## Install MPSKit.jl + MPSKitModels.jl + TensorKit.jl into julia-env/ (infinite MPS: VUMPS/IDMRG)
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["MPSKit", "MPSKitModels", "TensorKit"])'
	@julia --project=julia-env -e 'using MPSKit, MPSKitModels, TensorKit'
	@echo "MPSKit environment ready in julia-env/"
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
	@.venv/bin/python -c 'import netket, jax; print(netket.__version__, jax.devices())'
	@echo "NetKet environment ready in .venv"
	@echo "Activate with: source .venv/bin/activate"

install-netket-gpu: ## Install NetKet with CUDA-enabled JAX wheels into .venv (Linux GPU nodes)
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@[ -d .venv ] || uv venv .venv
	@uv pip install 'netket[cuda]' matplotlib
	@echo "NetKet GPU environment ready in .venv"
	@echo "Smoke test inside a GPU allocation: JAX_PLATFORM_NAME=gpu python -c 'import jax; print(jax.devices())'"

install-tenpy: ## Install TeNPy (physics-tenpy) into an isolated .venv-tenpy (Python iTEBD / MPS)
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@uv venv .venv-tenpy
	@uv pip install --python .venv-tenpy/bin/python physics-tenpy matplotlib
	@.venv-tenpy/bin/python -c 'import tenpy; print(tenpy.__version__)'
	@echo "TeNPy environment ready in .venv-tenpy (isolated venv: TeNPy pins a numpy ABI)"
	@echo "Run with: .venv-tenpy/bin/python scripts/<name>.py"

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

install-nctssos: ## Install NCTSSoS.jl + Clarabel.jl polynomial-optimization stack into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@julia --project=julia-env -e 'using NCTSSoS, Clarabel' >/dev/null 2>&1 || { cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(["NCTSSoS", "Clarabel", "Plots", "JSON"])'; }
	@julia --project=julia-env -e 'using NCTSSoS, Clarabel'
	@echo "Julia NCTSSoS polynomial-optimization environment ready in julia-env/"
	@echo "Activate with: julia --project=julia-env"

install-qmbcertify: ## Install QMBCertify.jl + Mosek structured-NPA certification stack into julia-env/
	@command -v julia >/dev/null 2>&1 || { echo "Julia not found. Run: make install julia"; exit 1; }
	@mkdir -p julia-env
	@julia --project=julia-env -e 'using QMBCertify' >/dev/null 2>&1 || { cd julia-env && julia --project=. -e 'using Pkg; Pkg.add(url="https://github.com/wangjie212/QMBCertify"); Pkg.add(["Plots", "JSON"])'; }
	@julia --project=julia-env -e 'using QMBCertify'
	@echo "Julia QMBCertify structured-NPA environment ready in julia-env/"
	@echo "Mosek needs a free academic license: set MOSEKLM_LICENSE_FILE or place ~/mosek/mosek.lic"
	@echo "Activate with: julia --project=julia-env"

install-cpmc-lab: ## Install CPMC-Lab Matlab package into .external/cpmc-lab/
	@matlab_bin="$$(command -v matlab 2>/dev/null || true)"; \
	if [ -z "$$matlab_bin" ] && [ -x /Applications/MATLAB_R2026a.app/bin/matlab ]; then matlab_bin=/Applications/MATLAB_R2026a.app/bin/matlab; fi; \
	[ -n "$$matlab_bin" ] || { echo "MATLAB not found. Put matlab on PATH or install MATLAB before CPMC-Lab."; exit 1; }; \
	command -v curl >/dev/null 2>&1 || { echo "curl not found; install curl before CPMC-Lab."; exit 1; }; \
	mkdir -p .external/downloads .external/cpmc-lab; \
	if ! find .external/cpmc-lab -name CPMC_Lab.m -print -quit | grep -q .; then \
	  curl -fsSL https://cpmc-lab.wm.edu/CPMC_Lab2.0.tar.gz -o .external/downloads/CPMC_Lab2.0.tar.gz; \
	  tar -xzf .external/downloads/CPMC_Lab2.0.tar.gz -C .external/cpmc-lab; \
	fi; \
	cpmc_file="$$(find .external/cpmc-lab -name CPMC_Lab.m -print -quit)"; \
	[ -n "$$cpmc_file" ] || { echo "CPMC_Lab.m was not found after extraction."; exit 1; }; \
	cpmc_root="$$(dirname "$$cpmc_file")"; \
	"$$matlab_bin" -batch "addpath('$$cpmc_root'); assert(exist('CPMC_Lab','file') == 2); disp('CPMC-Lab ready')"

install-classical-repro: ## Install stacks for DMRG, QMC/SSE, and CTMRG reproduction targets
	@for tool in itensors sse pepskit; do $(MAKE) install-$$tool; done
	@echo "Classical reproduction stacks ready."

install-pdf-render: ## Install PDF-to-Markdown rendering tools into .venv
	@if command -v uv >/dev/null 2>&1; then \
	  uv venv .venv; \
	  uv pip install pymupdf pymupdf4llm; \
	else \
	  command -v python3 >/dev/null 2>&1 || { echo "python3 not found. Install Python 3 first."; exit 1; }; \
	  python3 -m venv .venv; \
	  .venv/bin/python -m pip install --upgrade pip; \
	  .venv/bin/python -m pip install pymupdf pymupdf4llm; \
	fi
	@.venv/bin/python -c 'import pymupdf4llm; print("pymupdf4llm ready")'
	@echo "PDF-to-Markdown rendering tools ready in .venv"

serve: ## Serve the recommended-workflows website locally. Optional: PORT=8000
	@echo "Serving .github/template at http://localhost:$(or $(PORT),8000)/ (Ctrl-C to stop)"
	@python3 -m http.server $(or $(PORT),8000) --directory .github/template

clean: ## Remove generated HTML artifacts
	find . -name '*.html' -not -path './docs/*' -not -path './.github/*' -delete
