from typing import Dict, Any, Optional
from src import config

class ROICalculator:
    @staticmethod
    def calculate(price: float, time_saving_minutes_per_week: float) -> Dict[str, Any]:
        monthly_time_saving_hours = time_saving_minutes_per_week * 4 / 60
        monthly_value = monthly_time_saving_hours * config.DEFAULT_HOURLY_VALUE
        yearly_value = monthly_value * 12
        
        payback_period_months = price / monthly_value if monthly_value > 0 else None
        
        decision = "skip"
        if payback_period_months is not None:
            if payback_period_months <= 3:
                decision = "buy"
            elif payback_period_months <= 12:
                decision = "consider"
                
        return {
            "monthly_time_saving_hours": monthly_time_saving_hours,
            "monthly_value": monthly_value,
            "yearly_value": yearly_value,
            "payback_period_months": payback_period_months,
            "decision": decision
        }