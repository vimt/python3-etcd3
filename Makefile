.PHONY: test test-unit test-cluster test-cov install-dev genproto lint format clean build upload upload-test verify help

# 安装开发依赖
install-dev:
	python -m pip install -e ".[dev]"
	python -m pip install pifpaf

PIFPAF_CLUSTER = PYTHON_ETCD_HTTP_URL=http://127.0.0.1:2479 pifpaf run etcd --cluster --port 2479 --peer-port 2480 --

# 只跑不需要 etcd 的单元测试
test-unit:
	python -m pytest tests/ -m "not integration" -v

# 使用 pifpaf 起 3 节点 etcd 集群运行所有测试（需要 PATH 里有 etcd）
test-cluster:
	$(PIFPAF_CLUSTER) python -m pytest tests/ -v --timeout=120

# 运行所有测试（使用当前环境的 etcd，PYTHON_ETCD_HTTP_URL 或 localhost:2379）
# 注意：failover / members 测试需要 pifpaf 集群，请优先用 test-cluster
test:
	python -m pytest tests/ -v --timeout=120

# 在 pifpaf 集群上运行测试并生成覆盖率报告
test-cov:
	$(PIFPAF_CLUSTER) python -m pytest tests/ --timeout=120 --cov=etcd3 --cov-report=html --cov-report=term-missing

# 重新生成 etcd3/etcdrpc/ 下的 protobuf 代码与类型存根（需在装了 PROTO_GEN_DEPS 的 venv 中运行）
# - grpcio-tools 1.69 内置的 protoc 对应 protobuf 5.29，即 pyproject 声明的下限
# - mypy-protobuf 3.6 生成 rpc_pb2_grpc.pyi（gRPC stub 的类型）；4.x 起要求 protobuf>=6
# - rpc_pb2_grpc.py 刻意不重新生成：新版 grpc_tools 的输出会在 import 时强制
#   grpcio>=生成版本，现有文件不带这个限制
PROTO_GEN_DEPS = "grpcio-tools==1.69.*" "mypy-protobuf==3.6.*" ruff
PROTOS = etcd3/proto/rpc.proto etcd3/proto/auth.proto etcd3/proto/kv.proto

genproto:
	python -m grpc_tools.protoc -Ietcd3/proto \
		--python_out=etcd3/etcdrpc --pyi_out=etcd3/etcdrpc --mypy_grpc_out=etcd3/etcdrpc \
		$(PROTOS)
	rm -f etcd3/etcdrpc/auth_pb2_grpc.pyi etcd3/etcdrpc/kv_pb2_grpc.pyi
	sed -i -E 's/^import (rpc_pb2|kv_pb2|auth_pb2)( as .*)?$$/from . import \1\2/' \
		etcd3/etcdrpc/*_pb2.py etcd3/etcdrpc/*.pyi
	python -m ruff format etcd3/etcdrpc

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
	@echo "  test-cluster    - Run all tests on a 3-node pifpaf etcd cluster"
	@echo "  test            - Run all tests against the current etcd"
	@echo "  test-cov        - Run all tests on a pifpaf cluster with coverage"
	@echo "  genproto        - Regenerate etcd3/etcdrpc from etcd3/proto"
	@echo "  format          - Format code with ruff"
	@echo "  lint            - Run code quality checks"
	@echo "  build           - Build distribution packages"
	@echo "  clean           - Clean build artifacts"
	@echo "  upload          - Upload to PyPI"
	@echo "  upload-test     - Upload to TestPyPI"
	@echo "  verify          - Verify package can be imported"