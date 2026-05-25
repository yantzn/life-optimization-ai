import pytest
from src.services.roi_calculator import ROICalculator

def test_calculate_buy():
    res = ROICalculator.calculate(10000, 30)
    assert res["payback_period_months"] == 2.5
    assert res["decision"] == "buy"

def test_calculate_consider():
    res = ROICalculator.calculate(40000, 30)
    assert res["payback_period_months"] == 10.0
    assert res["decision"] == "consider"

def test_calculate_skip():
    res = ROICalculator.calculate(80000, 30)
    assert res["payback_period_months"] == 20.0
    assert res["decision"] == "skip"

def test_calculate_zero_time_saving():
    res = ROICalculator.calculate(10000, 0)
    assert res["payback_period_months"] is None
    assert res["decision"] == "skip"