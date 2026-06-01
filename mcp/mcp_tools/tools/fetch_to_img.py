import asyncio
import base64
import json
import logging
import math
from typing import Dict, Any, Optional, List
from io import BytesIO
from pydantic import Field, ConfigDict  # 记得导入 ConfigDict
from playwright.async_api import async_playwright, Browser, Playwright
from pydantic import Field
from PIL import Image, ImageOps
from typing import Union
import httpx  # 用于兜底请求

from mcp_tools.core.base_tool import BaseTool, ToolInput, ToolOutput, ToolSchema
from mcp_tools.config.loader import config_loader

# =============================================================================
# 辅助函数
# =============================================================================

def _need_process(w, h, max_aspect_ratio=100):
    longer, shorter = max(w, h), min(w, h)
    if longer / shorter > max_aspect_ratio:
        return True
    return False

def _should_use_jina_direct(url: str) -> bool:
    stripped = url.lower().split("?", 1)[0].split("#", 1)[0]
    return stripped.endswith((
        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"
    ))

def adaptive_resize_image(image: Union[Image.Image, dict], **kwargs) -> Image.Image:
    if isinstance(image, dict):
        image = Image.open(BytesIO(image['bytes']))
    image = ImageOps.exif_transpose(image)
    w, h = image.size
    
    max_aspect_ratio = kwargs.get('max_aspect_ratio')
    if max_aspect_ratio:
        longer, shorter = max(w, h), min(w, h)
        if longer / shorter > max_aspect_ratio:
            if w > h: w = int(h * max_aspect_ratio)
            else: h = int(w * max_aspect_ratio)
            image = image.resize((w, h), resample=Image.LANCZOS)
            
    if image.mode != 'RGB':
        image = image.convert('RGB')
    return image

# =============================================================================
# Tool 定义
# =============================================================================

class ScreenshotInput(ToolInput):
    url: List[str] = Field(description="The list of URLs to capture screenshots of")
    model_config = ConfigDict(extra='ignore')

class ScreenshotTool(BaseTool):
    """
    高并发优化版截图工具 - 批量版 (Batch Support)
    支持输入 URL 列表，返回对应的多维图片数组。
    """
    
    VIEWPORT_WIDTH = 1280
    SLICE_HEIGHT = 4480  
    OVERLAP_HEIGHT = 112
    MAX_TOTAL_LIMIT = 20000 
    DEFAULT_TIMEOUT = 60000 
    IMAGE_TAG = "<image>"
    MAX_CONCURRENT_TABS = 64
    # IMAGE_TAG = "<vision_start><image_pad><vision_end>"

    def __init__(self):
        super().__init__(
            name="fetch_url",
            description="Capture screenshots for a list of URLs. Returns structured text and nested image lists.",
            requires_sandbox=False
        )
        self.logger = logging.getLogger(__name__)
        self.config = config_loader.load_config()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._init_lock = asyncio.Lock() 

        # --- Jina AI 配置 ---
        self.jina_api_key = getattr(self.config.rerank, 'jina_api_key', None)
        self._httpx_client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        
        # ===== Browser Pool 配置 =====
        self.BROWSER_POOL_SIZE = 8  # 2~4 都可以
        self._browsers: List[Browser] = []
        self._browser_index = 0
        self._browser_lock = asyncio.Lock()
        # 控制「总 context 并发」
        self._context_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TABS)

    async def _ensure_browser_pool(self):
        if self._browsers:
            return

        async with self._init_lock:
            if self._browsers:
                return

            self._playwright = await async_playwright().start()

            for i in range(self.BROWSER_POOL_SIZE):
                browser = await self._playwright.chromium.launch(
                    headless=True,
                    proxy={
                        "server": "http://10.120.3.250:7890"
                    },
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--ignore-certificate-errors',
                        '--ignore-ssl-errors'
                    ]
                )
                self._browsers.append(browser)

            self.logger.info(f"Initialized Browser Pool size={len(self._browsers)}")

    async def _acquire_browser(self) -> Browser:
        async with self._browser_lock:
            browser = self._browsers[self._browser_index]
            self._browser_index = (self._browser_index + 1) % len(self._browsers)
            return browser


    async def aclose(self) -> None:
        try:
            if self._browser: await self._browser.close()
            if self._playwright: await self._playwright.stop()
            if self._httpx_client: await self._httpx_client.aclose()
        except: pass

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object", 
                "properties": {
                    "url": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "List of URLs"
                    }
                }, 
                "required": ["url"]
            },
            requires_sandbox=False
        )

    async def validate_input(self, input_data: Dict[str, Any]) -> ScreenshotInput:
        return ScreenshotInput(**input_data)

    async def _get_httpx_client(self) -> httpx.AsyncClient:
        """获取复用的 httpx 客户端"""
        if self._httpx_client is None:
            async with self._client_lock:
                if self._httpx_client is None:
                    self._httpx_client = httpx.AsyncClient(
                        timeout=60.0
                    )
        return self._httpx_client
    
    def _post_process_single_slice(self, img: Image.Image) -> str:
        """
        对单张切片进行统一的缩放、自适应调整和 Base64 编码
        逻辑与原 _capture_single_url 中的处理完全一致
        """
        # 1. 转 RGB
        if img.mode != 'RGB': 
            img = img.convert('RGB')
        
        # 2. 缩放 0.7 倍 (Scale)
        scale_factor = 0.7
        new_width = int(img.width * scale_factor)
        new_height = int(img.height * scale_factor)
        img = img.resize((new_width, new_height), resample=Image.LANCZOS)

        # 3. 极端长宽比处理 (Adaptive Resize)
        if _need_process(img.width, img.height, 100):
            img = adaptive_resize_image(img, max_aspect_ratio=100)
            
        # 4. 转 Base64
        return self._pil_to_base64_str(img)

    def _slice_and_process_image(self, full_img: Image.Image) -> List[Dict[str, Any]]:
        """
        将一张大图（如 Jina 返回的长图）按照 SLICE_HEIGHT 切割，并应用后处理
        模拟 Playwright 的滚动截图行为
        """
        w, h = full_img.size
        
        # --- 新增：应用最大高度限制 ---
        # 如果图片高度超过 20000px，只处理前 20000px
        effective_height = min(h, self.MAX_TOTAL_LIMIT)
        
        processed_slices = []
        
        # 如果有效高度小于切片高度，直接处理（当做一张图）
        if effective_height <= self.SLICE_HEIGHT:
            self.logger.warning(f"Image height {h} is within slice limit or clipped.")
            # 注意：这里如果原图很大但被limit裁减了，实际上也应该裁剪一下原图
            # 但通常这种情况较少见（除非 MAX_TOTAL_LIMIT 设置得比 SLICE_HEIGHT 还小）
            # 为了严谨，这里做一个 crop
            if h > effective_height:
                full_img = full_img.crop((0, 0, w, effective_height))
                
            b64 = self._post_process_single_slice(full_img)
            processed_slices.append({
                'image': b64,
                'image_wh': full_img.size, 
                'source': 'jina_fallback'
            })
            return processed_slices

        # 开始切片循环
        current_y = 0
        MIN_SLICE_HEIGHT = 200 
        
        # --- 修改：循环条件使用 effective_height ---
        while current_y < effective_height:
            # --- 修改：剩余高度计算使用 effective_height ---
            remaining = effective_height - current_y
            
            # 逻辑一致性：如果剩余部分太小且已有切片，则丢弃末尾
            if remaining < MIN_SLICE_HEIGHT and len(processed_slices) > 0:
                break
                
            # 计算裁剪区域
            slice_h = min(self.SLICE_HEIGHT, remaining)
            box = (0, current_y, w, current_y + slice_h)
            
            try:
                # self.logger.warning("slice_img!") # 调试日志可按需保留
                # Crop (left, upper, right, lower)
                slice_img = full_img.crop(box)
                
                # 应用统一的缩放和编码逻辑
                b64 = self._post_process_single_slice(slice_img)
                
                processed_slices.append({
                    'image': b64,
                    'image_wh': slice_img.size, 
                    'source': 'jina_fallback'
                })
                
            except Exception as e:
                self.logger.warning(f"Failed to crop Jina image at y={current_y}: {e}")

            # 计算下一次的 Y 坐标
            next_step = self.SLICE_HEIGHT - self.OVERLAP_HEIGHT
            current_y += next_step
            
        return processed_slices
    
    async def _fetch_with_jina_screenshot_fallback(self, url: str) -> List[Dict[str, Any]]:
        """
        截图兜底方案：智能处理 Jina 返回，并应用切片逻辑
        """
        if not self.jina_api_key:
            self.logger.warning("Jina API key not configured, skipping fallback.")
            return []
            
        self.logger.info(f"Attempting Jina AI screenshot fallback for {url}...")
        
        fetch_url = f"https://r.jina.ai/{url}"
        headers = {
            "Authorization": f"Bearer {self.jina_api_key.strip()}",
            "X-Return-Format": "pageshot",
            "X-No-Cache": "true"
        }

        try:
            client = await self._get_httpx_client()
            response = await client.get(
                fetch_url, 
                headers=headers, 
                timeout=60.0, 
                follow_redirects=True
            )
            if response.status_code != 200:
                self.logger.warning(f"Jina AI request failed: {response.status_code}")
                return []

            content_type = response.headers.get("content-type", "").lower()
            img_bytes = None
            
            # --- 1. 获取图片二进制数据 ---
            if "image" in content_type or response.content.startswith(b'\x89PNG'):
                self.logger.info("Jina returned binary image directly.")
                img_bytes = response.content
            
            elif "application/json" in content_type:
                try:
                    resp_json = response.json()
                    screenshot_url = resp_json.get("data", {}).get("screenshot")
                    if not screenshot_url: return []
                        
                    self.logger.info(f"Downloading screenshot from Jina URL: {screenshot_url}")
                    img_response = await client.get(screenshot_url, timeout=30.0, follow_redirects=True)
                    if img_response.status_code == 200:
                        img_bytes = img_response.content
                except Exception as json_err:
                    self.logger.warning(f"Failed to parse Jina JSON: {json_err}")
                    return []
            
            if not img_bytes:
                return []

            # --- 2. 统一转换为 PIL Image ---
            
            img = Image.open(BytesIO(img_bytes))
            
            # --- 3. 调用新的切片处理方法 (替代原本的直接缩放) ---
            # 这里会将长图切割成多张图，逻辑同 Playwright
            return self._slice_and_process_image(img)

        except Exception as e:
            self.logger.warning(f"Jina AI screenshot fallback error: {e}")
            return []

    async def execute(self, input_data: ScreenshotInput) -> ToolOutput:
        try:
            await self._ensure_browser_pool()
        except Exception as e:
            return ToolOutput(success=False, error=str(e))

        async def _process_one_url(url: str):
            async with self._context_semaphore:
                browser = await self._acquire_browser()

                try:
                    pil_images = await self._capture_single_url(browser, url)

                    images = []
                    tags = []
                    for img in pil_images:
                        images.append({
                            "image": self._pil_to_base64_str(img),
                            "image_wh": img.size
                        })
                        tags.append(self.IMAGE_TAG)

                    return {
                        "text": {"link": url, "images": tags},
                        "images": images
                    }

                except Exception as e:
                    self.logger.warning(f"Screenshot failed for {url}: {e}")
                    return {
                        "text": {"link": url, "error": f"Failed to capture: {e}"},
                        "images": []
                    }

        results = await asyncio.gather(
            *[_process_one_url(url) for url in input_data.url],
            return_exceptions=False
        )

        text_structures = [r["text"] for r in results]
        image_structures = [r["images"] for r in results]

        return ToolOutput(
            success=True,
            data={
                "text": text_structures,
                "image": image_structures
            }
        )


    async def _dismiss_modals(self, page):
        """
        尝试通过键盘 ESC 和点击常见的关闭按钮来移除遮罩层
        """
        try:
            # 1. 模拟按下 ESC 键 (这是关闭 Facebook 弹窗最快的方法)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

            # 2. 尝试点击常见的关闭按钮 (针对那些拦截了 ESC 的弹窗)
            # selectors 包括：aria-label 为 Close/关闭/Tutup 的元素，或 role=button 的 svg 父级
            close_selectors = [
                '[aria-label="Close"]', 
                '[aria-label="close"]',
                '[aria-label="关闭"]',
                '[aria-label="Tutup"]', # 针对您截图中可能出现的马来语
                'div[role="dialog"] [role="button"]',
                'div[role="dialog"] [aria-label*="lose"]' # 模糊匹配 Close
            ]
            
            for selector in close_selectors:
                # 检查元素是否可见，如果可见则点击
                if await page.locator(selector).first.is_visible(timeout=100):
                    try:
                        await page.locator(selector).first.click(timeout=200, no_wait_after=True)
                        self.logger.debug(f"Clicked modal close button: {selector}")
                        await asyncio.sleep(0.5)
                        break # 点击成功一个通常就够了
                    except:
                        continue
            
            # 3. 暴力移除 DOM (如果还在)
            # Facebook 的弹窗通常在 div[role="dialog"] 中
            await page.evaluate("""
                const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"]');
                dialogs.forEach(el => el.remove());
                
                // 再次确保 body 可以滚动
                document.body.style.overflow = 'visible';
                document.documentElement.style.overflow = 'visible';
            """)
            
        except Exception as e:
            # 忽略清理过程中的错误，不要阻塞主流程
            self.logger.warning(f"Dismiss modal warning: {e}")

    async def _capture_single_url(self, browser: Browser, url: str) -> List[Image.Image]:
        if not url.startswith("http"): url = "http://" + url
        
        # 使用动态视口 + 忽略证书错误
        context = await browser.new_context(
            viewport={"width": self.VIEWPORT_WIDTH, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        page = await context.new_page()
        pil_image_list = []

        try:
            self.logger.debug(f"Navigating to {url}...")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            # --- 在滚动前主动处理弹窗 ---
            
            await self._dismiss_modals(page)
            
            await page.add_init_script("""
                const style = document.createElement('style');
                style.innerHTML = `
                #cookie-banner, .cookie-banner, .modal, .popup, .ad-container { display: none !important; }
                ::-webkit-scrollbar { display: none; }
                header, nav, .sticky-header { position: absolute !important; } 
                `;
                document.head.appendChild(style);
            """)
            print('add_init_script!')

            await self._auto_scroll(page)
            print('_auto_scroll!')
            
            full_height = await page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
            full_width = await page.evaluate("Math.max(document.body.scrollWidth, document.body.offsetWidth)")
            
            full_width = min(full_width, 1920)
            full_height = min(full_height, self.MAX_TOTAL_LIMIT)
            
            view_width = int(full_width) if full_width > self.VIEWPORT_WIDTH else self.VIEWPORT_WIDTH
            current_y = 0
            
            # --- 截图循环 ---
            MIN_SLICE_HEIGHT = 200 # 定义一个最小高度，防止出现长宽比超限的窄条
            while current_y < full_height:
                print('MIN_SLICE_HEIGHT!',current_y)
                remaining = full_height - current_y
                if remaining <= 0: break
                # 如果剩余部分太小，且已经有截图了，就没必要再截这几像素了
                if remaining < MIN_SLICE_HEIGHT and len(pil_image_list) > 0:
                    break
                current_viewport_height = int(min(self.SLICE_HEIGHT, remaining))
                actual_viewport_height = max(current_viewport_height, MIN_SLICE_HEIGHT)

                await page.set_viewport_size({
                    "width": view_width,
                    "height": actual_viewport_height
                })
                await page.evaluate(f"window.scrollTo(0, {current_y})")
                await asyncio.sleep(0.5)

                try:
                    
                    image_bytes = await page.screenshot(
                        full_page=False, 
                        type='jpeg', 
                        quality=70,
                        caret="hide"
                    )
                    img = Image.open(BytesIO(image_bytes))
                    if img.mode != 'RGB': img = img.convert('RGB')
                    # 3. --- 新增：将长宽都压缩为原来的 0.7 倍 ---
                    scale_factor = 0.7
                    new_width = int(img.width * scale_factor)
                    new_height = int(img.height * scale_factor)

                    # 使用 LANCZOS 算法进行高质量缩放
                    img = img.resize((new_width, new_height), resample=Image.LANCZOS)
                    if _need_process(img.width, img.height, 100):
                        img = adaptive_resize_image(img, max_aspect_ratio=100)
                    # ----------------------------------------
                    pil_image_list.append(img)

                except Exception as slice_err:
                    self.logger.warning(f"Slice capture failed at y={current_y}: {slice_err}")

                next_step = self.SLICE_HEIGHT - self.OVERLAP_HEIGHT
                current_y += next_step
            print('pil_image_list!')
            return pil_image_list
            
        except Exception as e:
            self.logger.error(f"Capture logic error for {url}: {e}")
            raise e
        finally:
            if page: await page.close()
            if context: await context.close()

    def _pil_to_base64_str(self, image: Image.Image, quality: int = 85) -> str:
        buffer = BytesIO()
        if image.mode != 'RGB': image = image.convert('RGB')
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def _auto_scroll(self, page):
        h = 0
        while h < self.MAX_TOTAL_LIMIT:
            h += 720
            await page.evaluate(f"window.scrollTo(0, {h})")
            await asyncio.sleep(0.1)
            max_h = await page.evaluate("document.body.scrollHeight")
            if h > max_h: break
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)


# ---------------------------------------------------------------------------
# OpenAI function-calling schema (used by inference.py to declare tools)
# ---------------------------------------------------------------------------

fetch_page_tool_img = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "Fetch webpage(s) and return the screenshot of the page.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "The URL(s) of the webpage(s) to Fetch. "
                        "Can be a single URL or an array of URLs."
                    ),
                }
            },
            "required": ["url"],
        },
    },
}


# ---------------------------------------------------------------------------
# Sync MCP client wrapper (launches MCP server subprocess via StdioTransport)
# ---------------------------------------------------------------------------

def call_fetch_url_sync_img(arguments):
    """
    Synchronously call the ``fetch_url`` MCP tool that returns page screenshots.

    Launches an MCP server subprocess via ``StdioTransport``, sends the request,
    and returns the raw MCP result object.  On failure returns ``None``.

    All paths are resolved from environment variables.  The bash script
    (run_inference.sh) is the single source of truth for these paths.
    """
    import os as _os
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    _project_root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))

    pw_path = _os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    whl_path = _os.environ.get("MCP_WHL_PATH", "")
    cfg_path = _os.environ.get("MCP_CONFIG_PATH", "")
    log_path = _os.environ.get("MCP_LOG_FILE", _os.path.join(_project_root, "logs", "mcp_server.log"))

    missing = []
    if not pw_path:
        missing.append("PLAYWRIGHT_BROWSERS_PATH")
    if not whl_path:
        missing.append("MCP_WHL_PATH")
    if not cfg_path:
        missing.append("MCP_CONFIG_PATH")
    if missing:
        print(f"[call_fetch_url_sync_img] Missing required env vars: {', '.join(missing)}")
        return None

    _os.makedirs(_os.path.dirname(log_path), exist_ok=True)

    tool_name = "fetch_url"

    async def _run():
        transport = StdioTransport(
            command="bash",
            args=[
                "-c",
                f"export PLAYWRIGHT_BROWSERS_PATH={pw_path} && "
                f"UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple uv run --isolated --no-project "
                f"--with {whl_path} "
                f"mcp-tools-server --config {cfg_path} "
                f"2>> {log_path}",
            ],
            keep_alive=False,
        )
        client = Client(transport)
        try:
            async with client:
                result = await asyncio.wait_for(
                    client.call_tool(name=tool_name, arguments=arguments),
                    timeout=50,
                )
                return result
        except Exception as e:
            print(f"[call_fetch_url_sync_img] Internal error: {e}")
            return None
        finally:
            try:
                await client.close()
            except Exception:
                pass
            await asyncio.sleep(0.1)

    try:
        result = asyncio.run(_run())
        if result:
            # Debug: show what MCP returned
            if result.content:
                c0 = result.content[0]
                txt = getattr(c0, 'text', None)
                print(f"[DEBUG MCP] content[0] type={type(c0).__name__}, text[:200]={repr((txt or '')[:200])}")
            else:
                print(f"[DEBUG MCP] result.content is empty, isError={getattr(result, 'isError', '?')}")
            return result
        print("[call_fetch_url_sync_img] No valid result returned")
        return None
    except Exception as e:
        print(f"[call_fetch_url_sync_img] Failed: {e}")
        return None
