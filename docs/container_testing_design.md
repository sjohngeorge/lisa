# Container-Based Testing Framework Design for LISA

## Overview

This document outlines the design for integrating container-based testing capabilities into LISA (Linux Integration Test Automation). The goal is to enable running test code inside containers on remote nodes with minimal changes to the existing framework.

## Key Requirements

1. **Privileged Mode Support**: Tests may need to run in privileged containers to access system resources
2. **Root Filesystem Mounting**: Containers need access to the host's root filesystem for system-level testing
3. **Container Registry Support**: Ability to pull container images from registries
4. **Minimal Framework Changes**: Leverage existing LISA architecture and patterns

## Architecture Design

### 1. Container Tool Extension

Extend the existing `Docker` tool class to support more advanced container operations:

```python
class DockerAdvanced(Docker):
    """Extended Docker tool with advanced container capabilities"""
    
    def run_in_container(
        self,
        image: str,
        command: str,
        privileged: bool = False,
        volumes: Optional[Dict[str, str]] = None,
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        network_mode: Optional[str] = None,
        remove: bool = True,
        detach: bool = False,
        name: Optional[str] = None,
    ) -> ExecutableResult:
        """Run a command inside a container with advanced options"""
        pass
    
    def pull_image(
        self,
        image: str,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Pull container image from a registry"""
        pass
```

### 2. Container Test Suite Base Class

Create a base class for container-based test suites:

```python
@dataclass
class ContainerTestConfig:
    """Configuration for container-based tests"""
    image: str
    registry: Optional[str] = None
    privileged: bool = False
    mount_host_root: bool = False
    volumes: Dict[str, str] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    network_mode: str = "bridge"

class ContainerTestSuite(TestSuite):
    """Base class for test suites that run tests inside containers"""
    
    def __init__(self, metadata: TestSuiteMetadata):
        super().__init__(metadata)
        self._container_config: Optional[ContainerTestConfig] = None
    
    @property
    def container_config(self) -> ContainerTestConfig:
        """Override this property to provide container configuration"""
        if not self._container_config:
            self._container_config = self._get_container_config()
        return self._container_config
    
    def _get_container_config(self) -> ContainerTestConfig:
        """Override this method to provide container configuration"""
        raise NotImplementedError()
    
    def _prepare_container(self, node: Node) -> None:
        """Prepare the container environment on the node"""
        docker = node.tools[DockerAdvanced]
        config = self.container_config
        
        # Pull the image if needed
        docker.pull_image(
            image=config.image,
            registry=config.registry
        )
        
        # Set up volumes
        if config.mount_host_root:
            config.volumes["/host"] = "/"
    
    def _run_in_container(
        self,
        node: Node,
        command: str,
        **kwargs: Any
    ) -> ExecutableResult:
        """Execute a command inside the container"""
        docker = node.tools[DockerAdvanced]
        config = self.container_config
        
        return docker.run_in_container(
            image=config.image,
            command=command,
            privileged=config.privileged,
            volumes=config.volumes,
            environment=config.environment,
            network_mode=config.network_mode,
            **kwargs
        )
```

### 3. Container Test Case Decorator

Create a decorator to mark test cases that should run in containers:

```python
def container_test(
    image: Optional[str] = None,
    privileged: bool = False,
    mount_host_root: bool = False,
    volumes: Optional[Dict[str, str]] = None,
    environment: Optional[Dict[str, str]] = None,
) -> Callable:
    """Decorator to mark a test case to run inside a container"""
    def decorator(func: Callable) -> Callable:
        # Store container configuration in function attributes
        func._container_config = {
            "image": image,
            "privileged": privileged,
            "mount_host_root": mount_host_root,
            "volumes": volumes or {},
            "environment": environment or {},
        }
        return func
    return decorator
```

### 4. Container Execution Wrapper

Create a wrapper to handle container execution transparently:

```python
class ContainerExecutor:
    """Handles execution of commands inside containers"""
    
    def __init__(self, node: Node, config: ContainerTestConfig):
        self.node = node
        self.config = config
        self.docker = node.tools[DockerAdvanced]
        self._container_name: Optional[str] = None
    
    def __enter__(self) -> "ContainerExecutor":
        """Start a long-running container for test execution"""
        self._container_name = f"lisa_test_{uuid.uuid4().hex[:8]}"
        self.docker.run_in_container(
            image=self.config.image,
            command="sleep infinity",  # Keep container running
            name=self._container_name,
            detach=True,
            privileged=self.config.privileged,
            volumes=self.config.volumes,
            environment=self.config.environment,
            remove=False,
        )
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Clean up the container"""
        if self._container_name:
            self.docker.remove_container(self._container_name, force=True)
    
    def run(self, command: str, **kwargs: Any) -> ExecutableResult:
        """Execute a command in the running container"""
        return self.docker.exec_in_container(
            container=self._container_name,
            command=command,
            **kwargs
        )
```

## Usage Examples

### Example 1: Simple Container Test Suite

```python
@TestSuiteMetadata(
    area="container",
    category="functional",
    description="Example container-based test suite",
)
class MyContainerTests(ContainerTestSuite):
    def _get_container_config(self) -> ContainerTestConfig:
        return ContainerTestConfig(
            image="ubuntu:latest",
            privileged=True,
            mount_host_root=True,
        )
    
    @TestCaseMetadata(description="Test system calls in container")
    def test_system_calls(self, node: Node, log: Logger) -> None:
        # This runs inside the container
        result = self._run_in_container(
            node,
            "uname -a"
        )
        log.info(f"Container kernel: {result.stdout}")
        
        # Access host filesystem through /host mount
        result = self._run_in_container(
            node,
            "ls -la /host/etc"
        )
        assert_that(result.exit_code).is_equal_to(0)
```

### Example 2: Using Container Test Decorator

```python
@TestSuiteMetadata(
    area="container",
    category="functional",
    description="Decorator-based container tests",
)
class DecoratorContainerTests(TestSuite):
    @TestCaseMetadata(description="Run test in privileged container")
    @container_test(
        image="alpine:latest",
        privileged=True,
        mount_host_root=True,
    )
    def test_with_decorator(self, node: Node, log: Logger) -> None:
        # The framework automatically runs this in a container
        # based on the decorator configuration
        result = node.execute("cat /proc/1/status")
        log.info(f"Process 1 status: {result.stdout}")
```

### Example 3: Complex Container Test with Custom Image

```python
@TestSuiteMetadata(
    area="kernel",
    category="stress",
    description="Kernel testing in containers",
)
class KernelContainerTests(ContainerTestSuite):
    def _get_container_config(self) -> ContainerTestConfig:
        return ContainerTestConfig(
            image="myregistry.io/kernel-test:latest",
            registry="myregistry.io",
            privileged=True,
            mount_host_root=True,
            volumes={
                "/dev": "/dev",
                "/sys": "/sys",
                "/proc": "/proc",
            },
            environment={
                "TEST_MODE": "kernel",
                "LOG_LEVEL": "debug",
            },
            network_mode="host",
        )
    
    @TestCaseMetadata(description="Stress test kernel modules")
    def test_kernel_modules(self, node: Node, log: Logger) -> None:
        with ContainerExecutor(node, self.container_config) as executor:
            # Load kernel module inside container
            result = executor.run("modprobe dummy")
            assert_that(result.exit_code).is_equal_to(0)
            
            # Run stress test
            result = executor.run("/tests/kernel_stress.sh")
            assert_that(result.exit_code).is_equal_to(0)
            
            # Check dmesg for errors
            result = executor.run("dmesg | grep -i error")
            assert_that(result.stdout).is_empty()
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Implement `DockerAdvanced` tool with extended capabilities
2. Create `ContainerTestConfig` dataclass
3. Implement `ContainerTestSuite` base class
4. Add container execution methods

### Phase 2: Enhanced Features
1. Implement `@container_test` decorator
2. Create `ContainerExecutor` context manager
3. Add registry authentication support
4. Implement container caching for performance

### Phase 3: Integration
1. Update existing Docker tool tests
2. Create example test suites
3. Add documentation
4. Integration with CI/CD

## Benefits

1. **Isolation**: Tests run in isolated container environments
2. **Reproducibility**: Container images ensure consistent test environments
3. **Security**: Privileged operations are contained
4. **Flexibility**: Support for various container configurations
5. **Minimal Changes**: Leverages existing LISA patterns and infrastructure

## Considerations

1. **Performance**: Container startup overhead may impact test execution time
2. **Compatibility**: Ensure compatibility with different container runtimes (Docker, Podman)
3. **Security**: Privileged containers require careful security considerations
4. **Resource Management**: Proper cleanup of containers and images

## Future Enhancements

1. **Kubernetes Support**: Run tests in Kubernetes pods
2. **Container Composition**: Support for multi-container test scenarios
3. **Image Building**: Build test images as part of test execution
4. **Result Collection**: Enhanced result collection from containers
5. **Distributed Testing**: Run container tests across multiple nodes