import pytest
from src.services.compliance import ComplianceService

def test_pr_tag_inserted_when_has_link():
    text = "これは良い商品です。\nhttp://example.com"
    formatted, is_rejected = ComplianceService.check_and_format_post(text, True)
    assert not is_rejected
    assert formatted.startswith("【PR】")

def test_pr_tag_not_inserted_when_no_link():
    text = "今日は疲れました。"
    formatted, is_rejected = ComplianceService.check_and_format_post(text, False)
    assert not is_rejected
    assert not formatted.startswith("【PR】")

def test_trailing_pr_tag_replaced():
    text = "これは良い商品です。\nhttp://example.com\n#PR"
    formatted, is_rejected = ComplianceService.check_and_format_post(text, True)
    assert not is_rejected
    assert formatted.startswith("【PR】")
    assert not formatted.endswith("#PR")

def test_ng_words_replaced():
    text = "これでシミが消えるよ！"
    formatted, is_rejected = ComplianceService.check_and_format_post(text, False)
    assert not is_rejected
    assert "シミが消える" not in formatted
    assert "シミの悩みをケアする" in formatted

def test_length_limit():
    text = "あ" * 501
    _, is_rejected = ComplianceService.check_and_format_post(text, False)
    assert is_rejected

def test_a8_link_rejected():
    text = "詳細はこちら: http://px.a8.net/something"
    _, is_rejected = ComplianceService.check_and_format_post(text, True)
    assert is_rejected

def test_multiple_links_rejected():
    text = "リンク1: http://example.com リンク2: https://example.org"
    _, is_rejected = ComplianceService.check_and_format_post(text, True)
    assert is_rejected