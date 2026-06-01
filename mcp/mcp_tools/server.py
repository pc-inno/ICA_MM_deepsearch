"""Main server entry point for MCP Tools Framework."""

import asyncio
import logging
import sys
import argparse
from pathlib import Path
import traceback

from .config.loader import config_loader


def setup_uncaught_exception_handler():
    """Setup global exception handler for uncaught exceptions."""
    logger = logging.getLogger(__name__)
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Call the default handler for keyboard interrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.critical("="*80)
        logger.critical("UNCAUGHT EXCEPTION - SERVER CRASHED!")
        logger.critical("="*80)
        logger.critical(f"Exception type: {exc_type.__name__}")
        logger.critical(f"Exception message: {exc_value}")
        logger.critical("Full traceback:")
        logger.critical("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        logger.critical("="*80)
        
    sys.excepthook = handle_exception


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Disable verbose third-party library logs
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.WARNING)
    logging.getLogger('mcp.server.lowlevel.server').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)


def main():
    """Main entry point for the MCP Tools Server."""
    parser = argparse.ArgumentParser(description="MCP Tools Server")
    parser.add_argument(
        "--config", 
        "-c", 
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate example configuration file and exit"
    )
    parser.add_argument(
        "--api-key",
        help="Web search API key (overrides config file)"
    )
    parser.add_argument(
        "--db-url",
        help="Database URL for search cache (overrides config file)"
    )
    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "http", "sse", "streamable-http"],
        help="Transport type: stdio (default) or fastmcp (HTTP/SSE API)"
    )
    parser.add_argument(
        "--host",
        help="Host address for FastMCP server (overrides config file)"
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port for FastMCP server (overrides config file)"
    )
    parser.add_argument(
        "--search-url",
        help="HTTP search service URL (overrides config file)"
    )
    parser.add_argument(
        "--search-port",
        type=int,
        help="HTTP search service port (overrides config file)"
    )
    parser.add_argument(
        "--memory-data-path",
        help="Path to memory data directory (overrides config file)"
    )
    parser.add_argument(
        "--fetch-base-url",
        help="Fetch URL tool base URL (overrides config file)"
    )
    parser.add_argument(
        "--fetch-api-key",
        help="Fetch URL tool API key (overrides config file)"
    )
    parser.add_argument(
        "--fetch-model-name",
        help="Fetch URL tool model name (overrides config file)"
    )
    
    args = parser.parse_args()
    
    # Generate example config if requested
    if args.generate_config:
        config_loader.save_example_config("config.example.yaml")
        print("Generated example configuration file: config.example.yaml")
        return
    
    # Setup logging
    setup_logging(args.debug)
    setup_uncaught_exception_handler()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config_loader.config_path = args.config
        config = config_loader.load_config()
        
        # Override config with command line arguments if provided
        if args.api_key:
            config.web_search.api_key = args.api_key
        if args.db_url:
            config.web_search.db_url = args.db_url
        if args.search_url:
            config.http_search.url = args.search_url
        if args.search_port:
            config.http_search.port = args.search_port
        if args.memory_data_path:
            config.sandbox.memory_data_path = args.memory_data_path
        if args.fetch_base_url:
            config.fetch_url.base_url = args.fetch_base_url
        if args.fetch_api_key:
            config.fetch_url.api_key = args.fetch_api_key
        if args.fetch_model_name:
            config.fetch_url.model_name = args.fetch_model_name
        

        transport = args.transport or config.server.transport or "stdio"
            
        # Override host and port if provided
        if args.host:
            config.server.host = args.host
        if args.port:
            config.server.port = args.port
        
        logger.info(f"Starting MCP Tools Server with config: {args.config}")
        logger.info(f"Transport mode: {transport}")
        logger.info(f"Sandbox path: {config.sandbox.base_path}")
        if transport != "stdio":
            logger.info(f"FastMCP server will listen on {config.server.host}:{config.server.port}")
        
        # Create sandbox directory if it doesn't exist
        Path(config.sandbox.base_path).mkdir(parents=True, exist_ok=True)
        
        # Create and start server
        from .core.server import MCPToolsServer
        server = MCPToolsServer(transport=transport)
        
        try:
            logger.info("Initializing FastMCP server...")
            server.start()
        except Exception as e:
            logger.critical(f"Fatal error in FastMCP server: {e}", exc_info=True)
            logger.critical("="*60)
            logger.critical("FastMCP SERVER CRASHED!")
            logger.critical(f"Error type: {type(e).__name__}")
            logger.critical(f"Error message: {str(e)}")
            logger.critical("="*60)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical(f"Unexpected server error: {e}", exc_info=True)
        logger.critical("="*60)
        logger.critical("SERVER CRASHED WITH UNEXPECTED ERROR!")
        logger.critical(f"Error type: {type(e).__name__}")
        logger.critical(f"Error message: {str(e)}")
        logger.critical("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# def cli_main():
#     """CLI entry point."""
#     asyncio.run(main())


# if __name__ == "__main__":
#     cli_main()