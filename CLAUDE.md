# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LISA (Linux Integration Services Automation) is a Linux quality validation system designed to test Linux kernels and distributions across multiple platforms (Azure, AWS, HyperV, Libvirt, bare metal). It provides both a test framework and a comprehensive suite of tests.

## Common Development Commands

### Environment Setup
```bash
# Install nox for development workflow
pip3 install nox toml

# Create/update development virtual environment
nox -vs dev                  # Default: Azure + Libvirt (on Linux)
nox -vs dev -- azure         # Azure only
nox -vs dev -- azure aws     # Multiple platforms

# Activate virtual environment
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate.ps1   # Windows PowerShell
```

### Running Tests
```bash
# Run unit tests
nox -vs test
python -m unittest discover

# Run a specific test file
python -m unittest selftests.test_environment

# Run LISA with example configuration
lisa

# Run with specific runbook
lisa -r ./microsoft/runbook/azure.yml -v subscription_id:<id>

# Run container-based tests
lisa -r ./run_container_tests.yml
```

### Code Quality Commands
```bash
# Run all checks before committing
nox -vt all

# Individual checks
nox -vs black     # Format code
nox -vs isort     # Sort imports
nox -vs flake8    # Lint code
nox -vs mypy      # Type checking
nox -vs pylint    # Additional linting

# Format code (auto-fix)
nox -vt format    # Runs black and isort

# Build documentation
nox -vs docs
```

## High-Level Architecture

### Core Components

1. **Platform Abstraction** (`lisa/platform_.py`, `lisa/sut_orchestrator/`)
   - Base `Platform` class provides interface for environment management
   - Implementations: Azure, AWS, Libvirt (QEMU/Cloud Hypervisor), HyperV, Baremetal, Ready
   - Handles environment creation, deployment, deletion
   - Declares platform-specific features

2. **Test Framework**
   - **TestSuite** (`lisa/testsuite.py`): Base class for test collections
   - **TestCaseMetadata**: Decorator for test methods with requirements/metadata
   - **TestSelector** (`lisa/testselector.py`): Discovers and filters tests
   - **Runners** (`lisa/runners/`): Orchestrate test execution
     - `LisaRunner`: Main runner for LISA test suites
     - `LegacyRunner`: Supports older test formats

3. **Node Abstraction** (`lisa/node.py`)
   - Represents test targets (VMs, containers, physical machines)
   - Provides unified interface for shell commands, file operations
   - Supports local and remote (SSH) nodes
   - Manages tool installation and execution

4. **Tool System** (`lisa/executable.py`, `lisa/tools/`)
   - Abstraction for executables/utilities on nodes
   - 100+ pre-defined tools (git, make, systemctl, etc.)
   - Auto-installation based on distro
   - Cross-platform command variations

5. **Feature System** (`lisa/feature.py`, `lisa/features/`)
   - Platform-specific capabilities (GPU, SerialConsole, Hibernation)
   - Platforms implement feature interfaces
   - Tests declare required features
   - Enables platform-agnostic test writing

6. **Environment Management** (`lisa/environment.py`)
   - Groups nodes into test environments
   - Lifecycle: New → Prepared → Deployed → Connected → Deleted
   - Capability-based matching with test requirements

### Test Execution Flow

1. **Discovery**: TestSelector finds all TestSuite classes and @TestCaseMetadata methods
2. **Filtering**: Apply filters (area, category, tags, priority)
3. **Planning**: Match tests to environments based on requirements
4. **Execution**: 
   - Platform prepares/deploys environments
   - Tests run in matched environments
   - Tools installed on-demand
   - Results collected via notifier system
5. **Cleanup**: Environments deleted (unless preserve_environment set)

### Supporting Systems

- **Transformers** (`lisa/transformers/`): Modify configuration at different phases
- **Combinators** (`lisa/combinators/`): Generate test matrices from variables
- **Notifiers** (`lisa/notifiers/`): Plugin system for results/notifications
- **Search Space** (`lisa/search_space.py`): Capability requirement matching

## Test Organization

Tests are organized in `microsoft/testsuites/` by functional area:
- `core/`: Basic VM functionality
- `network/`: Networking tests (synthetic, SRIOV)
- `storage/`: Disk and storage tests
- `cpu/`: CPU and performance tests
- `gpu/`: GPU-specific tests
- Platform-specific tests in respective directories

## Key Concepts

- **Runbook**: YAML configuration defining platforms, test selection, variables
- **Node Capability**: Hardware/software specifications (CPU, memory, features)
- **Test Requirement**: Minimum capabilities needed by a test
- **Search Space**: Algorithm matching requirements to available capabilities
- **Message Bus**: Event-driven communication between components

## Container-Based Testing

LISA supports running tests inside containers for better isolation and dependency management:

```python
# Use ContainerTestSuite base class
from lisa.container_testsuite import ContainerTestConfig, ContainerTestSuite

class MyTests(ContainerTestSuite):
    def _get_container_config(self) -> ContainerTestConfig:
        return ContainerTestConfig(
            image="ubuntu:22.04",
            privileged=True,
            mount_host_root=True
        )

# Or use decorator
from lisa.container_testsuite import container_test

@container_test(image="alpine:latest", privileged=False)
def test_in_container(self, node: Node, log: Logger) -> None:
    # Commands run inside container
    pass
```

Key features:
- All test dependencies contained in image
- Privileged mode support for system tests
- Host filesystem mounting for inspection
- Container registry integration
- Automatic cleanup

See `docs/container_testing.md` for detailed documentation.
