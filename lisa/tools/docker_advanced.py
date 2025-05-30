# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from lisa.executable import Tool
from lisa.operating_system import Posix
from lisa.tools import Docker
from lisa.util import LisaException


class DockerAdvanced(Docker):
    """
    Extended Docker tool with advanced container features for testing.
    Supports privileged mode, host filesystem mounting, and registry operations.
    """

    @property
    def command(self) -> str:
        return "docker"

    @property
    def can_install(self) -> bool:
        return True

    def _check_exists(self) -> bool:
        return self.node.tools[Docker].is_installed

    def _install(self) -> bool:
        # Use the base Docker tool for installation
        self.node.tools[Docker].install()
        return self._check_exists()

    def pull_image(
        self,
        image: str,
        registry_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """
        Pull container image from registry with optional authentication.
        
        Args:
            image: Image name (e.g., "myapp:latest" or "ubuntu:22.04")
            registry_url: Optional registry URL (e.g., "myregistry.azurecr.io")
            username: Registry username
            password: Registry password
            force: Force pull even if image exists locally
        """
        # Construct full image name
        full_image = f"{registry_url}/{image}" if registry_url else image
        
        # Check if image already exists locally (unless force pull)
        if not force and self.image_exists(full_image):
            self._log.info(f"Image {full_image} already exists locally, skipping pull")
            return
            
        # Login to registry if credentials provided
        if registry_url and username and password:
            self._log.info(f"Logging into registry {registry_url}")
            # Use --password-stdin for better security
            login_result = self.run(
                f"login {registry_url} -u {username} --password-stdin",
                input_data=password,
                expected_exit_code=0,
                expected_exit_code_failure_message="Failed to login to container registry",
            )

        # Pull the image
        self._log.info(f"Pulling image {full_image}")
        self.run(
            f"pull {full_image}",
            expected_exit_code=0,
            expected_exit_code_failure_message=f"Failed to pull image {full_image}",
        )

    def run_container(
        self,
        image: str,
        command: Optional[str] = None,
        name: Optional[str] = None,
        privileged: bool = False,
        mount_host_root: bool = False,
        volumes: Optional[Dict[str, str]] = None,
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        detach: bool = False,
        remove: bool = True,
        network: Optional[str] = None,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        security_opts: Optional[List[str]] = None,
        cap_add: Optional[List[str]] = None,
        cap_drop: Optional[List[str]] = None,
        extra_args: Optional[str] = None,
    ) -> str:
        """
        Run a container with advanced options.
        
        Args:
            image: Container image to run
            command: Command to execute in container
            name: Container name
            privileged: Run in privileged mode
            mount_host_root: Mount host root filesystem at /host
            volumes: Additional volume mounts {host_path: container_path}
            environment: Environment variables
            working_dir: Working directory in container
            detach: Run container in background
            remove: Remove container after exit
            network: Network mode (host, bridge, none)
            memory_limit: Memory limit (e.g., "2g")
            cpu_limit: CPU limit (e.g., "1.5")
            security_opts: Security options
            cap_add: Capabilities to add
            cap_drop: Capabilities to drop
            extra_args: Additional docker run arguments
            
        Returns:
            Container output or container ID if detached
        """
        cmd_parts = ["run"]
        
        if detach:
            cmd_parts.append("-d")
        else:
            cmd_parts.append("-it")
            
        if remove and not detach:
            cmd_parts.append("--rm")
            
        if name:
            cmd_parts.extend(["--name", name])
            
        if privileged:
            cmd_parts.append("--privileged")
            
        if mount_host_root:
            cmd_parts.extend(["-v", "/:/host:ro"])
            
        if volumes:
            for host_path, container_path in volumes.items():
                cmd_parts.extend(["-v", f"{host_path}:{container_path}"])
                
        if environment:
            for key, value in environment.items():
                cmd_parts.extend(["-e", f"{key}={value}"])
                
        if working_dir:
            cmd_parts.extend(["-w", working_dir])
            
        if network:
            cmd_parts.extend(["--network", network])
            
        if memory_limit:
            cmd_parts.extend(["-m", memory_limit])
            
        if cpu_limit:
            cmd_parts.extend(["--cpus", cpu_limit])
            
        if security_opts:
            for opt in security_opts:
                cmd_parts.extend(["--security-opt", opt])
                
        if cap_add:
            for cap in cap_add:
                cmd_parts.extend(["--cap-add", cap])
                
        if cap_drop:
            for cap in cap_drop:
                cmd_parts.extend(["--cap-drop", cap])
                
        if extra_args:
            cmd_parts.append(extra_args)
            
        cmd_parts.append(image)
        
        if command:
            cmd_parts.append(command)
            
        result = self.run(
            " ".join(cmd_parts),
            expected_exit_code=0 if not detach else None,
            shell=True,
        )
        
        return result.stdout

    def exec_in_container(
        self,
        container: str,
        command: str,
        user: Optional[str] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        interactive: bool = False,
        tty: bool = False,
    ) -> str:
        """Execute a command in a running container."""
        cmd_parts = ["exec"]
        
        if interactive:
            cmd_parts.append("-i")
        if tty:
            cmd_parts.append("-t")
            
        if user:
            cmd_parts.extend(["-u", user])
            
        if working_dir:
            cmd_parts.extend(["-w", working_dir])
            
        if environment:
            for key, value in environment.items():
                cmd_parts.extend(["-e", f"{key}={value}"])
                
        cmd_parts.append(container)
        cmd_parts.append(command)
        
        result = self.run(
            " ".join(cmd_parts),
            shell=True,
        )
        
        return result.stdout

    def stop_container(self, container: str, timeout: int = 10) -> None:
        """Stop a running container."""
        self.run(
            f"stop -t {timeout} {container}",
            expected_exit_code=0,
        )

    def remove_container(self, container: str, force: bool = False) -> None:
        """Remove a container."""
        cmd = f"rm {'-f' if force else ''} {container}"
        self.run(cmd, expected_exit_code=0)

    def get_container_logs(self, container: str, tail: Optional[int] = None) -> str:
        """Get logs from a container."""
        cmd = f"logs {container}"
        if tail:
            cmd += f" --tail {tail}"
        result = self.run(cmd)
        return result.stdout

    def container_exists(self, container: str) -> bool:
        """Check if a container exists."""
        result = self.run(
            f"ps -a --filter name={container} --format '{{{{.Names}}}}'",
            expected_exit_code=0,
        )
        return container in result.stdout

    def is_container_running(self, container: str) -> bool:
        """Check if a container is running."""
        result = self.run(
            f"ps --filter name={container} --format '{{{{.Names}}}}'",
            expected_exit_code=0,
        )
        return container in result.stdout

    def image_exists(self, image: str) -> bool:
        """Check if a container image exists locally."""
        result = self.run(
            f"images -q {image}",
            expected_exit_code=0,
        )
        return bool(result.stdout.strip())

    def get_full_image_name(
        self,
        image: str,
        registry_url: Optional[str] = None,
    ) -> str:
        """Get the full image name including registry URL if provided."""
        return f"{registry_url}/{image}" if registry_url else image