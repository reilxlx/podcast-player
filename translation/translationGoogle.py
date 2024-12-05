import requests
import time
from typing import Optional

def google_translate(text: str, dest_lang: str = 'zh-cn', src_lang: str = 'auto') -> Optional[str]:
    """
    使用Google翻译API进行文本翻译
    
    Args:
        text: 要翻译的文本
        dest_lang: 目标语言代码，默认为简体中文
        src_lang: 源语言代码，默认为自动检测
        
    Returns:
        翻译后的文本，如果发生错误则返回None
    """
    try:

        url = "https://translate.googleapis.com/translate_a/single"


        params = {
            "client": "gtx",
            "sl": src_lang,
            "tl": dest_lang,
            "dt": "t",
            "q": text
        }


        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }


        max_retries = 3
        for i in range(max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()


                result = response.json()
                translated_text = ''.join(part[0] for part in result[0] if part[0])
                return translated_text

            except Exception as e:
                if i == max_retries - 1:          
                    raise e
                time.sleep(1)           

    except Exception as e:
        print(f"翻译错误: {str(e)}")
        return None

if __name__ == "__main__":

    test_text = "Hello, how are you?"
    result = google_translate(test_text)

    if result:
        print(f"原文: {test_text}")
        print(f"译文: {result}")
    else:
        print("翻译失败")