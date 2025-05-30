# Container-Based Testing Implementation for LISA

## Summary

This implementation adds container-based testing capabilities to LISA with minimal changes to the existing framework. The design follows LISA's patterns and architecture while providing flexible container testing options.

## Key Components Implemented

### 1. DockerAdvanced Tool (`lisa/tools/docker_advanced.py`)

An extended Docker tool that provides advanced container capabilities:

- **Advanced container execution** with support for:
  - Privileged mode
  - Volume mounting (including host root filesystem)
  - Environment variables
  - Network modes
  - Resource limits (CPU, memory)
  - Security options
  - Linux capabilities management
  
- **Container lifecycle management**:
  - Pull images from registries with authentication
  - Create, start, stop, and remove containers
  - Execute commands in running containers
  - Container logging and inspection

### 2. Container Test Suite Base Class (`lisa/container_testsuite.py`)

Provides base functionality for container-based test suites:

- **ContainerTestConfig**: Configuration dataclass for container settings
- **ContainerTestSuite**: Base class for test suites running in containers
- **ContainerExecutor**: Context manager for long-running container operations
- **@container_test**: Decorator to mark individual test cases for container execution

### 3. Example Test Suite (`examples/testsuites/container_example.py`)

Demonstrates various container testing patterns:

- Basic container command execution
- Long-running container operations with state persistence
- Custom container configurations
- Privileged operations and system-level testing
- Host filesystem access
- Using the @container_test decorator

### 4. Container Runner Mixin (`lisa/container_runner_mixin.py`)

Provides automatic container test detection and execution:

- Detects tests marked with @container_test decorator
- Automatically wraps test methods to run in containers
- Redirects node execution commands to container
- Adds container information to test results

## Usage Patterns

### Pattern 1: Inheriting from ContainerTestSuite

```python
@TestSuiteMetadata(...)
class MyContainerTests(ContainerTestSuite):
    def _get_container_config(self) -> ContainerTestConfig:
        return ContainerTestConfig(
            image="ubuntu:22.04",
            privileged=True,
            mount_host_root=True,
        )
    
    @TestCaseMetadata(...)
    def test_in_container(self, node: Node, log: Logger) -> None:
        # Run command in container
        result = self._run_in_container(node, "uname -a", log)
        assert_that(result.exit_code).is_equal_to(0)
```

### Pattern 2: Using ContainerExecutor

```python
def test_with_executor(self, node: Node, log: Logger) -> None:
    with self._create_container_executor(node, log) as executor:
        # Multiple commands in same container
        executor.run("apt-get update")
        executor.run("apt-get install -y curl")
        result = executor.run("curl --version")
```

### Pattern 3: Using @container_test Decorator

```python
@TestCaseMetadata(...)
@container_test(
    image="python:3.9",
    privileged=False,
    environment={"PYTHONDONTWRITEBYTECODE": "1"},
)
def test_python_app(self, node: Node, log: Logger) -> None:
    # Test automatically runs in specified container
    result = node.execute("python --version")
```

## Key Features

1. **Minimal Framework Changes**: 
   - Only adds new components without modifying existing code
   - Follows LISA's tool and test suite patterns
   - Compatible with existing test infrastructure

2. **Flexible Container Configuration**:
   - Support for any container image
   - Registry authentication
   - Privileged mode for system testing
   - Host filesystem mounting
   - Custom volumes and environment variables
   - Resource limits and security options

3. **Multiple Usage Patterns**:
   - Inheritance-based approach for test suites
   - Decorator-based approach for individual tests
   - Direct tool usage for maximum control

4. **Container Lifecycle Management**:
   - Automatic image pulling
   - Container creation and cleanup
   - Long-running containers for stateful tests
   - Proper error handling and logging

## Integration Points

1. **Tools System**: DockerAdvanced integrates as a standard LISA tool
2. **Test Framework**: ContainerTestSuite extends the standard TestSuite
3. **Node Execution**: Container execution transparently replaces node execution
4. **Result Reporting**: Container information added to test results

## Security Considerations

1. **Privileged Containers**: Use with caution, only when necessary
2. **Host Filesystem Access**: Mount read-only when possible
3. **Container Cleanup**: Automatic cleanup prevents resource leaks
4. **Registry Credentials**: Handle securely, don't log passwords

## Performance Considerations

1. **Image Caching**: Images are cached locally after first pull
2. **Container Reuse**: ContainerExecutor allows reusing containers
3. **Parallel Execution**: Each test can run in its own container
4. **Resource Limits**: Prevent containers from consuming all resources

## Future Enhancements

1. **Framework Integration**: Deeper integration with LISA runner
2. **Container Composition**: Support for multi-container scenarios
3. **Kubernetes Support**: Run tests in K8s pods
4. **Image Building**: Build test images on-demand
5. **Result Collection**: Enhanced artifact collection from containers

## Example Test Scenarios

### System Testing
```python
# Test kernel modules in privileged container
with ContainerExecutor(node, privileged_config, log) as executor:
    executor.run("modprobe dummy")
    executor.run("lsmod | grep dummy")
```

### Application Testing
```python
# Test application in isolated environment
result = self._run_in_container(
    node,
    "cd /app && python -m pytest tests/",
    log,
)
```

### Cross-Distribution Testing
```python
# Test on different Linux distributions
for image in ["ubuntu:22.04", "centos:8", "debian:11"]:
    config = ContainerTestConfig(image=image)
    with ContainerExecutor(node, config, log) as executor:
        executor.run("./test_script.sh")
```

## Conclusion

This implementation provides a clean, flexible way to run tests inside containers with minimal changes to the LISA framework. It supports various testing scenarios from simple command execution to complex system-level testing with privileged containers and host filesystem access.