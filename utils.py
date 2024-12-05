
import hashlib

def get_file_hash(file_path):
    """计算文件的MD5哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def format_time(ms):
    """将毫秒格式化为HH:MM:SS或MM:SS格式"""
    s = ms // 1000
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    if h > 0:
        return f'{h:02}:{m:02}:{s:02}'
    else:
        return f'{m:02}:{s:02}'
