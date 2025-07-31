.PHONY: test test-unit test-integration test-cluster install-dev lint format clean build pifpaf-start pifpaf-stop pifpaf-status

# 安装开发依赖
install-dev:
	python -m pip install -e ".[dev]"
	python -m pip install pifpaf

# 使用 pifpaf 集群运行所有测试
test-cluster:
	@echo "Running tests with pifpaf etcd cluster..."
	PYTHON_ETCD_HTTP_URL=http://127.0.0.1:2479 pifpaf run etcd --cluster --port 2479 --peer-port 2480 -- python -m pytest tests/ -v
	@echo "Tests completed, cluster automatically stopped"

# 运行所有测试（使用当前环境的 etcd）
test:
	python -m pytest tests/ -v

# 运行测试并生成覆盖率报告
test-cov:
	python -m pytest tests/ --cov=etcd3 --cov-report=html --cov-report=term-missing

# 代码格式化
format:
	python -m ruff format etcd3/ tests/

# 代码检查
lint:
	python -m ruff check etcd3/ tests/
	python -m mypy etcd3/

# 构建分发包
build:
	python -m build

# 清理构建文件
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete

# 上传到 PyPI（需要先配置认证）
upload:
	python -m twine upload dist/*

# 上传到 TestPyPI
upload-test:
	python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

# 验证包安装
verify:
	python -c "import etcd3; print('etcd3 version:', etcd3.__version__); print('Import successful!')"

help:
	@echo "Available targets:"
	@echo "  install-dev     - Install development dependencies"
	@echo "  test-unit       - Run unit tests (no etcd server required)"
	@echo "  test-integration- Run integration tests (requires etcd server)"
	@echo "  test            - Run all tests"
	@echo "  test-cov        - Run tests with coverage report"
	@echo "  format          - Format code with ruff"
	@echo "  lint            - Run code quality checks"
	@echo "  build           - Build distribution packages"
	@echo "  clean           - Clean build artifacts"
	@echo "  upload          - Upload to PyPI"
	@echo "  upload-test     - Upload to TestPyPI"
	@echo "  verify          - Verify package can be imported"