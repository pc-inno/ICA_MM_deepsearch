"""Configuration loader for MCP Tools Framework."""

import logging
import os
import yaml
from typing import Dict, Any
from pathlib import Path

from .models import MCPToolsConfig


class ConfigLoader:
    """Configuration loader that supports YAML files and environment variables."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._config = None
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> MCPToolsConfig:
        """Load configuration from file and environment variables."""
        if self._config is not None:
            return self._config
            
        # Load from YAML file if exists
        config_data = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        # Override with environment variables
        config_data = self._apply_env_overrides(config_data)
        
        # Create and validate configuration
        self._config = MCPToolsConfig(**config_data)
        return self._config
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Server configuration
        if 'MCP_HOST' in os.environ:
            config_data.setdefault('server', {})['host'] = os.environ['MCP_HOST']
        if 'MCP_PORT' in os.environ:
            config_data.setdefault('server', {})['port'] = int(os.environ['MCP_PORT'])
        if 'MCP_DEBUG' in os.environ:
            config_data.setdefault('server', {})['debug'] = os.environ['MCP_DEBUG'].lower() == 'true'
        
        # Sandbox configuration
        if 'MCP_SANDBOX_PATH' in os.environ:
            config_data.setdefault('sandbox', {})['base_path'] = os.environ['MCP_SANDBOX_PATH']
        
        # Model configurations
        if 'OPENAI_API_KEY' in os.environ:
            config_data.setdefault('models', {}).setdefault('openai', {})['api_key'] = os.environ['OPENAI_API_KEY']
        if 'ANTHROPIC_API_KEY' in os.environ:
            config_data.setdefault('models', {}).setdefault('anthropic', {})['api_key'] = os.environ['ANTHROPIC_API_KEY']
        
        # Web search configuration
        if 'SERPER_API_KEY' in os.environ:
            config_data.setdefault('web_search', {})['api_key'] = os.environ['SERPER_API_KEY']
        if 'WEB_SEARCH_DB_URL' in os.environ:
            config_data.setdefault('web_search', {})['db_url'] = os.environ['WEB_SEARCH_DB_URL']
        
        return config_data
    
    def save_example_config(self, path: str = "config.example.yaml"):
        """Save an example configuration file."""
        example_config = {
            'server': {
                'host': 'localhost',
                'port': 8000,
                'debug': False,
                'cors_origins': ['*']
            },
            'sandbox': {
                'base_path': './sandboxes',
                'max_file_size': 104857600,  # 100MB
                'max_command_timeout': 300,
                'allowed_commands': [
                    'ls', 'cat', 'echo', 'mkdir', 'touch', 'cp', 'mv', 'rm',
                    'grep', 'find', 'head', 'tail', 'wc', 'sort', 'uniq',
                    'python3', 'node', 'npm', 'python'
                ],
                'blocked_commands': [
                    'sudo', 'su', 'chmod', 'chown', 'systemctl', 'service',
                    'kill', 'killall'
                ]
            },
            'models': {
                'openai': {
                    'api_key': 'your-openai-api-key-here',
                    'model_name': 'gpt-3.5-turbo',
                    'timeout': 30
                },
                'anthropic': {
                    'api_key': 'your-anthropic-api-key-here',
                    'model_name': 'claude-3-sonnet-20240229',
                    'timeout': 30
                }
            },
            'tools': {
                'file_operations': {
                    'enabled': True,
                    'config': {
                        # Example: use module/class to allow dynamic loading
                        # 'module': 'mcp_tools.tools.file_operations',
                        # 'class': 'FileOperationsTool'
                    }
                },
                'command_execution': {
                    'enabled': True,
                    'config': {
                        # 'module': 'mcp_tools.tools.command_execution',
                        # 'class': 'CommandExecutionTool'
                    }
                },
                'python_execute': {
                    'enabled': True,
                    'config': {
                        # If your tool lives in a custom package, specify module and class
                        # 'module': 'mcp_tools.tools.python_execute',
                        # 'class': 'PythonExecuteTool'
                    }
                },
                'model_chat': {
                    'enabled': True,
                    'config': {
                        'default_model': 'openai'
                    }
                }
            },
            'web_search': {
                'api_key': 'your-serper-api-key-here',
                'db_url': 'sqlite:///./search_cache.db'
            }
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(example_config, f, default_flow_style=False, indent=2)


# Global configuration instance
config_loader = ConfigLoader()