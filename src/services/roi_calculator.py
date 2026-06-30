from typing import Any, Dict, Optional

from src import config


def calculate_roi(
    *,
    product_price: float,
    time_saving_minutes_per_week: float,
    hourly_value: int = config.DEFAULT_HOURLY_VALUE,
) -> Dict[str, Any]:
    """商品価格と週あたり削減分数からROI指標を計算する純粋関数。

    - monthly_time_saving_hours: 週次削減分数を4週間分として月間時間へ換算
    - hourly_value: 1時間の価値。環境変数DEFAULT_HOURLY_VALUEで調整する
    - monthly/yearly_value: 時間削減を金額換算した説明用指標
    - payback_period_months: 価格を月間価値で割った回収月数

    buy/consider/skipは内部判定であり、投稿本文やLPの表示文言として
    そのまま出さない。外向きにはroi_commentの自然文を使う。
    """
    monthly_time_saving_hours = round((time_saving_minutes_per_week * 4) / 60, 2)
    monthly_value = round(monthly_time_saving_hours * hourly_value)
    yearly_value = monthly_value * 12
    payback_period_months: Optional[float] = None
    if monthly_value > 0:
        payback_period_months = round(product_price / monthly_value, 2)

    roi_score = _roi_score(payback_period_months, yearly_value, product_price)
    if payback_period_months is not None and payback_period_months <= 3:
        decision = "buy"
    elif payback_period_months is not None and payback_period_months <= 12:
        decision = "consider"
    else:
        decision = "skip"

    return {
        "product_price": product_price,
        "monthly_time_saving_hours": monthly_time_saving_hours,
        "hourly_value": hourly_value,
        "monthly_value": monthly_value,
        "yearly_value": yearly_value,
        "payback_period_months": payback_period_months,
        "roi_score": roi_score,
        "decision": decision,
        "roi_comment": describe_roi(payback_period_months, monthly_time_saving_hours),
    }


def describe_roi(payback_period_months: Optional[float], monthly_hours: float) -> str:
    """内部判定値を露出させず、投稿で使える自然なROI説明へ変換する。"""
    if payback_period_months is None:
        return "時間削減がほぼ見込めないなら、今は見送ってよさそう。"
    if payback_period_months <= 1.5:
        return f"月に約{monthly_hours:g}時間戻る計算。1か月ちょっとで元が取れるならかなり現実的。"
    if payback_period_months <= 3:
        return f"月に約{monthly_hours:g}時間戻る計算。数か月で回収できるなら、家事の外注に近い投資感です。"
    if payback_period_months <= 12:
        return f"月に約{monthly_hours:g}時間戻る計算。すぐ元が取れるとは言わないけど、長く使うなら検討余地あり。"
    return f"月に約{monthly_hours:g}時間戻る計算。ただ、回収には時間がかかるので優先度は低め。"


def _roi_score(payback_period_months: Optional[float], yearly_value: float, product_price: float) -> float:
    """回収の早さを主軸に、年間価値も少し加味した0〜10点の内部スコア。"""
    if payback_period_months is None or product_price <= 0:
        return 0.0
    payback_component = max(0.0, 10.0 - (payback_period_months / 12.0) * 10.0)
    value_component = min(10.0, (yearly_value / product_price) * 2.0)
    return round((payback_component * 0.7) + (value_component * 0.3), 2)


class ROICalculator:
    @staticmethod
    def calculate(price: float, time_saving_minutes_per_week: float) -> Dict[str, Any]:
        return calculate_roi(
            product_price=price,
            time_saving_minutes_per_week=time_saving_minutes_per_week,
            hourly_value=config.DEFAULT_HOURLY_VALUE,
        )
