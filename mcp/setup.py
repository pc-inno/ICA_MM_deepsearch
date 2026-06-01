from setuptools import setup, find_packages

setup(
    name="mcp_tools",
    version="0.1.0",
    description="MCP Tools Framework with Sandbox Support",
    author="moolean",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "mcp_tools.tools.airline.data": ["*.json"]
    },
    install_requires=[
        "mcp>=1.0.0",
        "pydantic>=2.0.0",
        "uvicorn>=0.23.0",
        "fastapi>=0.104.0",
        "aiofiles>=23.0.0",
        "pyyaml>=6.0.0",
        "psutil>=5.9.0",
        "pathlib",
        "typing-extensions>=4.0.0",
        "httpx>=0.25.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "mcp-tools-server=mcp_tools.server:main",
        ],
    },
)