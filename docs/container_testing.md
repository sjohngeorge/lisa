# Container-Based Testing in LISA

This document describes how to use the container-based testing framework in LISA, which allows running tests inside containers with all dependencies pre-installed.

## Overview

Container-based testing provides several advantages:

1. **Dependency Isolation**: All test dependencies are contained within the container image
2. **Clean Environment**: Tests don't pollute the target VM with installed packages
3. **Reproducibility**: Same container image ensures consistent test environment
4. **Privileged Operations**: Can run privileged operations safely within containers
5. **Host Access**: Can mount host filesystem for inspection while keeping test tools isolated

## Quick Start

### 1. Using Container Test Suite

Create a test suite that inherits from `ContainerTestSuite`:

```python
from lisa.container_testsuite import ContainerTestConfig, ContainerTestSuite

@TestSuiteMetadata(area="myarea", category="functional")
class MyContainerTests(ContainerTestSuite):
    def _get_container_config(self) -> ContainerTestConfig:
        return ContainerTestConfig(
            image="myregistry.azurecr.io/my-test-image:latest",
            privileged=True,
            mount_host_root=True,
            registry_url="myregistry.azurecr.io",
            registry_username="myuser",
            registry_password="mypass",
        )
    
    @TestCaseMetadata(description="My test", priority=1)
    def test_something(self, node: Node, log: Logger) -> None:
        # Use run_in_container for single commands
        output = self.run_in_container(node, "ls /host", log)
        
        # Or use executor for multiple commands
        with self.get_container_executor(node, log) as executor:
            executor.run("apt-get update")
            executor.run("make test")
```

### 2. Using Container Test Decorator

Use the `@container_test` decorator on any test method:

```python
from lisa.container_testsuite import container_test

@TestSuiteMetadata(area="myarea", category="functional")
class MyTests(TestSuite):
    @TestCaseMetadata(description="Container test", priority=1)
    @container_test(image="ubuntu:22.04", privileged=True)
    def test_in_container(self, node: Node, log: Logger) -> None:
        # All node.execute() calls run inside the container
        result = node.execute("cat /etc/os-release")
```

### 3. Direct Tool Usage

Use `DockerAdvanced` tool directly for custom scenarios:

```python
from lisa.tools.docker_advanced import DockerAdvanced

def test_custom(self, node: Node, log: Logger) -> None:
    docker = node.tools[DockerAdvanced]
    
    # Pull from registry
    docker.pull_image(
        "myregistry.azurecr.io/test:latest",
        registry_url="myregistry.azurecr.io",
        username="user",
        password="pass"
    )
    
    # Run with custom options
    output = docker.run_container(
        image="test:latest",
        command="pytest /tests",
        privileged=True,
        mount_host_root=True,
        volumes={"/data": "/container_data"},
        environment={"TEST_ENV": "production"},
    )
```

## Container Configuration Options

The `ContainerTestConfig` class supports:

- `image`: Container image to use
- `privileged`: Run in privileged mode (default: False)
- `mount_host_root`: Mount host root at /host (default: False)
- `volumes`: Additional volume mounts as dict
- `environment`: Environment variables as dict
- `working_dir`: Working directory in container
- `network`: Network mode (host, bridge, none)
- `memory_limit`: Memory limit (e.g., "2g")
- `cpu_limit`: CPU limit (e.g., "1.5")
- `security_opts`: Security options list
- `cap_add`: Capabilities to add
- `cap_drop`: Capabilities to drop
- `registry_url`: Container registry URL
- `registry_username`: Registry username
- `registry_password`: Registry password
- `pull_always`: Always pull image (default: False)

## Using Pre-Built Container Images

The container testing framework is designed to use pre-built images from a container registry. This approach:

1. **Saves Time**: No need to install dependencies during test runs
2. **Ensures Consistency**: Same image = same test environment
3. **Improves Performance**: Images are cached locally after first pull
4. **Simplifies Maintenance**: Update image once, use everywhere

### Building Test Container Images

Build your test images once with all dependencies:

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install ALL test dependencies at build time
RUN apt-get update && apt-get install -y \
    # Test tools
    python3 \
    python3-pip \
    stress-ng \
    iperf3 \
    tcpdump \
    # System tools
    iproute2 \
    procps \
    sysstat \
    # Clean up to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Install Python test packages
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy test scripts and tools
COPY tests/ /tests/
COPY scripts/ /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/*.sh

WORKDIR /workspace
CMD ["/bin/bash"]
```

### Building and Pushing

```bash
# Set registry credentials
export LISA_REGISTRY_URL=myregistry.azurecr.io
export LISA_REGISTRY_USERNAME=myuser
export LISA_REGISTRY_PASSWORD=mypass

# Build the image with version tag
docker build -t $LISA_REGISTRY_URL/lisa-tests/network:v1.0 .

# Also tag as latest
docker tag $LISA_REGISTRY_URL/lisa-tests/network:v1.0 \
         $LISA_REGISTRY_URL/lisa-tests/network:latest

# Login and push
echo $LISA_REGISTRY_PASSWORD | docker login $LISA_REGISTRY_URL \
    -u $LISA_REGISTRY_USERNAME --password-stdin

docker push $LISA_REGISTRY_URL/lisa-tests/network:v1.0
docker push $LISA_REGISTRY_URL/lisa-tests/network:latest
```

### Using Registry Images in Tests

Configure your tests to use pre-built images:

```python
def _get_container_config(self) -> ContainerTestConfig:
    import os
    
    return ContainerTestConfig(
        # Image with all dependencies pre-installed
        image="lisa-tests/network:v1.0",
        
        # Registry configuration from environment
        registry_url=os.environ.get("LISA_REGISTRY_URL"),
        registry_username=os.environ.get("LISA_REGISTRY_USERNAME"),
        registry_password=os.environ.get("LISA_REGISTRY_PASSWORD"),
        
        # Don't pull if already cached locally
        pull_always=False,
        
        # Your test configuration
        privileged=True,
        mount_host_root=True,
    )
```

### Image Caching Behavior

1. **First Run**: Image is pulled from registry if not present locally
2. **Subsequent Runs**: Uses cached local image (no pull)
3. **Force Pull**: Set `pull_always=True` to always get latest
4. **Version Updates**: Use specific tags (v1.0, v1.1) for controlled updates

### Environment Variables

Set these in your environment or CI/CD:

```bash
# Registry configuration
export LISA_REGISTRY_URL=myregistry.azurecr.io
export LISA_REGISTRY_USERNAME=myuser
export LISA_REGISTRY_PASSWORD=mypass

# Specific image versions (optional)
export LISA_CPU_IMAGE=lisa-tests/cpu:v2.1
export LISA_NETWORK_IMAGE=lisa-tests/network:v1.5
export LISA_STORAGE_IMAGE=lisa-tests/storage:latest
```

## Best Practices

1. **Pre-install Dependencies**: Include all test dependencies in the container image
2. **Use Specific Tags**: Avoid using 'latest' tag in production
3. **Minimize Image Size**: Use multi-stage builds when possible
4. **Security**: Only use privileged mode when necessary
5. **Registry Authentication**: Store credentials securely (e.g., Azure Key Vault)
6. **Host Filesystem**: Mount as read-only when possible
7. **Cleanup**: Containers are automatically cleaned up after tests

## Real-World Example

Here's a complete example for network performance testing:

```python
@TestSuiteMetadata(area="network", category="performance")
class NetworkPerfContainer(ContainerTestSuite):
    def _get_container_config(self) -> ContainerTestConfig:
        return ContainerTestConfig(
            image="myregistry.azurecr.io/netperf:v1.0",
            privileged=True,  # Needed for network namespace
            network="host",   # Use host networking
            mount_host_root=True,
            environment={
                "IPERF_PORT": "5201",
                "TEST_DURATION": "60",
            },
        )
    
    @TestCaseMetadata(
        description="Measure network throughput using iperf3",
        priority=2,
    )
    def test_network_throughput(self, node: Node, log: Logger) -> None:
        with self.get_container_executor(node, log) as executor:
            # Check host network configuration
            host_iface = executor.run("ls /host/sys/class/net/ | grep -v lo | head -1")
            log.info(f"Testing interface: {host_iface}")
            
            # Run iperf3 server in background
            executor.run("iperf3 -s -D")
            
            # Run client test
            result = executor.run("iperf3 -c localhost -t 10 -J")
            
            # Parse JSON results
            import json
            perf_data = json.loads(result)
            throughput_gbps = perf_data["end"]["sum_received"]["bits_per_second"] / 1e9
            
            log.info(f"Network throughput: {throughput_gbps:.2f} Gbps")
            
            # Validate performance
            assert throughput_gbps > 10, f"Throughput {throughput_gbps} below 10 Gbps"
```

## Troubleshooting

1. **Container Start Failures**: Check Docker daemon logs
2. **Permission Denied**: Ensure privileged mode for system operations  
3. **Registry Auth Issues**: Verify credentials and registry URL
4. **Missing Tools**: Ensure all tools are installed in the container image
5. **Cleanup Issues**: Containers are auto-removed, check `docker ps -a` if needed