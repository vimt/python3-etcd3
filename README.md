# python3-etcd3

A Python client library for etcd version 3, modernized for Python 3.8+.

## About This Project

**This project is a Python 3 modernization of [kragniz/python-etcd3](https://github.com/kragniz/python-etcd3).** 

The original project has not been actively maintained and had compatibility issues with newer Python versions and gRPC. This fork provides:

- **Python 3.8+ compatibility** (removed Python 2 support)
- **Modern Python syntax** with type annotations
- **Updated gRPC compatibility** for newer versions
- **Modern packaging** with pyproject.toml
- **Code quality improvements** with ruff formatting

**Credit**: All core functionality and original implementation credit goes to [Louis Taylor](https://github.com/kragniz) and the original contributors of python-etcd3.

## Features

- Full etcd3 API support via gRPC
- Asynchronous operations  
- Distributed locking
- Key watching capabilities
- Lease management
- Transaction support
- Cluster management

## Installation

```bash
pip install python3-etcd3
```

## Quick Start

```python
import etcd3

etcd = etcd3.client()

# Put a key
etcd.put('key', 'value')

# Get a key
value, metadata = etcd.get('key')
print(value)

# Watch for changes
watch_iterator, cancel = etcd.watch('key')
for event in watch_iterator:
    print(event)
```

## Requirements

- Python 3.8+
- grpcio
- protobuf

## Contributing

This project focuses on maintaining Python 3 compatibility and modern Python practices. For major feature additions, please consider contributing to the [original project](https://github.com/kragniz/python-etcd3) first.

## License

Apache License 2.0 (same as original project)