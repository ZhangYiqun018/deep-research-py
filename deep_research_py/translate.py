import asyncio
import json
import os
from typing import Optional

from ai.providers import openai_client
from loguru import logger


async def translate_to_english(query: str) -> str:
    """
    Translate Chinese query to English using GPT
    
    Args:
        query: Chinese query string
    
    Returns:
        str: Translated English query string, or original query if translation fails
    """
    try:
        # 检查是否需要翻译（包含中文字符）
        if not any(u'\u4e00' <= char <= u'\u9fff' for char in query):
            return query
            
        # 使用与其他部分相同的异步模式调用 OpenAI API
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai_client.chat.completions.create(
                model=os.getenv("TRANSLATION_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate the given Chinese text to English accurately and naturally."},
                    {
                        "role": "user", 
                        "content": f"Translate the following query to English: {query}"
                        "Return the response as a JSON object with a 'translation' field.",
                    }
                ],
                temperature=0.2,  # Use lower temperature for more stable translations
                top_p=0.75,
                response_format={"type": "json_object"},
            )
        )
        # Parse the JSON response
        try:
            result = json.loads(response.choices[0].message.content)
            translated_text = result.get("translation", query)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            translated_text = query
        logger.info(f"Translated '{query}' to '{translated_text}'")
        return translated_text
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return query  # If translation fails, return the original query 