import asyncio
import logging
import random
import re
import ssl
import time
from typing import List, Optional, Tuple

import httpx
import tiktoken
import trafilatura

logger = logging.getLogger(__name__)


# =========================================================================
# LLM Prompt Templates
# =========================================================================

summarize_webpage_with_points = """"
You are given the full text content of a webpage.

Your task is to transform the content into question-ready knowledge, suitable for generating general factual questions later.

Do NOT describe the webpage itself.
Do NOT mention websites, pages, archives, or navigation.
Focus only on the real-world entities, facts, relationships, events, studies, people, places, or concepts described in the content.

IMPORTANT SUITABILITY CHECK:
Before writing any summary or extraction, determine whether the content contains
clear, concrete, real-world facts that could reasonably support general factual questions
(e.g., identifiable entities, attributes, relationships, dates, locations, actions, or outcomes).

If the content is NOT suitable for generating such questions
(for example: navigation lists, indexes, empty pages, purely generic descriptions,
or content without concrete factual substance),
THEN:
- Return ONLY the following JSON and NOTHING ELSE:
{{
"suitable": false
}}

If the content IS suitable, proceed with the tasks below.

Please do the following:

1) Generate a concise, neutral title that reflects the main subject matter (not the webpage).
2) Write a brief summary that describes the core topics and findings in a general, standalone way.
3) Extract clear, atomic information points that:
- Can stand alone without needing webpage context
- Describe facts, comparisons, attributes, or relationships
- Are phrased so they could naturally be turned into general questions
- Avoid meta-language such as “this page”, “this article”, “the website”, or “the archive”

Return ONLY a valid JSON object with exactly these keys:
- suitable: true
- title: string
- summary: string
- information_points: array of strings

Webpage content:
{content}
"""


# ============================================================================
# Global Statistics for fetch_and_extract
# ============================================================================

class FetchStatistics:
    """Global statistics tracker for fetch_and_extract function."""
    
    def __init__(self, log_interval: int = 1000):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.log_interval = log_interval
        self._lock = asyncio.Lock()
    
    async def record_success(self):
        """Record a successful fetch."""
        async with self._lock:
            self.total_requests += 1
            self.successful_requests += 1
            self._auto_log_if_needed()
    
    async def record_failure(self):
        """Record a failed fetch."""
        async with self._lock:
            self.total_requests += 1
            self.failed_requests += 1
            self._auto_log_if_needed()
    
    def _auto_log_if_needed(self):
        """Automatically log statistics every log_interval requests."""
        if self.total_requests % self.log_interval == 0 or self.total_requests == 1:
            stats = self.get_statistics()
            logger.info(
                f"[Fetch Statistics] Total: {stats['total_requests']}, "
                f"Success: {stats['successful_requests']}, "
                f"Failed: {stats['failed_requests']}, "
                f"Success Rate: {stats['success_rate']}"
            )
    
    def get_success_rate(self) -> float:
        """Get the success rate as a percentage.
        
        Returns:
            Success rate (0-100), or 0 if no requests recorded
        """
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    def get_statistics(self) -> dict:
        """Get all statistics.
        
        Returns:
            Dictionary with total, successful, failed requests and success rate
        """
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{self.get_success_rate():.2f}%"
        }
    
    def reset(self):
        """Reset all statistics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0


# Global instance for tracking fetch statistics
_fetch_stats = FetchStatistics()


def get_fetch_statistics() -> dict:
    """Get current fetch statistics.
    
    Returns:
        Dictionary with fetch statistics including success rate
    """
    return _fetch_stats.get_statistics()


def reset_fetch_statistics():
    """Reset fetch statistics to zero."""
    _fetch_stats.reset()


# ============================================================================
# Token Counting and Text Processing Utilities
# ============================================================================

class TokenCounter:
    """Utility class for counting tokens using tiktoken."""
    
    def __init__(self):
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoder = None
            logger.warning("Failed to initialize tiktoken encoder, using approximation")
    
    def count(self, text: str) -> int:
        """Count tokens in text.
        
        Args:
            text: Input text string
            
        Returns:
            Number of tokens, or approximate count if encoder unavailable
        """
        if self.encoder is None:
            # Fallback: approximate 1 token ≈ 4 chars
            return len(text) // 4
        
        try:
            return len(self.encoder.encode(text))
        except Exception:
            return len(text) // 4


def remove_text_links(text: str) -> str:
    """Remove markdown format links, keeping link text.
    
    Args:
        text: Text with markdown links
        
    Returns:
        Text with links removed
    """
    return re.sub(r'\[(.*?)\]\((.*?)\)', r'\1', text)


# ============================================================================
# Text Chunking
# ============================================================================

def remove_tag(txt: str) -> str:
    """Remove position tags from text."""
    return re.sub(r"@@[\t0-9.-]+?##", "", txt)


def naive_merge(
    sections: str | list,
    chunk_token_num: int = 128,
    delimiter: str = "\n。；！？",
    overlapped_percent: int = 0,
    token_counter: Optional[TokenCounter] = None
) -> list[str]:
    """Merge text sections into chunks with specified token limits.
    
    Args:
        sections: Text string or list of (text, position) tuples
        chunk_token_num: Target token count per chunk
        delimiter: Delimiter string (can include custom delimiters in backticks)
        overlapped_percent: Percentage of overlap between chunks (0-100)
        token_counter: TokenCounter instance for counting tokens
        
    Returns:
        List of text chunks
    """
    if not sections:
        return []
    
    if token_counter is None:
        token_counter = TokenCounter()
    
    if isinstance(sections, str):
        sections = [sections]
    if isinstance(sections[0], str):
        sections = [(s, "") for s in sections]
    
    cks = [""]  
    tk_nums = [0]

    def add_chunk(t: str, pos: str = ""):
        nonlocal cks, tk_nums
        tnum = token_counter.count(t)
        if not pos:
            pos = ""
        if tnum < 8:
            pos = ""
        
        threshold = chunk_token_num * (100 - overlapped_percent) / 100.
        
        if cks[-1] == "" or tk_nums[-1] > threshold:
            if cks and overlapped_percent > 0:
                # Add overlapped content from previous chunk
                overlapped = remove_tag(cks[-1])
                overlap_start = int(len(overlapped) * (100 - overlapped_percent) / 100.)
                t = overlapped[overlap_start:] + t
            
            # Append position info if not already in text
            if pos and t.find(pos) < 0:
                t += pos
            
            cks.append(t)
            tk_nums.append(tnum)
        else:
            # Append to existing chunk
            if pos and cks[-1].find(pos) < 0:
                t += pos
            
            cks[-1] += t
            tk_nums[-1] += tnum

    # Check for custom delimiters (wrapped in backticks)
    custom_delimiters = [m.group(1) for m in re.finditer(r"`([^`]+)`", delimiter)]
    has_custom = bool(custom_delimiters)
    
    if has_custom:
        custom_pattern = "|".join(
            re.escape(t) for t in sorted(set(custom_delimiters), key=len, reverse=True)
        )
        
        cks, tk_nums = [], []
        
        for sec, pos in sections:
            # Split by custom delimiters, keeping delimiters in result
            split_sec = re.split(r"(%s)" % custom_pattern, sec, flags=re.DOTALL)
            
            for sub_sec in split_sec:
                # Skip the delimiter itself
                if re.fullmatch(custom_pattern, sub_sec or ""):
                    continue
                
                text = "\n" + sub_sec
                local_pos = pos
                if token_counter.count(text) < 8:
                    local_pos = ""
                if local_pos and text.find(local_pos) < 0:
                    text += local_pos
                
                cks.append(text)
                tk_nums.append(token_counter.count(text))
        
        return cks
    
    # Default mode: merge sections intelligently
    for sec, pos in sections:
        add_chunk("\n" + sec, pos)
    
    return cks[1:]


# ============================================================================
# Web Content Fetching
# ============================================================================

async def fetch_and_extract(url: str, max_retries: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """Fetch web page and extract main content using trafilatura.
    
    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
    
    Returns:
        tuple: (content, error_message) where one of them will be None
    """
    retry_delay = 1.0
    html = None
    last_error = None
    fetch_successful = False  # Track if this fetch attempt succeeds
    
    for attempt in range(max_retries):
        try:
            # Comprehensive browser headers
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
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
            
            # Create SSL context for compatibility
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            ssl_context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
            
            # Fetch HTML content
            async with httpx.AsyncClient(
                timeout=10.0, 
                follow_redirects=True,
                max_redirects=5,
                http2=True,
                verify=ssl_context
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html = response.text
                fetch_successful = True  # Mark fetch as successful
                break  # Success
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.warning(f"HTTP 403 for URL {url} (attempt {attempt + 1}/{max_retries})")
                last_error = f"Access denied (HTTP 403). The website '{url}' is blocking automated requests."
                if attempt < max_retries - 1:
                    continue
            elif e.response.status_code == 404:
                last_error = f"Page not found (HTTP 404). The URL '{url}' does not exist."
                break
            elif e.response.status_code >= 500:
                logger.warning(f"Server error {e.response.status_code} for URL {url}")
                last_error = f"Server error (HTTP {e.response.status_code}). Please try again later."
                if attempt < max_retries - 1:
                    continue
            else:
                last_error = f"HTTP error {e.response.status_code}"
                break
        except httpx.TimeoutException:
            logger.warning(f"Timeout for URL {url} (attempt {attempt + 1}/{max_retries})")
            last_error = f"Request timeout. The website took too long to respond."
            if attempt < max_retries - 1:
                continue
        except httpx.RequestError as e:
            logger.warning(f"Request error for URL {url}: {e}")
            last_error = f"Network error: {str(e)}"
            if attempt < max_retries - 1:
                continue
        except Exception as e:
            logger.error(f"Unexpected error fetching URL {url}: {e}")
            last_error = f"Unexpected error: {str(e)}"
            break
    
    if html is None:
        await _fetch_stats.record_failure()
        return None, last_error or "Failed to fetch HTML content after all retries"
    
    try:
        # Extract text content using trafilatura
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
            await _fetch_stats.record_failure()
            return None, "Could not extract readable content from the page."
        
        # Successfully fetched and extracted content
        await _fetch_stats.record_success()
        return text, None
    except Exception as e:
        logger.error(f"Error extracting content: {e}")
        await _fetch_stats.record_failure()
        return None, f"Content extraction failed: {str(e)}"


# ============================================================================
# Reranking Service Integration
# ============================================================================

class RerankService:
    """Client for reranking API."""
    
    def __init__(self, api_url: str | List[str], top_k: int = 2, max_retries: int = 3, max_concurrent_requests: int = 32):
        """Initialize RerankService.
        
        Args:
            api_url: Single URL string or list of URLs for rerank service
            top_k: Number of top results to return
            max_retries: Maximum retry attempts
            max_concurrent_requests: Maximum number of concurrent rerank requests
        """
        # Convert single URL to list for uniform handling
        if isinstance(api_url, str):
            self.api_urls = [api_url]
        else:
            self.api_urls = api_url
        
        if not self.api_urls:
            raise ValueError("At least one rerank API URL must be provided")
        
        self.top_k = top_k
        self.max_retries = max_retries
        logger.info(f"RerankService initialized with {len(self.api_urls)} URL(s): {self.api_urls}")
        
        # 复用的httpx.AsyncClient实例
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        
        # 并发控制
        self.max_concurrent_requests = max_concurrent_requests
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        logger.info(f"RerankService initialized with max_concurrent_requests={max_concurrent_requests}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建复用的AsyncClient实例"""
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        timeout=60.0,
                        limits=httpx.Limits(
                            max_connections=self.max_concurrent_requests,
                            max_keepalive_connections=self.max_concurrent_requests
                        )
                    )
                    logger.info("Created new httpx.AsyncClient instance for RerankService")
        return self._client
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """获取或创建并发控制的Semaphore"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
            logger.info(f"Created Semaphore with limit={self.max_concurrent_requests}")
        return self._semaphore
    
    async def cleanup(self):
        """清理资源，关闭client连接"""
        if self._client is not None:
            async with self._client_lock:
                if self._client is not None:
                    await self._client.aclose()
                    self._client = None
                    logger.info("Closed httpx.AsyncClient instance for RerankService")
    
    def _get_random_url(self) -> str:
        """Randomly select one URL from the configured list."""
        return random.choice(self.api_urls)
    
    async def rerank(self, query: str, texts: List[str]) -> Optional[str]:
        """Call rerank API and return merged relevant content (async).
        
        Args:
            query: Search query
            texts: List of text chunks
            
        Returns:
            Merged reranked content, or None if failed
        """
        # 使用并发控制
        semaphore = self._get_semaphore()
        async with semaphore:
            for attempt in range(self.max_retries):
                try:
                    # Randomly select a URL for this request
                    selected_url = self._get_random_url()
                    logger.debug(f"Using rerank URL: {selected_url} (attempt {attempt + 1}/{self.max_retries})")
                    
                    payload = {
                        "query": query,
                        "texts": texts,
                        "use_embedding": False,
                        "top_k": self.top_k,
                        "threshold": 0,
                        "threshold": 0.0
                    }
                    
                    start = time.time()
                    
                    # Use reusable client
                    client = await self._get_client()
                    response = await client.post(selected_url, json=payload)
                    
                    elapsed = time.time() - start
                    
                    if response.status_code != 200:
                        logger.error(f"Rerank API failed at {selected_url} (attempt {attempt + 1}/{self.max_retries}): {response.status_code}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep((attempt + 1) * 2)
                            continue
                        return None
                    
                    result = response.json()
                    
                    if result and "results" in result:
                        results = result["results"]
                        if results:
                            reranked_texts = [item["text"] for item in results]
                            merged_content = "##".join(reranked_texts)
                            logger.debug(f"Rerank successful at {selected_url} in {elapsed:.2f}s, returned {len(reranked_texts)} chunks")
                            return merged_content
                        else:
                            # logger.warning("No relevant chunks found after rerank")
                            return None
                    else:
                        logger.error(f"Invalid rerank response format from {selected_url}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep((attempt + 1) * 2)
                            continue
                        return None
                        
                except Exception as e:
                    logger.error(f"Exception during rerank at {selected_url} (attempt {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep((attempt + 1) * 2)
                        continue
                    return None
            
            return None

