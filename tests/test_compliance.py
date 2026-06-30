from src.services.compliance import ComplianceService


def test_pr_tag_can_be_inserted_at_front_when_formatting():
    formatted, rejected = ComplianceService.check_and_format_post("本文です\nhttps://example.com/lp", True)

    assert not rejected
    assert formatted.startswith("【PR】")


def test_missing_front_pr_rejected_in_quality_check():
    result = ComplianceService.check_post("本文です\nhttps://example.com/lp", has_affiliate_or_lp=True)

    assert result.status == "rejected"
    assert result.rejection_reason == "missing_front_pr"


def test_internal_decision_value_is_deducted():
    result = ComplianceService.check_post("【PR】判定はbuyです。これは便利です https://example.com", has_affiliate_or_lp=True)

    assert result.quality_score <= 70
    assert "内部判定値" in result.warnings[0]


def test_duplicate_hook_is_deducted():
    result = ComplianceService.check_post(
        "【PR】夕飯後の片付けを少し軽くする話です https://example.com",
        has_affiliate_or_lp=True,
        hook="同じhook",
        existing_hooks={"同じhook"},
    )

    assert result.quality_score <= 85
    assert result.status == "queued"


def test_rejects_over_500_chars():
    result = ComplianceService.check_post("あ" * 501)

    assert result.status == "rejected"
    assert result.rejection_reason == "text_length_exceeds_500"


def test_rejects_a8_direct_link():
    result = ComplianceService.check_post("【PR】https://px.a8.net/example", has_affiliate_or_lp=True)

    assert result.status == "rejected"
    assert result.rejection_reason == "a8_direct_link_forbidden"


def test_detects_regulated_expression():
    result = ComplianceService.check_post("このサプリで免疫力アップします")

    assert result.status == "rejected"
    assert result.rejection_reason == "regulated_expression_detected"


def test_limits_affiliate_url_to_one():
    result = ComplianceService.check_post(
        "【PR】リンク1 https://example.com/a リンク2 https://example.com/b",
        has_affiliate_or_lp=True,
    )

    assert result.status == "rejected"
    assert result.rejection_reason == "too_many_urls"


def test_affiliate_smell_expression_is_deducted():
    result = ComplianceService.check_post("【PR】大人気でおすすめです https://example.com", has_affiliate_or_lp=True)

    assert result.status == "rejected"
    assert result.quality_score <= 60
    assert result.warnings
