import os
from typing import Optional
from openai import OpenAI

api_key = ''

def translate_to_chinese(
    text: str,
    api_key: str,
    base_url: str = 'https://api.siliconflow.cn/v1',
    model: str = 'Qwen/Qwen2.5-7B-Instruct',
    timeout: int = 30
) -> str:
    """
    Translates English text to Chinese using OpenAI's ChatCompletion API.

    Parameters:
        text (str): The English text to be translated.
        api_key (str): Your OpenAI API key.
        base_url (str): The base URL for the OpenAI API. Defaults to 'https://api.siliconflow.cn/v1'.
        model (str): The model to use for translation. Defaults to 'Qwen/Qwen2.5-7B-Instruct'.
        timeout (int): The timeout in seconds for the API request. Defaults to 30.

    Returns:
        str: The translated Chinese text.

    Raises:
        ValueError: If the input text is empty.
        openai.OpenAIError: If an error occurs during the API request.
    """
    if not text.strip():
        raise ValueError("Input text for translation cannot be empty.")

    if not api_key:
        raise ValueError("OpenAI API key must be provided.")


    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout
    )

    try:

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': 'You are an expert translator. Please translate the following English text to Chinese accurately and fluently.'
                },
                {
                    'role': 'user',
                    'content': text
                }
            ],
            temperature=0.3,
            max_tokens=1024
        )


        translated_text = response.choices[0].message.content.strip()
        return translated_text

    except Exception as e:
        print(f"翻译过程中发生错误: {e}")
        raise


if __name__ == "__main__":
    try:
        english_text = "SiliconCloud has launched a tiered rate plan and free model RPM has increased by 10 times. What changes will this bring to the entire large model application field?"
        chinese_translation = translate_to_chinese(english_text, api_key='sk-', base_url='https://api.siliconflow.cn/v1')
        print("Translated Text:", chinese_translation)
    except Exception as e:
        print(f"Translation failed: {e}")
