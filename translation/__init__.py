from . import translationGoogle
from . import translationGemini
from . import translationSiliconCloud


def translate_text(text, translator_type='google', api_key=None):
    """
    统一的翻译接口
    
    Args:
        text: 要翻译的文本
        translator_type: 翻译器类型 ('google', 'gemini', 'silicon_cloud')
        api_key: API密钥（对于需要的翻译器）
    
    Returns:
        翻译后的文本
    """
    try:
        if translator_type == 'google':
            return translationGoogle.google_translate(text)
        elif translator_type == 'gemini':
            return translationGemini.translate_text(text, api_key=api_key)
        elif translator_type == 'silicon_cloud':
            return translationSiliconCloud.translate_to_chinese(text, api_key=api_key)
        else:
            raise ValueError(f"不支持的翻译器类型: {translator_type}")
    except Exception as e:
        print(f"翻译出错: {e}")
        return None

__all__ = ['translationGoogle', 'translationGemini', 'translationSiliconCloud', 'translate_text']
