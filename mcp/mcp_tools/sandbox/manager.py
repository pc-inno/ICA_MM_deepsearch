"""Sandbox management system for MCP Tools Framework."""

import logging
import os
import shutil
import json
import asyncio
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import threading
import time

import psutil

from ..config.loader import config_loader


class SandboxManager:
    """Manages isolated sandboxes for tool execution."""
    
    def __init__(self):
        self._sandboxes: Dict[str, 'Sandbox'] = {}
        self._lock = threading.RLock()
        self.config = config_loader.load_config().sandbox
        self.logger = logging.getLogger(__name__)
    
    def get_sandbox(self, sandbox_id: str) -> 'Sandbox':
        """Get or create a sandbox by ID."""
        with self._lock:
            if sandbox_id not in self._sandboxes:
                self._sandboxes[sandbox_id] = Sandbox(sandbox_id, self.config)
            return self._sandboxes[sandbox_id]
    
    def list_sandboxes(self) -> List[str]:
        """List all active sandbox IDs."""
        with self._lock:
            return list(self._sandboxes.keys())
    
    def cleanup_sandbox(self, sandbox_id: str, force: bool = False):
        """Clean up a sandbox."""
        with self._lock:
            if sandbox_id in self._sandboxes:
                sandbox = self._sandboxes[sandbox_id]
                sandbox.cleanup(force=force)
                del self._sandboxes[sandbox_id]
    
    def cleanup_all_sandboxes(self, force: bool = False):
        """Clean up all sandboxes."""
        with self._lock:
            sandbox_ids = list(self._sandboxes.keys())
            for sandbox_id in sandbox_ids:
                self.cleanup_sandbox(sandbox_id, force=force)


class Sandbox:
    """Individual sandbox instance with isolated file system and process management."""
    
    def __init__(self, sandbox_id: str, config):
        self.sandbox_id = sandbox_id
        self.config = config
        self.base_path = Path(config.base_path) / sandbox_id
        self.metadata_file = self.base_path / ".sandbox_metadata.json"
        self._running_processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
        
        # Initialize sandbox
        self._initialize()
    
    def _initialize(self):
        """Initialize the sandbox directory and metadata."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Load or create metadata
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                'sandbox_id': self.sandbox_id,
                'created_at': datetime.now().isoformat(),
                'last_accessed': datetime.now().isoformat(),
                'file_count': 0,
                'total_size': 0
            }
            self._save_metadata()
    
    def _save_metadata(self):
        """Save sandbox metadata."""
        self.metadata['last_accessed'] = datetime.now().isoformat()
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Get absolute path within sandbox, ensuring it stays within sandbox bounds."""
        # Normalize and resolve the path
        abs_path = (self.base_path / relative_path).resolve()
        
        # Ensure the path is within the sandbox
        try:
            abs_path.relative_to(self.base_path.resolve())
        except ValueError:
            raise PermissionError(f"Path {relative_path} is outside sandbox bounds")
        
        return abs_path
    
    async def read_file(self, file_path: str) -> str:
        """Read file content from sandbox."""
        abs_path = self.get_absolute_path(file_path)
        
        if not abs_path.exists():
            raise FileNotFoundError(f"File {file_path} not found in sandbox")
        
        if abs_path.stat().st_size > self.config.max_file_size:
            raise ValueError(f"File {file_path} exceeds maximum size limit")
        
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self._save_metadata()
        return content
    
    async def write_file(self, file_path: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Write content to file in sandbox."""
        abs_path = self.get_absolute_path(file_path)
        
        # Check content size
        if len(content.encode('utf-8')) > self.config.max_file_size:
            raise ValueError(f"Content exceeds maximum file size limit")
        
        # Create parent directories if needed
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = 'a' if append else 'w'
        with open(abs_path, mode, encoding='utf-8') as f:
            f.write(content)
        
        # Update metadata
        self.metadata['file_count'] = len(list(self.base_path.rglob('*'))) - 1  # Exclude metadata file
        self.metadata['total_size'] = sum(f.stat().st_size for f in self.base_path.rglob('*') if f.is_file())
        self._save_metadata()
        
        return {
            'path': file_path,
            'size': abs_path.stat().st_size,
            'created': not append
        }
    
    async def list_files(self, directory: str = ".") -> List[Dict[str, Any]]:
        """List files in sandbox directory."""
        abs_path = self.get_absolute_path(directory)
        
        if not abs_path.exists():
            raise FileNotFoundError(f"Directory {directory} not found in sandbox")
        
        if not abs_path.is_dir():
            raise ValueError(f"Path {directory} is not a directory")
        
        files = []
        for item in abs_path.iterdir():
            if item.name.startswith('.sandbox_'):
                continue  # Skip sandbox metadata files
            
            try:
                stat = item.stat()
                files.append({
                    'name': item.name,
                    'path': str(item.relative_to(self.base_path.resolve())),
                    'type': 'directory' if item.is_dir() else 'file',
                    'size': stat.st_size if item.is_file() else None,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except (OSError, ValueError):
                continue  # Skip files we can't stat
        
        self._save_metadata()
        return sorted(files, key=lambda x: (x['type'], x['name']))
    
    async def delete_file(self, file_path: str) -> Dict[str, Any]:
        """Delete file or directory from sandbox."""
        abs_path = self.get_absolute_path(file_path)
        
        if not abs_path.exists():
            raise FileNotFoundError(f"Path {file_path} not found in sandbox")
        
        if abs_path.is_dir():
            shutil.rmtree(abs_path)
        else:
            abs_path.unlink()
        
        # Update metadata
        self.metadata['file_count'] = len(list(self.base_path.rglob('*'))) - 1
        self.metadata['total_size'] = sum(f.stat().st_size for f in self.base_path.rglob('*') if f.is_file())
        self._save_metadata()
        
        return {'path': file_path, 'deleted': True}
    
    async def execute_command(self, command: str, cwd: str = ".", timeout = None) -> Dict[str, Any]:
        """Execute command in sandbox with memory and time limits."""
        import resource
        import signal
        # Security check - validate command

        base_cmd = command[0]  # Assume command is a list of strings
        if base_cmd in self.config.blocked_commands:
            raise PermissionError(f"Command '{base_cmd}' is not allowed")

        if self.config.allowed_commands and base_cmd not in self.config.allowed_commands:
            raise PermissionError(f"Command '{base_cmd}' is not in allowed commands list")

        # Set working directory
        work_dir = self.get_absolute_path(cwd)
        if not work_dir.exists():
            work_dir.mkdir(parents=True, exist_ok=True)

        # Set timeout
        if timeout is None:
            timeout = self.config.max_command_timeout
        elif timeout > self.config.max_command_timeout:
            timeout = self.config.max_command_timeout

        # Set memory limit (in bytes)
        max_memory = getattr(self.config, 'max_memory', 512)  # 默认为512MB
        if max_memory is not None:
            # Assume MB, convert to bytes
            mem_bytes = int(max_memory) * 1024 * 1024
            def set_limits():
                _, hard_memory_limit_AS = resource.getrlimit(resource.RLIMIT_AS)
                _, hard_memory_limit_DATA = resource.getrlimit(resource.RLIMIT_DATA)
                soft_memory_limit = mem_bytes
                resource.setrlimit(resource.RLIMIT_AS, (soft_memory_limit, hard_memory_limit_AS))
                resource.setrlimit(resource.RLIMIT_DATA, (soft_memory_limit, hard_memory_limit_DATA))

                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
                # Set wall-clock time alarm (more accurate than asyncio.wait_for)
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Command exceeded {timeout}s timeout")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout-1)
        else:
            set_limits = None

        process = None
        process_key = None
        
        try:
            # Log command execution start
            self.logger.debug(f"[Sandbox {self.sandbox_id}] Executing command: {' '.join(command)} (timeout={timeout}s)")
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, 'HOME': str(self.base_path)},
                preexec_fn=set_limits
            )

            # Track the process
            with self._lock:
                process_key = f"cmd_{id(process)}"
                self._running_processes[process_key] = process

            # Execute and wait for completion
            # 增加计时
            start_time = time.monotonic()
            # stdout, stderr = await asyncio.wait_for(
            #     process.communicate(),
            #     timeout=timeout
            # )
            stdout, stderr = await process.communicate()
            # await asyncio.wait_for(process.wait(), timeout=timeout)  # Ensure process has fully terminated
            stdout  = stdout.decode('utf-8', errors='replace')
            stderr  = stderr.decode('utf-8', errors='replace')

            if stderr.strip() == '':
                stderr = "command timeout, the program's complexity is too high" if process.returncode != 0 else stderr

            result = {
                'command': command,
                'return_code': process.returncode,
                'stdout': stdout,
                'stderr': stderr,
                'success': process.returncode == 0
            }

            # result = {
            #     'command': command,
            #     'return_code': process.returncode,
            #     'stdout': await self.get_output_non_blocking(process.stdout),
            #     'stderr': await self.get_output_non_blocking(process.stderr),
            #     'success': process.returncode == 0
            # }

            self.logger.debug(f"[Sandbox {self.sandbox_id}] Command completed: return_code={process.returncode}")

            end_time = time.monotonic()
            # self.logger.info(f"[Sandbox={self.sandbox_id}] Command timed out after {timeout}s: real time: {end_time - start_time:.2f}, {' '.join(command)}")
 
            self._save_metadata()
            return result

        except asyncio.TimeoutError:
            end_time = time.monotonic()
            self.logger.warning(f"[Sandbox={self.sandbox_id}] Command timed out after {timeout}s: real time: {end_time - start_time:.2f}, {' '.join(command)}")
            return {
                'command': command,
                'return_code': -1,
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'success': False
            }
        except Exception as e:
            self.logger.warning(f"[Sandbox {self.sandbox_id}] Command execution error: {e}")
            return {
                'command': command,
                'return_code': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
        finally:
            # Aggressive process cleanup - runs regardless of success, timeout, or error
            if process is not None:
                try:
                    # First try to terminate gracefully
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        # Force kill if termination doesn't work
                        # self.logger.warning(f"[Sandbox {self.sandbox_id}] Process did not terminate, sending SIGKILL")
                        if psutil.pid_exists(process.pid):
                            self._kill_process_tree(process.pid)
                        # process.kill()
                        await process.wait()
                except ProcessLookupError:
                    # Process already died
                    pass
                except Exception as e:
                    self.logger.error(f"[Sandbox {self.sandbox_id}] Error during process cleanup: {e}")
                finally:
                    # Remove from tracking
                    if process_key is not None:
                        with self._lock:
                            self._running_processes.pop(process_key, None)

    async def get_output_non_blocking(self, fd):
        res = b''
        try:
            # read up to 1MB
            res = await asyncio.wait_for(fd.read(1024 * 1024), timeout=0.0001)
        except asyncio.TimeoutError:
            pass
        return self.try_decode(res)
    
    def try_decode(self, s: bytes) -> str:
        try:
            r = s.decode()
        except Exception as e:
            r = f'[DecodeError] {e}'
        return r


    def _kill_process_tree(self, pid):
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.kill()
            parent.kill()
        except Exception as e:
            self.logger.warning(f'error on killing process tree: {e}')

    
    def get_info(self) -> Dict[str, Any]:
        """Get sandbox information."""
        return {
            'sandbox_id': self.sandbox_id,
            'base_path': str(self.base_path),
            'metadata': self.metadata,
            'exists': self.base_path.exists()
        }
    
    def cleanup(self, force: bool = False):
        """Clean up sandbox resources."""
        with self._lock:
            # Terminate any running processes
            for proc in self._running_processes.values():
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    try:
                        proc.kill()
                    except:
                        pass
            
            self._running_processes.clear()
            
            # Optionally remove sandbox directory
            if force and self.base_path.exists():
                shutil.rmtree(self.base_path)


# Global sandbox manager instance
sandbox_manager = SandboxManager()