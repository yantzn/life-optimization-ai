from src.services.roi_calculator import calculate_roi


def test_calculate_roi_buy():
    result = calculate_roi(product_price=10000, time_saving_minutes_per_week=120, hourly_value=2000)

    assert result["monthly_time_saving_hours"] == 8.0
    assert result["monthly_value"] == 16000
    assert result["yearly_value"] == 192000
    assert result["payback_period_months"] == 0.62
    assert result["decision"] == "buy"
    assert result["roi_score"] > 8


def test_calculate_roi_consider():
    result = calculate_roi(product_price=40000, time_saving_minutes_per_week=60, hourly_value=2000)

    assert result["payback_period_months"] == 5.0
    assert result["decision"] == "consider"


def test_calculate_roi_skip_when_no_time_saving():
    result = calculate_roi(product_price=10000, time_saving_minutes_per_week=0, hourly_value=2000)

    assert result["payback_period_months"] is None
    assert result["roi_score"] == 0.0
    assert result["decision"] == "skip"
