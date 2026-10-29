.PHONY: demo test tokens clean
demo:            ## synthetic billing data -> reports/finops-report.html (no AWS needed)
	pip install -q duckdb
	python demo/generate_sample.py
	python demo/run_demo.py
tokens:          ## AI token spend report -> reports/ai-token-report.md
	python ai-tokens/token_report.py --sample
test:            ## unit tests for the waste finder
	cd lambda/waste_finder && python -m unittest -v
clean:
	rm -rf demo/data reports/*.html reports/*.md ai-tokens/sample_usage.csv terraform/aws/.build
