.PHONY: demo test tokens k8s all clean
demo:            ## synthetic billing data -> reports/finops-report.html (no AWS needed)
	pip install -q duckdb
	python demo/generate_sample.py
	python demo/run_demo.py
tokens:          ## AI token spend report -> reports/ai-token-report.md
	python ai-tokens/token_report.py --sample
k8s:             ## Kubernetes allocation on a synthetic cluster -> reports/k8s-allocation.md
	python k8s/allocate.py
test:            ## unit tests
	cd lambda/waste_finder && python -m unittest -v
	cd k8s && python -m unittest -v
all: test demo tokens k8s
clean:
	rm -rf demo/data reports/*.html reports/*.md ai-tokens/sample_usage.csv terraform/aws/.build
