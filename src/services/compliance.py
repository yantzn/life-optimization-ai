import re

class ComplianceService:
    NG_WORDS = {
        "シミが消える": "シミの悩みをケアする",
        "免疫力アップ": "健康維持をサポートする",
        "脂肪分解": "スッキリをサポート",
        "治る": "改善が期待できる",
        "完治": "健康的な状態へ",
        "絶対痩せる": "ダイエットをサポート",
        "誰でも必ず": "多くの方が"
    }

    @staticmethod
    def filter_text(text: str) -> tuple[str, bool]:
        """
        Returns (filtered_text, is_rejected)
        """
        filtered_text = text
        for ng_word, safe_word in ComplianceService.NG_WORDS.items():
            if ng_word in filtered_text:
                filtered_text = filtered_text.replace(ng_word, safe_word)
        
        return filtered_text, False

    @staticmethod
    def check_and_format_post(text: str, has_link: bool) -> tuple[str, bool]:
        """
        Returns (formatted_text, is_rejected)
        """
        # 1. 薬機法NG表現を検出・置換
        text, is_rejected = ComplianceService.filter_text(text)
        if is_rejected:
            return text, True

        # 2. PR表記の強制挿入
        if has_link:
            # '#PR' を末尾ハッシュタグだけに置く実装は禁止
            # 念のため末尾の#PRは取り除く（文脈上置換する）
            text = re.sub(r'#PR$', '', text).strip()
            
            # 冒頭に 【PR】 がなければ付与
            if not text.startswith("【PR】"):
                text = f"【PR】\n{text}"

        # 3. Threads文字数制限 (最大500文字)
        if len(text) > 500:
            return text, True
            
        # 4. A8.net の直接URLをThreads本文に入れない
        if "px.a8.net" in text:
            return text, True
            
        # 5. リンクは原則1件まで (簡易チェック: httpの数)
        if text.count("http://") + text.count("https://") > 1:
            return text, True
            
        return text, False