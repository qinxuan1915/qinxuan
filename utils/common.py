# 文件路径: utils/common.py
import re
from collections import Counter

class ThesisUtils:
    """
    对应原项目的 utils.js
    """
    
    @staticmethod
    def is_valid_caption(text):
        """
        对应 utils.js -> isValidCaption
        判断是否为有效的图注/表注
        """
        if not text:
            return False
        text = text.strip()
        if len(text) > 40:
            return False
        # Python 正则表达式处理中文
        if re.search(r'所示|参考|见|即', text):
            return False
        if re.search(r'[。，；;!！]$', text):
            return False
        return True

    @staticmethod
    def get_mode(arr):
        """
        对应 utils.js -> getMode
        获取数组中的众数（主要用于判断正文字号）
        """
        if not arr:
            return 0
        # 对数值进行偶数取整，模拟 JS 中的 Math.round(a/2)*2
        rounded = [round(x / 2) * 2 for x in arr]
        counts = Counter(rounded)
        # 获取出现次数最多的元素
        return counts.most_common(1)[0][0]

    @staticmethod
    def get_chapter(page_idx, chapter_map):
        """
        对应 utils.js -> getChapter
        根据页码判断当前属于第几章
        """
        for ch in chapter_map:
            if ch['start_page'] <= page_idx <= ch['end_page']:
                return ch['num']
        return 0