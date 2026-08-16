"""
豆包（Doubao）搜索服务 — 通过 FeedCoop Global Search API 提供通用搜索能力

API 文档: https://open.feedcoopapi.com/search_api/global_search
使用 POST JSON 直调搜索接口，返回结构化搜索结果。

配置环境变量:
  DOUBAO_API_KEY           - 豆包搜索 API Key（必填）
  DOUBAO_API_BASE          - API 地址（默认 https://open.feedcoopapi.com）
  DOUBAO_TIMEOUT           - 超时秒数（默认 30）
  DOUBAO_MAX_RESULTS       - 返回结果条数，默认 10，最大 20（对应 DocCount）
  DOUBAO_MAX_SNIPPET_LENGTH - 摘要最大 tokens，默认 500，最大 3000
"""

import logging
import os
from typing import Dict, Any, List, Optional

import requests

from .general_search_base import GeneralSearchBase

logger = logging.getLogger(__name__)

_global_doubao_service: Optional['DoubaoSearchService'] = None


class DoubaoSearchService(GeneralSearchBase):
    """豆包搜索服务 — 通过 FeedCoop Global Search API 实现"""

    name = "doubao"
    BASE_URL = "https://open.feedcoopapi.com"

    def __init__(self, api_key: str = "", api_base: str = "",
                 timeout: int = 30, max_results: int = 10,
                 max_snippet_length: int = 500):
        self.api_key = api_key or os.environ.get("DOUBAO_API_KEY", "")
        self.api_base = (api_base or os.environ.get("DOUBAO_API_BASE", self.BASE_URL)
                         ).rstrip("/")
        self.timeout = timeout
        self.max_results = max_results
        self.max_snippet_length = max_snippet_length

    def is_available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "success": False, "results": [], "summary": "",
                "error": "豆包搜索 API Key 未配置",
            }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "Query": query,
                "SearchType": "web",
                "DocCount": min(max_results or self.max_results, 20),
                "MaxSnippetLength": min(self.max_snippet_length, 3000),
                "MaxImageCountPerDoc": 0,
            }

            url = f"{self.api_base}/search_api/global_search"
            logger.info(f"🌐 使用豆包搜索: {query}")
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            results = self._parse_results(data)
            summary = self._generate_summary_from_results(results)

            logger.info(f"豆包搜索完成: {len(results)} 条结果")
            return {
                "success": True,
                "results": results,
                "summary": summary,
                "error": None,
            }

        except Exception as e:
            logger.error(f"豆包搜索失败: {e}")
            return {
                "success": False, "results": [], "summary": "",
                "error": f"豆包搜索失败: {str(e)}",
            }

    def _parse_results(self, data: Dict) -> List[Dict[str, Any]]:
        """解析 FeedCoop Global Search 响应为统一格式"""
        results = []

        # 检查接口层错误
        metadata = data.get("ResponseMetadata", {})
        if metadata.get("Error"):
            logger.warning(f"豆包搜索接口错误: {metadata['Error']}")
            return results

        result = data.get("Result")
        if not result:
            return results

        if result.get("ErrorCode", 0) != 0:
            logger.warning(f"豆包搜索业务错误 [{result.get('ErrorCode')}]: {result.get('ErrorMsg')}")
            return results

        documents = result.get("Documents", [])
        for doc in documents:
            title = doc.get("Title", "")
            url = doc.get("Url", "")
            # 提取所有文本片段
            content_parts = []
            for snippet in doc.get("Snippet", []):
                if snippet.get("Type") == "text":
                    text = snippet.get("Text", "")
                    if text:
                        content_parts.append(text)
            content = "\n".join(content_parts)

            # 来源 = 站点名
            host_info = doc.get("HostInfo", {})
            source = host_info.get("Hostname", "Doubao")

            # 发布时间
            doc_info = doc.get("DocumentInfo", {})
            publish_time = doc_info.get("PublishTime", "")

            if title or content:
                results.append({
                    "title": title,
                    "url": url,
                    "content": content,
                    "source": source,
                    "publish_time": publish_time,
                })

        return results


def init_doubao_search_service(config: Dict[str, Any] = None) -> Optional[DoubaoSearchService]:
    """初始化豆包搜索服务"""
    global _global_doubao_service
    api_key = os.environ.get("DOUBAO_API_KEY", "")
    if not api_key:
        logger.info("豆包搜索: DOUBAO_API_KEY 未配置，跳过")
        _global_doubao_service = None
        return None

    _global_doubao_service = DoubaoSearchService(
        api_key=api_key,
        api_base=os.environ.get("DOUBAO_API_BASE", DoubaoSearchService.BASE_URL),
        timeout=int(os.environ.get("DOUBAO_TIMEOUT", "30")),
        max_results=int(os.environ.get("DOUBAO_MAX_RESULTS", "10")),
        max_snippet_length=int(os.environ.get("DOUBAO_MAX_SNIPPET_LENGTH", "500")),
    )
    logger.info("豆包搜索服务已初始化")
    return _global_doubao_service


def get_doubao_search_service() -> Optional[DoubaoSearchService]:
    """获取豆包搜索服务实例"""
    return _global_doubao_service