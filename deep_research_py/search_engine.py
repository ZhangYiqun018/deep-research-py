import asyncio
import os
from enum import Enum
from typing import Dict, List, Optional, TypedDict

from firecrawl import FirecrawlApp
from tavily import TavilyClient
from loguru import logger

class SearchResponse(TypedDict):
    data: List[Dict[str, str]]

class SearchEngineType(Enum):
    FIRECRAWL = "firecrawl"
    TAVILY = "tavily"

class SearchEngine(object):
    def __init__(self, engine_type: SearchEngineType = SearchEngineType.FIRECRAWL):
        self.engine_type = engine_type
        if self.engine_type == SearchEngineType.FIRECRAWL:
            self.engine = Firecrawl(api_key=os.environ.get("FIRECRAWL_KEY", ""), api_url=os.environ.get("FIRECRAWL_BASE_URL"))
        elif self.engine_type == SearchEngineType.TAVILY:
            self.engine = Tavily(api_key=os.environ.get("TAVILY_KEY", ""))

class Firecrawl:
    """Simple wrapper for Firecrawl SDK."""

    def __init__(self, api_key: str = "", api_url: Optional[str] = None):
        self.app = FirecrawlApp(api_key=api_key, api_url=api_url)

    async def search(
        self, query: str, timeout: int = 15000, limit: int = 5
    ) -> SearchResponse:
        """Search using Firecrawl SDK in a thread pool to keep it async."""
        try:
            # Run the synchronous SDK call in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.app.search(
                    query=query,
                ),
            )

            # Handle the response format from the SDK
            if isinstance(response, dict) and "data" in response:
                # Response is already in the right format
                return response
            elif isinstance(response, dict) and "success" in response:
                # Response is in the documented format
                return {"data": response.get("data", [])}
            elif isinstance(response, list):
                # Response is a list of results
                formatted_data = []
                for item in response:
                    if isinstance(item, dict):
                        formatted_data.append(item)
                    else:
                        # Handle non-dict items (like objects)
                        formatted_data.append(
                            {
                                "url": getattr(item, "url", ""),
                                "markdown": getattr(item, "markdown", "")
                                or getattr(item, "content", ""),
                                "title": getattr(item, "title", "")
                                or getattr(item, "metadata", {}).get("title", ""),
                            }
                        )
                return {"data": formatted_data}
            else:
                logger.error(f"Unexpected response format from Firecrawl: {type(response)}")
                return {"data": []}

        except Exception as e:
            logger.error(f"Error searching with Firecrawl: {e}")
            logger.error(
                f"Response type: {type(response) if 'response' in locals() else 'N/A'}"
            )
            return {"data": []}
        
    
class Tavily:
    def __init__(self, api_key: str = ""):
        self.client = TavilyClient(api_key=api_key)
        
    async def search(
        self, query: str, timeout: int=15_000, limit: int=5
    ) -> SearchResponse:
        """Search using Tavily SDK in a thread pool to keep it async."""
        try:
            # Run the synchronous SDK call in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.search(
                    query=query,
                    search_depth="advanced",
                    topic="general", # general or news
                    days=5, # only used if topic is news
                    max_results=limit,
                    include_answer=True,
                    include_raw_content=True,
                )
            )
            formatted_data = []
            results = response.get("results", [])
            if results:
                for item in results:
                    formatted_data.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "markdown": item.get("published_date", "") + "\n" + item.get("content", "")
                    })
                return {"data": formatted_data, "answer": response.get("answer", "")}
            else:
                logger.error(f"Unexpected response format from Tavily: {response}")
                return {"data": []}
        except Exception as e:
            logger.error(f"Error searching with Tavily: {e}")
            return {"data": []}