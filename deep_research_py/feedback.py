import asyncio
import json
import os
from typing import List

from ai.providers import openai_client, trim_prompt
from loguru import logger
from prompt import system_prompt
from search_engine import SearchResponse, SearchEngine, SearchEngineType
from translate import translate_to_english
from datetime import datetime

async def generate_feedback(query: str, use_search_enhancement: bool = True) -> List[str]:
    """Generates follow-up questions to clarify research direction.
    
    Args:
        query: The research topic/query
        use_search_enhancement: Whether to use search to enhance question generation
    """
    
    context = ""
    if use_search_enhancement:
        search_engine = SearchEngine(SearchEngineType.TAVILY).engine
        # Get background knowledge through search
        query = await translate_to_english(query)
        search_result = await search_engine.search(query, limit=5)
        contents = [
            trim_prompt(item.get("markdown", ""), 15_000)
            for item in search_result["data"]
            if item.get("markdown")
        ]
        search_answer = search_result.get("answer", "")
        context = "\n\nHere is some background information about the topic:\n" + \
                 "".join(f"<content>\n{content}\n</content>" for content in contents) + \
                 f"{search_answer}"
        logger.info(f"Search result: {context}")
        
    # Run OpenAI call with optional context
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: openai_client.chat.completions.create(
            model=os.getenv("REASONING_MODEL", "o3-mini"),
            messages=[
                {"role": "system", "content": system_prompt()},
                {
                    "role": "user",
                    "content": f"Given this research topic: {query}{context}, "
                    "generate 3-5 follow-up questions to better understand the user's research needs. "
                    "Return the response as a JSON object with a 'questions' array field.",
                },
            ],
            response_format={"type": "json_object"},
        ),
    )

    # Parse the JSON response
    try:
        result = json.loads(response.choices[0].message.content)
        return result.get("questions", [])
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw response: {response.choices[0].message.content}")
        return []

