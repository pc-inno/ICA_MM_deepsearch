"""Base tool interface for MCP Tools Framework."""

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, ClassVar
from pydantic import BaseModel
from threading import Lock
from ..config.loader import config_loader

class ToolInput(BaseModel):
    """Base input model for tools."""
    sandbox_id: Optional[str] = None  # Injected by framework for sandbox-aware tools
    
    class Config:
        extra = "allow"


class ToolOutput(BaseModel):
    """Base output model for tools."""
    success: bool
    data: Any = None
    error: Optional[str] = None


class ToolSchema(BaseModel):
    """Schema definition for a tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    requires_sandbox: bool = False
    extra_schema: Optional[Dict[str, Any]] = None


class BaseTool(ABC):
    """Abstract base class for all MCP tools."""
    
    # Class-level variables for global statistics 
    _stats = {'total_calls': 0, 'success_calls': 0}
    _tool_calls: Dict[str, int] = {}
    _tool_success_calls: Dict[str, int] = {}
    _tool_total_duration: Dict[str, float] = {}  # Total duration per tool for calculating average
    _tool_max_duration: Dict[str, float] = {}  # Max duration per tool
    _tool_duration_count: Dict[str, int] = {}  # Count of durations recorded per tool
    _stats_lock = Lock()
    _log_interval = 1000  # Log every 1000 calls
    
    def __init__(self, name: str, description: str, requires_sandbox: bool = False):
        self.name = name
        self.description = description
        self.requires_sandbox = requires_sandbox
        self.config = config_loader.load_config()
        # Default timeout (seconds) for validate+execute. Can be overridden per-call.
        self.timeout_seconds = self.config.sandbox.tool_execution_timeouts
        
        # Initialize tool call counter
        with BaseTool._stats_lock:
            if self.name not in BaseTool._tool_calls:
                BaseTool._tool_calls[self.name] = 0
            if self.name not in BaseTool._tool_success_calls:
                BaseTool._tool_success_calls[self.name] = 0
            if self.name not in BaseTool._tool_total_duration:
                BaseTool._tool_total_duration[self.name] = 0.0
            if self.name not in BaseTool._tool_max_duration:
                BaseTool._tool_max_duration[self.name] = 0.0
            if self.name not in BaseTool._tool_duration_count:
                BaseTool._tool_duration_count[self.name] = 0
    
    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Get the tool schema for MCP protocol."""
        pass
    
    @abstractmethod
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Execute the tool with given input."""
        pass
    
    async def validate_input(self, input_data: Dict[str, Any]) -> ToolInput:
        """Validate and parse input data."""
        return ToolInput(**input_data)
    
    @classmethod
    def _increment_call_stats(cls, tool_name: str, success: bool = False, duration: Optional[float] = None) -> None:
        """Increment call statistics and log when reaching milestones.
        
        Args:
            tool_name: Name of the tool being called
            success: Whether the tool call was successful
            duration: Duration of the tool call in seconds
        """
        logger = logging.getLogger(__name__)
        
        with cls._stats_lock:
            # Increment tool-specific counter
            cls._tool_calls[tool_name] = cls._tool_calls.get(tool_name, 0) + 1
            # Increment total counter
            cls._stats['total_calls'] += 1
            
            # Increment success counters if successful
            if success:
                cls._tool_success_calls[tool_name] = cls._tool_success_calls.get(tool_name, 0) + 1
                cls._stats['success_calls'] += 1
            
            # Record duration if provided
            if duration is not None:
                if tool_name not in cls._tool_total_duration:
                    cls._tool_total_duration[tool_name] = 0.0
                if tool_name not in cls._tool_max_duration:
                    cls._tool_max_duration[tool_name] = 0.0
                if tool_name not in cls._tool_duration_count:
                    cls._tool_duration_count[tool_name] = 0
                    
                cls._tool_total_duration[tool_name] += duration
                cls._tool_duration_count[tool_name] += 1
                if duration > cls._tool_max_duration[tool_name]:
                    cls._tool_max_duration[tool_name] = duration
            
            total_count = cls._stats['total_calls']
            
            # Log when total calls reach multiples of 1000
            if total_count % cls._log_interval == 0 or total_count == 1:
                total_success = cls._stats['success_calls']
                success_rate = (total_success / total_count * 100) if total_count > 0 else 0
                
                # Build a summary of all tool calls with success rates and duration stats
                tool_stats = []
                for name in sorted(cls._tool_calls.keys()):
                    calls = cls._tool_calls[name]
                    successes = cls._tool_success_calls.get(name, 0)
                    rate = (successes / calls * 100) if calls > 0 else 0
                    
                    # Calculate duration statistics
                    duration_count = cls._tool_duration_count.get(name, 0)
                    if duration_count > 0:
                        total_duration = cls._tool_total_duration.get(name, 0.0)
                        avg_duration = total_duration / duration_count
                        max_duration = cls._tool_max_duration.get(name, 0.0)
                        tool_stats.append(
                            f"{name}: {successes}/{calls} ({rate:.1f}%), "
                            f"avg={avg_duration:.3f}s, max={max_duration:.3f}s"
                        )
                    else:
                        tool_stats.append(f"{name}: {successes}/{calls} ({rate:.1f}%)")
                
                tool_stats_str = ", ".join(tool_stats)
                logger.info(
                    f"[Tool Stats] Total: {total_success}/{total_count} ({success_rate:.1f}%) - [{tool_stats_str}]"
                )

    
    async def __call__(self, input_data: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        """Call the tool with input data and return serialized output.
        
        Args:
            input_data: Tool-specific input parameters
            sandbox_id: Optional sandbox identifier (injected for sandbox-aware tools)
            timeout: Optional timeout in seconds (overrides default)
        """
        logger = logging.getLogger(__name__)
        
        try:
            logger.debug(f"Tool '{self.name}' called with input: {input_data}")
            # Allow per-call override, otherwise use instance default
            effective_timeout = timeout if timeout is not None else self.timeout_seconds

            logger.debug(f"[Tool '{self.name}'] Starting execution (sandbox={input_data.get('sandbox_id')}, timeout={effective_timeout}s)")

            validated_input = await self.validate_input(input_data)
            
            start_time = time.monotonic()
            result = await asyncio.wait_for(self.execute(validated_input), timeout=effective_timeout)
            end_time = time.monotonic()
            duration = end_time - start_time
        
            # Increment call statistics with success status and duration
            self._increment_call_stats(self.name, success=result.success, duration=duration)

            logger.debug(f"Tool '{self.name}' execution completed in {duration:.2f}s with result: {result}")
            return result.model_dump()
        
        except asyncio.TimeoutError:
            end_time = time.monotonic()
            duration = end_time - start_time
            logger.warning(f"Tool '{self.name},sandbox={input_data.get('sandbox_id')},timed out after {effective_timeout} seconds, real time: {duration:.2f}s")
            # Increment call statistics for timeout (failed call)
            self._increment_call_stats(self.name, success=False, duration=duration)
            return ToolOutput(
                success=False,
                error=f"Tool '{self.name},timed out after {effective_timeout} seconds"
            ).model_dump()
        except Exception as e:
            end_time = time.monotonic()
            duration = end_time - start_time if 'start_time' in locals() else 0.0
            logger.error(f"Tool '{self.name}',parameters:{input_data} execution error: {str(e)}", exc_info=True)
            # Increment call statistics for exception (failed call)
            self._increment_call_stats(self.name, success=False, duration=duration)
            return ToolOutput(
                success=False,
                error=f"Tool '{self.name},error: {str(e)}"
            ).model_dump()