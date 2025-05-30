# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Example of container-based CPU tests using pre-built images from a registry.
This demonstrates how to use container images that have all dependencies pre-installed.
"""

from typing import List

from lisa import (
    Logger,
    Node,
    TestCaseMetadata,
    TestSuite,
    TestSuiteMetadata,
    simple_requirement,
)
from lisa.container_testsuite import ContainerTestConfig, ContainerTestSuite
from lisa.operating_system import Posix


@TestSuiteMetadata(
    area="core",
    category="functional",
    description="""
    CPU tests that run in pre-built containers from a registry.
    No local building required - all dependencies are in the container image.
    """,
)
class ContainerCpuTestSuite(ContainerTestSuite):
    """
    CPU validation tests using container images with stress-ng, cpuinfo tools pre-installed.
    """
    
    def _get_container_config(self) -> ContainerTestConfig:
        """
        Configure to use a pre-built image from Azure Container Registry.
        In production, replace with your actual registry and image.
        """
        return ContainerTestConfig(
            # Example: using a public stress-ng image
            # In production, use your custom image like:
            # image="lisa-tests/cpu:v1.0",
            # registry_url="myregistry.azurecr.io",
            image="alexeiled/stress-ng:latest",
            
            # No registry auth needed for public images
            # For private registries, set these from environment or secrets:
            # registry_username=os.environ.get("ACR_USERNAME"),
            # registry_password=os.environ.get("ACR_PASSWORD"),
            
            # CPU tests often need privileged access
            privileged=True,
            
            # Mount host /proc and /sys for CPU info
            volumes={
                "/proc": "/host/proc:ro",
                "/sys": "/host/sys:ro",
            },
            
            # Don't pull if already cached
            pull_always=False,
        )
    
    @TestCaseMetadata(
        description="""
        Verify CPU count matches between container and host.
        Uses pre-built container with necessary tools.
        """,
        priority=1,
        requirement=simple_requirement(supported_os=[Posix]),
    )
    def verify_cpu_count_container(
        self,
        node: Node,
        log: Logger,
    ) -> None:
        """Test CPU detection inside a container."""
        
        with self.get_container_executor(node, log) as executor:
            # Get CPU count from container's view
            container_cpus = executor.run("nproc").strip()
            log.info(f"Container sees {container_cpus} CPUs")
            
            # Get CPU count from host /proc
            host_cpus = executor.run("grep -c ^processor /host/proc/cpuinfo").strip()
            log.info(f"Host has {host_cpus} CPUs")
            
            # Verify they match
            assert container_cpus == host_cpus, (
                f"CPU count mismatch: container={container_cpus}, host={host_cpus}"
            )
            
            # Also check CPU info is accessible
            cpu_info = executor.run("cat /host/proc/cpuinfo | head -20")
            log.debug(f"CPU info:\n{cpu_info}")
    
    @TestCaseMetadata(
        description="""
        Run CPU stress test using pre-installed stress-ng.
        Demonstrates using complex tools without installation.
        """,
        priority=2,
        requirement=simple_requirement(supported_os=[Posix]),
    )
    def verify_cpu_stress_container(
        self,
        node: Node,
        log: Logger,
    ) -> None:
        """Run CPU stress test in container."""
        
        # For stress testing, we might want a custom config
        stress_config = ContainerTestConfig(
            image="alexeiled/stress-ng:latest",
            privileged=True,
            # Limit CPU to prevent overload
            cpu_limit="2.0",
            # Set memory limit
            memory_limit="1g",
            pull_always=False,
        )
        
        with self.get_container_executor(node, log, stress_config) as executor:
            log.info("Running CPU stress test for 10 seconds")
            
            # Run stress-ng CPU test
            # The image already has stress-ng installed
            result = executor.run(
                "stress-ng --cpu 2 --timeout 10s --metrics-brief"
            )
            
            log.info(f"Stress test output:\n{result}")
            
            # Verify stress test completed successfully
            assert "successful run completed" in result.lower(), "Stress test failed"


@TestSuiteMetadata(
    area="core",
    category="functional",
    description="""
    Example using a custom pre-built image with all test dependencies.
    This simulates what you would do with your own registry.
    """,
)
class CustomImageCpuTests(ContainerTestSuite):
    """
    Example using a hypothetical custom image from a private registry.
    """
    
    def _get_container_config(self) -> ContainerTestConfig:
        """
        Example configuration for a private registry.
        In practice, credentials would come from secure storage.
        """
        # Import these at runtime to avoid issues if not set
        import os
        
        return ContainerTestConfig(
            # Your custom image with all test tools pre-installed
            image="lisa-cpu-tests:v2.1.0",
            
            # Your private registry
            registry_url=os.environ.get("LISA_REGISTRY_URL", ""),
            registry_username=os.environ.get("LISA_REGISTRY_USERNAME", ""),
            registry_password=os.environ.get("LISA_REGISTRY_PASSWORD", ""),
            
            # The image has everything needed, just pull once
            pull_always=False,
            
            privileged=True,
            mount_host_root=True,
            
            # Set consistent environment
            environment={
                "TEST_TIMEOUT": "300",
                "LOG_LEVEL": "INFO",
            },
        )
    
    @TestCaseMetadata(
        description="Run comprehensive CPU validation from pre-built image",
        priority=1,
        requirement=simple_requirement(supported_os=[Posix]),
    )
    def verify_cpu_comprehensive(
        self,
        node: Node,
        log: Logger,
    ) -> None:
        """
        This test assumes the container image has a test script pre-installed.
        The script contains all the complex CPU validation logic.
        """
        
        with self.get_container_executor(node, log) as executor:
            # The container image includes the test script
            # No need to install anything or copy scripts
            log.info("Running comprehensive CPU tests from container")
            
            # Execute pre-installed test script
            result = executor.run("/usr/local/bin/cpu_validation.sh")
            
            # The script outputs JSON results
            import json
            try:
                test_results = json.loads(result)
                
                log.info(f"CPU test results: {test_results}")
                
                # Verify all tests passed
                for test_name, test_result in test_results.items():
                    assert test_result["status"] == "PASS", (
                        f"Test {test_name} failed: {test_result.get('message', 'No message')}"
                    )
                    
            except json.JSONDecodeError:
                # Fallback if not JSON
                assert "ALL TESTS PASSED" in result, "CPU validation failed"