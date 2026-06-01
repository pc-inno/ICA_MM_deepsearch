"""Fetch URL tool for MCP Tools Framework."""

import asyncio
import logging
import os
import ssl
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx
import trafilatura
from openai import AsyncOpenAI

from mcp_tools.core.base_tool import BaseTool, ToolInput, ToolOutput, ToolSchema
from mcp_tools.config.loader import config_loader

class FetchUrlInput(ToolInput):
    """Input schema for fetch URL."""
    url: str = Field(description="URL to fetch and extract content from")
    query: str = Field(description="Query to guide content summarization if content exceeds 1000 characters")


class FetchUrlTool(BaseTool):
    """Tool for fetching and summarizing web page content."""

    def __init__(self):
        super().__init__(
            name="fetch_url",
            description="Fetch web page content and summarize based on query. If the content is less than 1000 characters, it will be returned as is.",
            requires_sandbox=False
        )
        self.logger = logging.getLogger(__name__)
        self.config = config_loader.load_config()

        # Initialize AsyncOpenAI client for Qwen model
        self.client = AsyncOpenAI(
            api_key=self.config.fetch_url.api_key,
            base_url=self.config.fetch_url.base_url
        )
        self.logger.info("FetchUrlTool initialized, base_url: %s", self.config.fetch_url.base_url)

    def get_schema(self) -> ToolSchema:
        """Get the tool schema for MCP protocol."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch and extract content from"
                    },
                    "query": {
                        "type": "string",
                        "description": "Query to guide content summarization"
                    }
                },
                "required": ["url", "query"]
            },
            requires_sandbox=False,
            extra_schema={
                "type": "object",
                "properties": {
                    "sandbox_id": {
                        "type": "string",
                        "default": "sandbox_default",
                        "description": "ID of the sandbox to use for execution"
                    },
                },
            }
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> FetchUrlInput:
        """Validate and parse input data."""
        return FetchUrlInput(**input_data)

    async def execute(self, input_data: FetchUrlInput) -> ToolOutput:
        """Execute the fetch URL tool."""
        # Fetch the web page content with timeout
        try:
            content, error = await asyncio.wait_for(
                self._fetch_and_extract(input_data.url),
                timeout=15.0  # 30 seconds timeout for fetching
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Fetch and extract operation timed out for URL: {input_data.url}")
            return ToolOutput(
                success=False,
                error=f"Operation timed out while fetching content from URL: {input_data.url}"
            )
        
        if error:
            return ToolOutput(
                success=False,
                error=error
            )
        
        if not content:
            return ToolOutput(
                success=False,
                error="Failed to extract content from URL"
            )
        
        # If content is less than 1000 characters, return as is
        if len(content) <= 1000:
            return ToolOutput(
                success=True,
                data={
                    "url": input_data.url,
                    "content": content,
                    "summarized": False,
                    "length": len(content)
                }
            )
        
        # Otherwise, summarize using QwQ model with timeout
        try:
            summary, summary_error = await asyncio.wait_for(
                self._summarize_content(content, input_data.query),
                timeout=50.0  # 50 seconds timeout for summarization
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"Summarization operation timed out for URL: {input_data.url}")
            # If summarization times out, return truncated content with a note
            return ToolOutput(
                success=True,
                data={
                    "url": input_data.url,
                    "content": content[:1000] + "...\n\n[Note: Content was truncated. Summarization timed out after 50 seconds.]",
                    "summarized": False,
                    "original_length": len(content),
                    "truncated": True
                }
            )
        
        if summary_error:
            # If summarization fails, return truncated content with a note
            return ToolOutput(
                success=True,
                data={
                    "url": input_data.url,
                    "content": content[:1000] + "...\n\n[Note: Content was truncated. Summarization failed: " + summary_error + "]",
                    "summarized": False,
                    "original_length": len(content),
                    "truncated": True
                }
            )
        
        return ToolOutput(
            success=True,
            data={
                "url": input_data.url,
                "content": summary,
                "summarized": True,
                "original_length": len(content),
                "summary_length": len(summary)
            }
        )

    async def _fetch_and_extract(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """Fetch web page and extract main content using trafilatura.
        
        Returns:
            tuple: (content, error_message) where one of them will be None
        """
        max_retries = 3
        retry_delay = 1.0
        html = None
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Set more comprehensive headers to mimic a real browser
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                    "Referer": "https://www.google.com/"
                }
                
                # Add delay between retries
                if attempt > 0:
                    await asyncio.sleep(retry_delay * attempt)
                
                # Create a custom SSL context that allows legacy renegotiation
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                # Enable legacy renegotiation for older servers
                ssl_context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
                
                # Fetch HTML content with longer timeout and retry logic
                async with httpx.AsyncClient(
                    timeout=10.0, 
                    follow_redirects=True,
                    max_redirects=5,  # Limit maximum redirects to 5
                    http2=True,  # Enable HTTP/2 support
                    verify=ssl_context  # Use custom SSL context
                ) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    html = response.text
                    break  # Success, exit retry loop
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    self.logger.warning(f"HTTP 403 for URL {url} (attempt {attempt + 1}/{max_retries})")
                    last_error = (
                        f"Access denied (HTTP 403). The website '{url}' is blocking automated requests. "
                        "This could be due to rate limiting, WAF protection, or bot detection. "
                        "Please try a different URL or access the site manually."
                    )
                    if attempt < max_retries - 1:
                        continue  # Retry
                elif e.response.status_code == 404:
                    last_error = f"Page not found (HTTP 404). The URL '{url}' does not exist."
                    break  # Don't retry for 404
                elif e.response.status_code >= 500:
                    self.logger.warning(f"Server error {e.response.status_code} for URL {url} (attempt {attempt + 1}/{max_retries})")
                    last_error = f"Server error (HTTP {e.response.status_code}). The website is experiencing issues. Please try again later."
                    if attempt < max_retries - 1:
                        continue  # Retry for server errors
                else:
                    last_error = f"HTTP error {e.response.status_code}: {e.response.text[:200]}"
                    break  # Don't retry for other errors
            except httpx.TimeoutException:
                self.logger.warning(f"Timeout for URL {url} (attempt {attempt + 1}/{max_retries})")
                last_error = f"Request timeout. The website took too long to respond. Please try again later."
                if attempt < max_retries - 1:
                    continue  # Retry on timeout
            except httpx.RequestError as e:
                self.logger.warning(f"Request error for URL {url}: {e} (attempt {attempt + 1}/{max_retries})")
                last_error = f"Network error: {str(e)}"
                if attempt < max_retries - 1:
                    continue  # Retry on network errors
            except Exception as e:
                self.logger.error(f"Unexpected error fetching URL {url}: {e}")
                last_error = f"Unexpected error: {str(e)}"
                break  # Don't retry for unexpected errors
        
        if html is None:
            return None, last_error or "Failed to fetch HTML content after all retries"
        
        try:
            # Extract text content using trafilatura
            # Run in executor since trafilatura is synchronous
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: trafilatura.extract(
                    html,
                    include_comments=False,
                    include_images=False,
                    include_tables=False,
                    favor_recall=True,
                    fast=True
                )
            )
            
            if not text:
                return None, "Could not extract readable content from the page. The page may be empty or use unsupported formats."
            
            return text, None
        except Exception as e:
            self.logger.error(f"Error extracting content: {e}")
            return None, f"Content extraction failed: {str(e)}"

    async def _summarize_content(self, content: str, query: str) -> tuple[str, Optional[str]]:
        """Summarize content using QwQ model based on the query.
        
        Returns:
            tuple: (summary, error_message) where error_message is None on success
        """
        max_retries = 3
        retry_delay = 1.0
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Add delay between retries
                if attempt > 0:
                    await asyncio.sleep(retry_delay * attempt)
                
                prompt = f"""
You are given a question and content of a page or document.
1. Extract the most relevant key information from the content that directly addresses or relates to the question.
2. Provide a concise overall summary of the entire content.
3. The extracted text should summarize relevant facts instead of only providing a short phrase.
4. The result must be concise, informative, and no longer than 300 characters in total.
5. Do not add extra interpretation beyond the content.
6. Only output the results; do not add headers such as "Key information" or "Summary".
7. When no relevant information can be detected, or the retrieved content is unreadable/garbled, the system MUST return exactly the following message: "No relevant information found."

Input:
- Question: {query}
- Content: {content}

Output:
- The extracted information and summary must be written in complete sentences rather than a single phrase.
- a concise overall summary of the entire content."""



                # Use AsyncOpenAI for non-blocking API call
                completion = await self.client.chat.completions.create(
                    model=self.config.fetch_url.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024*10,
                )
                
                if not completion or not hasattr(completion, 'choices') or not completion.choices:
                    raise ValueError("Invalid API response: missing choices")
                
                if not completion.choices[0].message or not hasattr(completion.choices[0].message, 'content'):
                    raise ValueError("Invalid API response: missing message content")
                
                # Extract summary from response
                summary = completion.choices[0].message.content
                if not summary:
                    raise ValueError("Empty summary received from API")
                    
                return summary, None
                
            except Exception as e:
                self.logger.warning(f"Summarization error (attempt {attempt + 1}/{max_retries}): {e}")
                last_error = f"AI summarization failed: {str(e)}"
                if attempt < max_retries - 1:
                    continue  # Retry
        
        return "", last_error
