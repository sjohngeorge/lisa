# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Mixin to enhance test runners with container test support.

This module provides functionality to automatically detect and run
tests marked with @container_test decorator inside containers.
"""

import functools
import inspect
from typing import Any, Callable, Dict, Optional

from lisa import Logger, Node, TestResult, TestSuite
from lisa.container_testsuite import ContainerExecutor, ContainerTestConfig
from lisa.tools.docker_advanced import DockerAdvanced
from lisa.util import LisaException


class ContainerRunnerMixin:
    """
    Mixin class that adds container test support to test runners.
    
    This mixin intercepts test case execution and runs tests marked with
    @container_test decorator inside containers automatically.
    """
    
    def _wrap_container_test_method(
        self,
        test_method: Callable,
        container_config: ContainerTestConfig,
    ) -> Callable:
        """
        Wrap a test method to run inside a container.
        
        Args:
            test_method: The original test method
            container_config: Container configuration from decorator
        
        Returns:
            Wrapped test method that runs in container
        """
        @functools.wraps(test_method)
        def wrapped_method(*args: Any, **kwargs: Any) -> None:
            # Extract node and log from kwargs
            node: Optional[Node] = kwargs.get("node")
            log: Optional[Logger] = kwargs.get("log")
            
            if not node:
                raise LisaException("Node not provided to container test")
            
            if not log:
                log = node.log
            
            # Prepare container
            docker = node.tools[DockerAdvanced]
            log.info(f"Preparing container test with image {container_config.image}")
            
            # Pull image
            docker.pull_image(
                image=container_config.image,
                registry=container_config.registry,
                quiet=True,
            )
            
            # Run test in container
            with ContainerExecutor(node, container_config, log) as executor:
                # Create a modified test method that uses the executor
                def container_test_impl(*args: Any, **kwargs: Any) -> None:
                    # Replace node.execute with container executor
                    original_execute = node.execute
                    original_execute_async = node.execute_async
                    
                    def execute_in_container(
                        cmd: str,
                        shell: bool = True,
                        sudo: bool = False,
                        **exec_kwargs: Any
                    ) -> Any:
                        return executor.run(
                            cmd,
                            shell=shell,
                            sudo=sudo,
                            **exec_kwargs
                        )
                    
                    def execute_async_in_container(
                        cmd: str,
                        shell: bool = True,
                        sudo: bool = False,
                        **exec_kwargs: Any
                    ) -> Any:
                        # For async, we need to handle differently
                        # For now, just run sync
                        return execute_in_container(
                            cmd,
                            shell=shell,
                            sudo=sudo,
                            **exec_kwargs
                        )
                    
                    try:
                        # Temporarily replace node execution methods
                        node.execute = execute_in_container  # type: ignore
                        node.execute_async = execute_async_in_container  # type: ignore
                        
                        # Run the actual test method
                        test_method(*args, **kwargs)
                    finally:
                        # Restore original methods
                        node.execute = original_execute  # type: ignore
                        node.execute_async = original_execute_async  # type: ignore
                
                # Call the container test implementation
                container_test_impl(*args, **kwargs)
        
        return wrapped_method
    
    def _prepare_test_suite(self, test_suite: TestSuite) -> None:
        """
        Prepare test suite by wrapping container tests.
        
        This method should be called before running tests to wrap any methods
        marked with @container_test decorator.
        
        Args:
            test_suite: The test suite to prepare
        """
        # Iterate through all methods in the test suite
        for name in dir(test_suite):
            # Skip private methods
            if name.startswith("_"):
                continue
            
            attr = getattr(test_suite, name)
            
            # Check if it's a method with container test marker
            if (
                inspect.ismethod(attr)
                and hasattr(attr, "_is_container_test")
                and hasattr(attr, "_container_config")
            ):
                # Get container configuration
                container_config: ContainerTestConfig = attr._container_config
                
                # Wrap the method
                wrapped = self._wrap_container_test_method(attr, container_config)
                
                # Replace the method on the test suite
                setattr(test_suite, name, wrapped)
    
    def _is_container_test_case(self, test_case: Any) -> bool:
        """
        Check if a test case is marked as a container test.
        
        Args:
            test_case: Test case to check
        
        Returns:
            True if test case should run in container
        """
        # Check if test case has container test marker
        return (
            hasattr(test_case, "_is_container_test")
            and hasattr(test_case, "_container_config")
        )
    
    def _get_container_config_for_test(self, test_case: Any) -> Optional[ContainerTestConfig]:
        """
        Get container configuration for a test case.
        
        Args:
            test_case: Test case to get config for
        
        Returns:
            Container configuration or None
        """
        if self._is_container_test_case(test_case):
            return getattr(test_case, "_container_config", None)
        return None


class ContainerTestResultMixin:
    """
    Mixin to enhance test results with container information.
    """
    
    def _add_container_info(self, result: TestResult, container_config: ContainerTestConfig) -> None:
        """
        Add container information to test result.
        
        Args:
            result: Test result to enhance
            container_config: Container configuration used
        """
        result.information["container_image"] = container_config.image
        result.information["container_privileged"] = str(container_config.privileged)
        
        if container_config.registry:
            result.information["container_registry"] = container_config.registry
        
        if container_config.mount_host_root:
            result.information["container_host_mount"] = "/host"
        
        if container_config.environment:
            result.information["container_env"] = str(container_config.environment)