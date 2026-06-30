import logging
import random
from pathlib import Path
from typing import Any, Dict, Iterable, Set

from src import config
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

POST_TYPE_WEIGHTS = {
    "affiliate": 50,
    "two_line_copy": 20,
    "story": 20,
    "account_note": 10,
}


class ContentGenerator:
    """enriched_productsからThreads向けpost_candidatesを生成する。

    post_typeの意図:
    - affiliate: 商品紹介。PR表記とCTAが必須
    - two_line_copy: 2行の共感/ROI訴求コピー
    - story: 失敗談や気づきからLPへつなぐ投稿
    - account_note: アカウント運用メモ系の将来枠
    - comparison: 比較投稿の将来枠
    """

    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini
        self.prompt_dir = Path(__file__).resolve().parents[1] / "prompts"

    def generate_posts(self, *, limit: int | None = None) -> int:
        """enriched_products(status=enriched)をpost_candidates(status=draft)へ変換する。

        生成直後に即投稿せずdraftに置くのは、初期運用では人間承認を挟み、
        BANや規約違反のリスクを下げるため。
        """
        products = self.db.get_documents_by_status("enriched_products", "enriched", limit=limit)
        used_hooks = self._existing_hooks()
        processed = 0
        for product in products:
            try:
                post_type = self._choose_post_type()
                post_data = self._build_post(product, post_type, used_hooks)
                used_hooks.add(post_data["hook"])
                self.db.add_document("post_candidates", post_data)
                self.db.update_document("enriched_products", product["id"], {"status": "post_generated"})
                self.db.update_document("products", product["product_id"], {"status": "post_generated"})
                processed += 1
            except Exception as exc:
                logger.exception("post_generation_failed enriched_product_id=%s", product["id"])
                self.db.update_document(
                    "enriched_products",
                    product["id"],
                    {"status": "post_generation_error", "error_message": str(exc)},
                )
        return processed

    def _choose_post_type(self) -> str:
        types = list(POST_TYPE_WEIGHTS)
        weights = list(POST_TYPE_WEIGHTS.values())
        return random.choices(types, weights=weights, k=1)[0]

    def _build_post(self, product: Dict[str, Any], post_type: str, used_hooks: Set[str]) -> Dict[str, Any]:
        """1商品分の投稿候補を組み立てる。

        affiliate_urlをどう扱うかはsource/URLで判定する。A8はThreads本文への
        直接リンクを避け、プロフィールLP誘導へ寄せる。
        """
        context = self._context(product)
        generated = self._generate_with_prompt(post_type, context)
        hook, body, cta = self._extract_generated(generated, context, post_type)
        hook = self._unique_hook(hook or self._fallback_hook(context), context, used_hooks)
        cta = cta or self._cta(context)
        post_text = self._compose_post(post_type, hook, body, cta, context)
        post_text = self._strip_internal_decisions(post_text)
        return {
            "product_id": product.get("product_id"),
            "post_type": post_type,
            "platform": config.TARGET_PLATFORM,
            "hook": hook,
            "body": body,
            "hashtags": ["#時短", "#共働き"],
            "cta": cta,
            "post_text": post_text,
            "quality_score": 0,
            "status": "draft",
            "scheduled_at": None,
        }

    def _generate_with_prompt(self, post_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """投稿タイプ別プロンプトでGemini生成する。

        Geminiが失敗してもパイプライン確認を止めないためfallback文へ進むが、
        最終的な品質はQualityGateで必ず再評価する。
        """
        prompt_name = {
            "affiliate": "post_affiliate.txt",
            "two_line_copy": "two_line_copy.txt",
            "story": "story_post.txt",
        }.get(post_type, "story_post.txt")
        prompt_template = (self.prompt_dir / prompt_name).read_text(encoding="utf-8")
        prompt = self._render_prompt(prompt_template, context)
        try:
            return self.gemini.generate_json(prompt) or {}
        except Exception as exc:
            logger.warning("gemini_post_generation_failed fallback=true product=%s error=%s", context["title"], exc)
            return {}

    def _extract_generated(
        self,
        generated: Dict[str, Any],
        context: Dict[str, Any],
        post_type: str,
    ) -> tuple[str, str, str]:
        if post_type == "two_line_copy" and generated.get("copies"):
            copy = generated["copies"][0]
            return copy.get("line1", ""), copy.get("line2", ""), self._cta(context)
        if post_type == "story" and generated.get("post_text"):
            return generated.get("hook", ""), generated.get("post_text", ""), generated.get("cta", "") or self._cta(context)
        if generated:
            return generated.get("hook", ""), generated.get("body", ""), generated.get("cta", "") or self._cta(context)
        return self._fallback_hook(context), self._fallback_body(context, post_type), self._cta(context)

    def _context(self, product: Dict[str, Any]) -> Dict[str, Any]:
        source = product.get("source_product", {})
        roi = product.get("roi", {})
        use_cases = product.get("use_cases", [])
        pain_points = product.get("pain_points", [])
        return {
            "product": source.get("title", ""),
            "title": source.get("title", ""),
            "category": source.get("category", ""),
            "source": source.get("source", ""),
            "product_strengths": product.get("summary", ""),
            "target_persona": product.get("target_persona", ""),
            "pain_point": " / ".join(pain_points),
            "primary_pain": pain_points[0] if pain_points else "夜の家事が終わらない",
            "target_scene": source.get("target_scene") or (use_cases[0] if use_cases else "平日の夜"),
            "roi": roi.get("roi_comment", ""),
            "post_angle": source.get("post_angle", ""),
            "affiliate_url": source.get("affiliate_url", ""),
            "past_problem": pain_points[0] if pain_points else "家事が終わらず、寝る前に毎日ぐったりしていた",
            "turning_point": "気合いではなく、道具と仕組みに寄せた",
            "current_change": product.get("summary", ""),
            "message": roi.get("roi_comment", ""),
            "next_action": "プロフィールのまとめLPを見る",
        }

    def _fallback_hook(self, context: Dict[str, Any]) -> str:
        category = context["category"]
        scene = context["target_scene"]
        pain = context["primary_pain"]
        if "キッチン" in category:
            return f"夕飯後の片付け、そこで体力を削られすぎてた。"
        if "掃除" in category or "ロボット" in context["title"]:
            return f"床掃除って、気づいた瞬間にもう負けてる。"
        if scene:
            return f"{scene}を少し軽くするだけで、夜の残り方が変わる。"
        return f"{pain}なら、頑張る前に仕組みを変えたい。"

    def _fallback_body(self, context: Dict[str, Any], post_type: str) -> str:
        if post_type == "story":
            return (
                f"{context['primary_pain']}。\n"
                "前はここを気合いで押し切ろうとして、だいたい寝る前に力尽きてた。\n"
                f"{context['title']}みたいな道具は、買い物というより家事の詰まりを減らす仕組み。\n"
                f"{context['roi']}"
            )
        return (
            f"{context['title']}は、{context['target_scene']}の摩擦を減らすための道具。\n"
            f"{context['roi']}"
        )

    def _cta(self, context: Dict[str, Any]) -> str:
        """link_strategy相当のCTAを返す。

        profile_lp: A8など直接リンクを避けたい場合
        direct_link: MVPで許可した単一URLを本文に置く場合
        none: 将来の非商品投稿でリンクを置かない場合
        """
        if self._is_a8_url(context["affiliate_url"]):
            return "直接リンクではなく、プロフィールのまとめLPに置いています。"
        return "詳細はプロフィールのまとめLPから見られます。"

    def _compose_post(self, post_type: str, hook: str, body: str, cta: str, context: Dict[str, Any]) -> str:
        """PR表記とリンクを含む最終本文を組み立てる。

        PR表記はURL直貼りの有無ではなく、商品紹介やLP誘導があるかで必要になる。
        """
        if post_type == "affiliate":
            parts = ["【PR】" + hook, body, cta]
            if context["affiliate_url"] and not self._is_a8_url(context["affiliate_url"]):
                parts.append(context["affiliate_url"])
            return "\n".join(part.strip() for part in parts if part).strip()
        if post_type == "two_line_copy":
            return f"{hook}\n{body}\n{cta}".strip()
        return f"{hook}\n\n{body}\n\n{cta}".strip()

    def _unique_hook(self, hook: str, context: Dict[str, Any], used_hooks: Set[str]) -> str:
        """同一hookの使い回しを避ける。

        Threadsでは冒頭が同じ投稿は機械的に見えやすく、読者体験とアカウント安全性の両面で弱い。
        """
        if hook not in used_hooks:
            return hook
        variants = [
            f"{context['category']}のしんどさ、削るならここからだった。",
            f"{context['primary_pain']}。ここを道具で減らす発想、もっと早く欲しかった。",
            f"{context['title']}、買う理由を時間で見ると急に冷静になれる。",
        ]
        for variant in variants:
            if variant not in used_hooks:
                return variant
        return f"{hook} ({len(used_hooks) + 1})"

    def _existing_hooks(self) -> Set[str]:
        hooks: Set[str] = set()
        for status in ("draft", "approved", "queued", "dry_run_posted", "posted", "rejected"):
            hooks.update(str(post.get("hook", "")) for post in self.db.get_documents_by_status("post_candidates", status))
        return {hook for hook in hooks if hook}

    @staticmethod
    def _strip_internal_decisions(text: str) -> str:
        """buy/consider/skipなど内部判定値を外向きの投稿から除去する。"""
        replacements = {
            "判定はbuyです。": "",
            "判定はconsiderです。": "",
            "判定はskipです。": "",
            "判定はbuyです": "",
            "判定はconsiderです": "",
            "判定はskipです": "",
            "decision: buy": "",
            "decision: consider": "",
            "decision: skip": "",
        }
        cleaned = text
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        return cleaned.strip()

    @staticmethod
    def _is_a8_url(url: str) -> bool:
        return "a8.net" in url or "px.a8.net" in url

    @staticmethod
    def _render_prompt(template: str, context: Dict[str, Any]) -> str:
        rendered = template
        for key, value in context.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        return rendered
