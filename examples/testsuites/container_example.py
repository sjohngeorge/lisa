# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Example test suite demonstrating container-based testing in LISA.

This test suite shows how to:
1. Run tests inside containers with various configurations
2. Use privileged containers for system-level testing
3. Mount host filesystem for inspection
4. Use different container images for different tests
"""

from pathlib import Path
from typing import Any

from assertpy import assert_that

from lisa import Logger, Node, TestCaseMetadata, TestSuiteMetadata, simple_requirement
from lisa.container_testsuite import (
    ContainerExecutor,
    ContainerTestConfig,
    ContainerTestSuite,
    container_test,
)
from lisa.tools import Cat, Echo


@TestSuiteMetadata(
    area="container_demo",
    category="functional",
    description="""
    Example container-based test suite demonstrating various container testing patterns.
    """,
    requirement=simple_requirement(
        supported_os=[],  # Works on any OS with Docker
    ),
)
class ContainerExampleTests(ContainerTestSuite):
    """Example test suite running tests inside containers"""
    
    def _get_container_config(self) -> ContainerTestConfig:
        """Default container configuration for this test suite"""
        return ContainerTestConfig(
            image="ubuntu:22.04",
            privileged=True,
            mount_host_root=True,
            environment={
                "TEST_ENV": "lisa_container_test",
                "DEBUG": "true",
            },
        )
    
    @TestCaseMetadata(
        description="""
        Basic container test that runs commands inside a container.
        Shows how to use the _run_in_container method.
        """,
        priority=1,
    )
    def test_basic_container_execution(self, node: Node, log: Logger) -> None:
        # Prepare the container environment
        self._prepare_container(node, log)
        
        # Run a simple command in the container
        result = self._run_in_container(
            node,
            "uname -a",
            log,
        )
        log.info(f"Container kernel info: {result.stdout}")
        assert_that(result.exit_code).is_equal_to(0)
        
        # Check environment variable
        result = self._run_in_container(
            node,
            "echo $TEST_ENV",
            log,
        )
        assert_that(result.stdout.strip()).is_equal_to("lisa_container_test")
        
        # Access host filesystem through /host mount
        result = self._run_in_container(
            node,
            "ls -la /host/etc | head -5",
            log,
        )
        log.info(f"Host /etc contents:\n{result.stdout}")
        assert_that(result.exit_code).is_equal_to(0)
    
    @TestCaseMetadata(
        description="""
        Test using ContainerExecutor for long-running container operations.
        Shows how to maintain state across multiple commands.
        """,
        priority=2,
    )
    def test_container_executor(self, node: Node, log: Logger) -> None:
        # Prepare the container environment
        self._prepare_container(node, log)
        
        # Use ContainerExecutor for multiple operations in the same container
        with self._create_container_executor(node, log) as executor:
            # Create a file in the container
            result = executor.run("echo 'Hello from container' > /tmp/test.txt")
            assert_that(result.exit_code).is_equal_to(0)
            
            # Read the file back
            result = executor.run("cat /tmp/test.txt")
            assert_that(result.stdout.strip()).is_equal_to("Hello from container")
            
            # Install a package (works because container persists)
            result = executor.run("apt-get update && apt-get install -y curl", timeout=300)
            assert_that(result.exit_code).is_equal_to(0)
            
            # Use the installed package
            result = executor.run("curl --version | head -1")
            log.info(f"Curl version: {result.stdout.strip()}")
            assert_that(result.stdout).contains("curl")
    
    @TestCaseMetadata(
        description="""
        Test with custom container configuration.
        Shows how to override container settings for specific tests.
        """,
        priority=2,
    )
    def test_custom_container_config(self, node: Node, log: Logger) -> None:
        # Create custom configuration for this test
        custom_config = ContainerTestConfig(
            image="alpine:latest",
            privileged=False,  # Non-privileged container
            volumes={
                node.working_path.as_posix(): "/workspace",
            },
            environment={
                "CUSTOM_TEST": "alpine_test",
            },
            memory="512m",
            cpus="1",
        )
        
        # Prepare and run with custom config
        docker = node.tools.get("DockerAdvanced")
        docker.pull_image(custom_config.image)
        
        with ContainerExecutor(node, custom_config, log) as executor:
            # Check we're running Alpine
            result = executor.run("cat /etc/os-release | grep PRETTY_NAME")
            log.info(f"OS: {result.stdout.strip()}")
            assert_that(result.stdout).contains("Alpine")
            
            # Check memory limit
            result = executor.run("cat /sys/fs/cgroup/memory/memory.limit_in_bytes")
            log.info(f"Memory limit: {result.stdout.strip()}")
            
            # Create file in mounted workspace
            result = executor.run("echo 'Alpine test' > /workspace/alpine_test.txt")
            assert_that(result.exit_code).is_equal_to(0)
        
        # Verify file exists on host
        cat = node.tools[Cat]
        host_file = node.working_path / "alpine_test.txt"
        content = cat.read(host_file.as_posix())
        assert_that(content.strip()).is_equal_to("Alpine test")
    
    @TestCaseMetadata(
        description="""
        Test system operations in privileged container.
        Shows how privileged containers can perform system-level operations.
        """,
        priority=3,
    )
    def test_privileged_operations(self, node: Node, log: Logger) -> None:
        # This test uses the default privileged configuration
        self._prepare_container(node, log)
        
        with self._create_container_executor(node, log) as executor:
            # Check we have privileged access
            result = executor.run("cat /proc/1/status | grep CapEff")
            log.info(f"Effective capabilities: {result.stdout.strip()}")
            
            # Try to load a kernel module (requires privilege)
            result = executor.run("modprobe dummy numdummies=2", no_error_log=True)
            if result.exit_code == 0:
                log.info("Successfully loaded dummy kernel module")
                
                # Check module is loaded
                result = executor.run("lsmod | grep dummy")
                assert_that(result.stdout).contains("dummy")
                
                # Unload module
                executor.run("rmmod dummy")
            else:
                log.warning("Could not load kernel module (expected on some systems)")
            
            # Access host devices
            result = executor.run("ls -la /host/dev | head -10")
            log.info(f"Host devices:\n{result.stdout}")
            assert_that(result.exit_code).is_equal_to(0)
    
    def before_case(self, log: Logger, **kwargs: Any) -> None:
        """Setup before each test case"""
        log.info("Setting up container test environment")
    
    def after_case(self, log: Logger, **kwargs: Any) -> None:
        """Cleanup after each test case"""
        log.info("Cleaning up container test environment")


# Example of using the @container_test decorator with a regular TestSuite
from lisa import TestSuite


@TestSuiteMetadata(
    area="container_decorator_demo",
    category="functional",
    description="""
    Example test suite using the @container_test decorator.
    """,
)
class ContainerDecoratorTests(TestSuite):
    """Example test suite using container test decorator"""
    
    @TestCaseMetadata(
        description="""
        Test using the @container_test decorator to run in a container.
        """,
        priority=1,
    )
    @container_test(
        image="python:3.9-slim",
        privileged=False,
        environment={
            "PYTHONUNBUFFERED": "1",
        },
    )
    def test_python_container(self, node: Node, log: Logger) -> None:
        """This test is marked to run in a Python container"""
        # Note: The framework would need to be extended to automatically
        # handle @container_test decorated methods. For now, this shows
        # the intended usage pattern.
        
        # Get the container config from the decorator
        config = getattr(self.test_python_container, "_container_config", None)
        if config:
            log.info(f"Test configured to run in container: {config.image}")
            
            # In a full implementation, the framework would automatically
            # run this test inside the specified container
            docker = node.tools.get("DockerAdvanced")
            docker.pull_image(config.image)
            
            result = docker.run_in_container(
                image=config.image,
                command="python --version",
                privileged=config.privileged,
                environment=config.environment,
            )
            
            log.info(f"Python version in container: {result.stdout.strip()}")
            assert_that(result.stdout).contains("Python 3.9")
    
    @TestCaseMetadata(
        description="""
        Test with privileged container using decorator.
        """,
        priority=2,
    )
    @container_test(
        image="ubuntu:22.04",
        privileged=True,
        mount_host_root=True,
        volumes={
            "/var/log": "/host_logs",
        },
    )
    def test_privileged_with_decorator(self, node: Node, log: Logger) -> None:
        """Test that needs privileged access"""
        config = getattr(self.test_privileged_with_decorator, "_container_config", None)
        if config:
            log.info("Running privileged container test")
            
            docker = node.tools.get("DockerAdvanced")
            docker.pull_image(config.image)
            
            # Prepare volumes
            volumes = config.volumes.copy()
            if config.mount_host_root:
                volumes["/"] = "/host"
            
            # Check host logs are accessible
            result = docker.run_in_container(
                image=config.image,
                command="ls -la /host_logs | head -5",
                privileged=config.privileged,
                volumes=volumes,
            )
            
            log.info(f"Host logs:\n{result.stdout}")
            assert_that(result.exit_code).is_equal_to(0)