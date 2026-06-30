import re
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

URL_RE = re.compile(r"https?://[^\s]+")
PR_PREFIXES = ("【PR】", "#PR")
INTERNAL_DECISION_RE = re.compile(r"\b(buy|consider|skip)\b|判定は(?:buy|consider|skip)です", re.IGNORECASE)


@dataclass
class QualityResult:
    text: str
    quality_score: float
    status: str
    warnings: List[str] = field(default_factory=list)
    rejection_reason: str | None = None


class ComplianceService:
    """Threads投稿前のPython側品質・規約チェック。

    Gemini生成文は自然でも、法規制・ASP規約・Threads制限はコードで固定的に守る。
    quality_scoreは改善余地、warningsは修正ヒント、rejection_reasonは投稿停止理由を表す。
    """
    PHARMA_NG_WORDS = [
        "シミが消える",
        "免疫力アップ",
        "脂肪分解",
        "治る",
        "完治",
        "絶対痩せる",
        "医師不要",
    ]
    AFFILIATE_SMELL_WORDS = [
        "おすすめ",
        "大人気",
        "これ一つで全て解決",
        "今すぐ買うべき",
        "最強",
        "神アイテム",
    ]

    @classmethod
    def check_post(
        cls,
        text: str,
        *,
        has_affiliate_or_lp: bool = False,
        hook: str | None = None,
        existing_hooks: Iterable[str] | None = None,
        product_title: str | None = None,
        auto_fix_pr: bool = False,
    ) -> QualityResult:
        """投稿本文を検査し、queued/rejected相当の判定を返す。

        publish直前にも同じ検査を行うことで、手動編集や再生成で混入した違反表現を止める。
        """
        normalized = text.strip()
        if has_affiliate_or_lp and auto_fix_pr:
            normalized = cls.ensure_front_pr(normalized)

        warnings: List[str] = []
        score = 100.0

        if len(normalized) > 500:
            return QualityResult(normalized, 0.0, "rejected", rejection_reason="text_length_exceeds_500")

        urls = URL_RE.findall(normalized)
        if len(urls) > 1:
            return QualityResult(normalized, 0.0, "rejected", rejection_reason="too_many_urls")

        if any("px.a8.net" in url or "a8.net" in url for url in urls):
            return QualityResult(normalized, 0.0, "rejected", rejection_reason="a8_direct_link_forbidden")

        if has_affiliate_or_lp and not cls._has_front_pr(normalized):
            # ステマ規制対策として、PR表記は末尾タグではなく冒頭に置く。
            return QualityResult(normalized, 0.0, "rejected", rejection_reason="missing_front_pr")

        if INTERNAL_DECISION_RE.search(normalized):
            warnings.append("内部判定値が本文に露出しています")
            score -= 30

        existing_hook_set = {item for item in (existing_hooks or []) if item}
        if hook and hook in existing_hook_set:
            warnings.append("hookが過去生成済み投稿と重複しています")
            score -= 15

        for word in cls.PHARMA_NG_WORDS:
            if word in normalized:
                # 薬機法・誇大表現はアカウント停止や法務リスクが高いためreject扱い。
                return QualityResult(
                    normalized,
                    0.0,
                    "rejected",
                    warnings=[f"薬機法・誇大表現: {word}"],
                    rejection_reason="regulated_expression_detected",
                )

        for word in cls.AFFILIATE_SMELL_WORDS:
            if word in normalized:
                # 売り込み臭の強い表現はBANというより読者離脱・低品質化を招くため減点。
                warnings.append(f"売り込み臭の強い表現: {word}")
                score -= 20

        if product_title and not cls._has_context(normalized, product_title):
            warnings.append("商品名と本文の文脈が薄い可能性があります")
            score -= 15

        if len(normalized) > 220:
            warnings.append("推奨文字数120〜220文字を超えています")
            score -= 5
        elif has_affiliate_or_lp and len(normalized) < 80:
            warnings.append("投稿が短く、文脈不足の可能性があります")
            score -= 3

        status = "queued" if score >= 80 else "rejected"
        return QualityResult(normalized, max(score, 0.0), status, warnings=warnings)

    @classmethod
    def check_and_format_post(cls, text: str, has_link: bool) -> Tuple[str, bool]:
        result = cls.check_post(text, has_affiliate_or_lp=has_link, auto_fix_pr=True)
        return result.text, result.status == "rejected"

    @classmethod
    def ensure_front_pr(cls, text: str) -> str:
        cleaned = re.sub(r"(\s|^)(#PR|【PR】)\s*$", "", text).strip()
        if cls._has_front_pr(cleaned):
            return cleaned
        return f"【PR】{cleaned}"

    @staticmethod
    def _has_front_pr(text: str) -> bool:
        stripped = text.lstrip()
        return stripped.startswith(PR_PREFIXES)

    @staticmethod
    def _has_context(text: str, product_title: str) -> bool:
        title_terms = [term for term in re.split(r"[\s・、。/／\-ー]+", product_title) if len(term) >= 2]
        if any(term in text for term in title_terms):
            return True
        context_terms = ["家事", "時間", "片付け", "掃除", "キッチン", "投資", "時短", "夜", "負担", "摩擦"]
        return sum(1 for term in context_terms if term in text) >= 2
