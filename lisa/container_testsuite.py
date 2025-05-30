# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import functools
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from lisa import TestCaseMetadata, TestSuite, TestSuiteMetadata
from lisa.environment import Environment
from lisa.node import Node
from lisa.tools.docker_advanced import DockerAdvanced
from lisa.util import LisaException
from lisa.util.logger import Logger


@dataclass
class ContainerTestConfig:
    """Configuration for container-based tests."""
    image: str
    privileged: bool = False
    mount_host_root: bool = False
    volumes: Optional[Dict[str, str]] = None
    environment: Optional[Dict[str, str]] = None
    working_dir: Optional[str] = None
    network: Optional[str] = None
    memory_limit: Optional[str] = None
    cpu_limit: Optional[str] = None
    security_opts: Optional[List[str]] = None
    cap_add: Optional[List[str]] = None
    cap_drop: Optional[List[str]] = None
    registry_url: Optional[str] = None
    registry_username: Optional[str] = None
    registry_password: Optional[str] = None
    pull_always: bool = False
    extra_args: Optional[str] = None


class ContainerExecutor:
    """
    Context manager for running commands in a container.
    Allows multiple commands to be run in the same container instance.
    """
    
    def __init__(self, node: Node, config: ContainerTestConfig, log: Logger):
        self.node = node
        self.config = config
        self.log = log
        self.docker = node.tools[DockerAdvanced]
        self.container_name: Optional[str] = None
        
    def __enter__(self) -> "ContainerExecutor":
        # Generate unique container name
        import uuid
        self.container_name = f"lisa_test_{uuid.uuid4().hex[:8]}"
        
        # Get full image name including registry
        full_image = self.docker.get_full_image_name(
            self.config.image,
            self.config.registry_url
        )
        
        # Pull image if configured to always pull or if it doesn't exist locally
        if self.config.pull_always or not self.docker.image_exists(full_image):
            self.log.info(f"Pulling container image: {full_image}")
            self.docker.pull_image(
                self.config.image,
                self.config.registry_url,
                self.config.registry_username,
                self.config.registry_password,
                force=self.config.pull_always,
            )
        else:
            self.log.info(f"Using existing local image: {full_image}")
        
        # Start container in detached mode
        self.log.info(f"Starting container: {self.container_name}")
        self.docker.run_container(
            image=full_image,  # Use full image name
            name=self.container_name,
            command="/bin/sh -c 'while true; do sleep 30; done'",  # Keep container running
            privileged=self.config.privileged,
            mount_host_root=self.config.mount_host_root,
            volumes=self.config.volumes,
            environment=self.config.environment,
            working_dir=self.config.working_dir,
            network=self.config.network,
            memory_limit=self.config.memory_limit,
            cpu_limit=self.config.cpu_limit,
            security_opts=self.config.security_opts,
            cap_add=self.config.cap_add,
            cap_drop=self.config.cap_drop,
            extra_args=self.config.extra_args,
            detach=True,
            remove=False,
        )
        
        return self
        
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Clean up container
        if self.container_name and self.docker.container_exists(self.container_name):
            self.log.info(f"Stopping container: {self.container_name}")
            self.docker.stop_container(self.container_name)
            self.docker.remove_container(self.container_name)
            
    def run(self, command: str, expected_exit_code: int = 0) -> str:
        """Run a command in the container."""
        if not self.container_name:
            raise LisaException("Container not started")
            
        self.log.debug(f"Running in container: {command}")
        output = self.docker.exec_in_container(
            self.container_name,
            command,
            working_dir=self.config.working_dir,
        )
        
        # Check exit code
        exit_code_result = self.docker.exec_in_container(
            self.container_name,
            "echo $?",
        )
        actual_exit_code = int(exit_code_result.strip())
        
        if actual_exit_code != expected_exit_code:
            raise LisaException(
                f"Command '{command}' failed with exit code {actual_exit_code}, "
                f"expected {expected_exit_code}. Output: {output}"
            )
            
        return output
        


class ContainerTestSuite(TestSuite):
    """
    Base class for test suites that run tests inside containers.
    Provides utilities for container-based test execution.
    """
    
    def _get_container_config(self) -> ContainerTestConfig:
        """
        Override this method to provide container configuration.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _get_container_config()")
        
    def run_in_container(
        self,
        node: Node,
        command: str,
        log: Logger,
        config: Optional[ContainerTestConfig] = None,
        expected_exit_code: int = 0,
    ) -> str:
        """
        Run a single command in a container.
        
        Args:
            node: The node to run on
            command: Command to execute
            log: Logger instance
            config: Optional custom config, uses class default if not provided
            expected_exit_code: Expected exit code
            
        Returns:
            Command output
        """
        if config is None:
            config = self._get_container_config()
            
        docker = node.tools[DockerAdvanced]
        
        # Get full image name
        full_image = docker.get_full_image_name(config.image, config.registry_url)
        
        # Pull image if needed
        if config.pull_always or not docker.image_exists(full_image):
            log.info(f"Pulling container image: {full_image}")
            docker.pull_image(
                config.image,
                config.registry_url,
                config.registry_username,
                config.registry_password,
                force=config.pull_always,
            )
        else:
            log.info(f"Using existing local image: {full_image}")
        
        # Run command in container
        log.info(f"Running command in container: {command}")
        output = docker.run_container(
            image=full_image,
            command=command,
            privileged=config.privileged,
            mount_host_root=config.mount_host_root,
            volumes=config.volumes,
            environment=config.environment,
            working_dir=config.working_dir,
            network=config.network,
            memory_limit=config.memory_limit,
            cpu_limit=config.cpu_limit,
            security_opts=config.security_opts,
            cap_add=config.cap_add,
            cap_drop=config.cap_drop,
            extra_args=config.extra_args,
            remove=True,
        )
        
        return output
        
    def get_container_executor(
        self,
        node: Node,
        log: Logger,
        config: Optional[ContainerTestConfig] = None,
    ) -> ContainerExecutor:
        """
        Get a container executor for running multiple commands.
        
        Args:
            node: The node to run on
            log: Logger instance
            config: Optional custom config, uses class default if not provided
            
        Returns:
            ContainerExecutor instance
        """
        if config is None:
            config = self._get_container_config()
            
        return ContainerExecutor(node, config, log)


def container_test(
    image: str,
    privileged: bool = False,
    mount_host_root: bool = False,
    **kwargs: Any
) -> Callable:
    """
    Decorator to mark a test method to run inside a container.
    
    Args:
        image: Container image to use
        privileged: Run in privileged mode
        mount_host_root: Mount host root at /host
        **kwargs: Additional ContainerTestConfig parameters
        
    Example:
        @container_test(image="ubuntu:22.04", privileged=True)
        def test_something(self, node: Node, log: Logger) -> None:
            # This runs inside the container
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self: Any, node: Node, log: Logger, *args: Any, **func_kwargs: Any) -> Any:
            # Create container config
            config = ContainerTestConfig(
                image=image,
                privileged=privileged,
                mount_host_root=mount_host_root,
                **kwargs
            )
            
            # Check if the test class has container support
            if hasattr(self, 'run_in_container'):
                # For ContainerTestSuite subclasses
                original_run_in_container = self.run_in_container
                
                # Temporarily replace the config
                def get_config() -> ContainerTestConfig:
                    return config
                    
                original_get_config = self._get_container_config
                self._get_container_config = get_config
                
                try:
                    return func(self, node, log, *args, **func_kwargs)
                finally:
                    self._get_container_config = original_get_config
            else:
                # For regular TestSuite classes
                # Create a minimal container test suite instance
                class TempContainerSuite(ContainerTestSuite):
                    def _get_container_config(self) -> ContainerTestConfig:
                        return config
                        
                temp_suite = TempContainerSuite()
                
                # Bind the method to use container execution
                original_func = func
                
                def container_func(node: Node, log: Logger, *args: Any, **kwargs: Any) -> Any:
                    with temp_suite.get_container_executor(node, log) as executor:
                        # Replace node's execute method temporarily
                        original_execute = node.execute
                        
                        def container_execute(
                            cmd: str,
                            *exec_args: Any,
                            **exec_kwargs: Any
                        ) -> Any:
                            return executor.run(cmd)
                            
                        node.execute = container_execute
                        
                        try:
                            return original_func(self, node, log, *args, **kwargs)
                        finally:
                            node.execute = original_execute
                            
                return container_func(node, log, *args, **func_kwargs)
                
        return wrapper
    return decorator