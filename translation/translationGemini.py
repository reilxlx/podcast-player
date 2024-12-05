import requests
import json
import re
from typing import Optional


url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent'
api_key = ''
headers = {
    'Content-Type': 'application/json'
}

def translate_text(source_text: str, lang_from: str = "English", lang_to: str = "Chinese") -> Optional[str]:
    """
    翻译文本并进行错误处理
    
    Args:
        source_text: 要翻译的源文本
        lang_from: 源语言
        lang_to: 目标语言
    
    Returns:
        翻译后的文本，如果发生错误则返回None
    """
    try:
        prompt_text = f"""
        As an academic expert with specialized knowledge in various fields, please provide a proficient and precise translation from {lang_from} to {lang_to} of the academic text enclosed in 🔤. It is crucial to maintaining the original phrase or sentence and ensure accuracy while utilizing the appropriate language. The text is as follows:  🔤 {source_text} 🔤  Please provide the translated result without any additional explanation and remove 🔤.
        """

        data = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text}
                    ]
                }
            ]
        }

        response = requests.post(
            f"{url}?key={api_key}",
            headers=headers,
            data=json.dumps(data),
            timeout=30
        )

        response.raise_for_status()            

        response_data = response.json()


        if not response_data.get("candidates"):
            raise ValueError("No translation candidates in response")

        if not response_data["candidates"][0].get("content"):
            raise ValueError("No content in translation response")

        answer_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        return answer_text.strip()             

    except requests.RequestException as e:
        print(f"网络请求错误: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"响应格式错误: {e}")
        return None
    except Exception as e:
        print(f"未预期的错误: {e}")
        return None


if __name__ == "__main__":
    langFrom = "English"
    langTo = "Chinese"
    sourceText = "Hey, everyone, and welcome back for another deep dive. Today we're going to be looking at something pretty wild. It's this new paper from Meta all about. Well, the title is kind of a mouthful, but it's basically about teaching AI to think."

    result = translate_text(sourceText, langFrom, langTo)
    if result:
        print("翻译结果:", result)
    else:
        print("翻译失败")