.PHONY: demo test tokens k8s all clean setup
# Windows: make PY=python
PY ?= python3
setup:           ## local venv with the 2 Python deps
	$(PY) -m venv .venv && .venv/bin/pip install -q duckdb pyyaml && echo "now: source .venv/bin/activate"
demo:            ## synthetic billing data -> reports/finops-report.html (no AWS needed)
	$(PY) demo/generate_sample.py
	$(PY) demo/run_demo.py
tokens:          ## AI token spend report -> reports/ai-token-report.md
	$(PY) ai-tokens/token_report.py --sample
k8s:             ## Kubernetes allocation on a synthetic cluster -> reports/k8s-allocation.md
	$(PY) k8s/allocate.py
test:            ## unit tests
	cd lambda/waste_finder && $(PY) -m unittest -v
	cd k8s && $(PY) -m unittest -v
all: test demo tokens k8s
clean:
	rm -rf demo/data reports/*.html reports/*.md ai-tokens/sample_usage.csv terraform/aws/.build
