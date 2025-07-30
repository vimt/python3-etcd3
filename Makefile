.PHONY: test test-unit test-integration install-dev lint format clean build

# 安装开发依赖
install-dev:
	python -m pip install -e ".[dev]"

# 运行单元测试（不需要 etcd 服务器）
test-unit:
	python -m pytest tests/ -k "not TestEtcd3 and not TestAlarms and not TestFailoverClient and not test_user_pwd_auth and not test_compact" -v

# 运行集成测试（需要 etcd 服务器）
test-integration:
	python -m pytest tests/ -k "TestEtcd3 or TestAlarms or TestFailoverClient" -v

# 运行所有测试
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