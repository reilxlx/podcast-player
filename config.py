
import json
import logging
from pathlib import Path

def load_config(config_file):
    """加载配置文件"""
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except Exception as e:
            logging.error(f"加载配置文件出错: {e}")
    return None

def save_config(config_file, gemini_api_key, silicon_cloud_api_key):
    """保存配置文件"""
    try:
        config = {
            'gemini_api_key': gemini_api_key,
            'silicon_cloud_api_key': silicon_cloud_api_key
        }
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存配置文件出错: {e}")
