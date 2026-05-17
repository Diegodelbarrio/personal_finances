import datetime
import math
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

from core.services.net_worth import calculate_net_worth
from finances.services import queries as finance_queries
from finances.models import Category
from settings.models import SavingsPotentialModel, UserSettings

class SettingsService:
    PROFILE_CONFIG = {
        "BALANCED": {
            "label": "Balanced",
            "weights": {
                "savings_rate": 0.25,
                "emergency": 0.25,
                "budget": 0.25,
                "net_worth": 0.25,
            },
            "budget_margin": 0.08,
            "base_emergency_months": 6,
            "min_emergency_months": 3,
            "max_emergency_months": 12,
            "minimum_savings_rate": 0.12,
            "savings_target_multiplier": 1.0,
            "simulator_multiplier": 1.0,
            "low_savings_threshold": 10,
        },
        "SECURITY": {
            "label": "Security First",
            "weights": {
                "savings_rate": 0.20,
                "emergency": 0.40,
                "budget": 0.30,
                "net_worth": 0.10,
            },
            "budget_margin": 0.05,
            "base_emergency_months": 9,
            "min_emergency_months": 6,
            "max_emergency_months": 12,
            "minimum_savings_rate": 0.08,
            "savings_target_multiplier": 0.95,
            "simulator_multiplier": 0.95,
            "low_savings_threshold": 12,
        },
        "GROWTH": {
            "label": "Growth Focus",
            "weights": {
                "savings_rate": 0.35,
                "emergency": 0.15,
                "budget": 0.15,
                "net_worth": 0.35,
            },
            "budget_margin": 0.12,
            "base_emergency_months": 3,
            "min_emergency_months": 3,
            "max_emergency_months": 9,
            "minimum_savings_rate": 0.18,
            "savings_target_multiplier": 1.15,
            "simulator_multiplier": 1.15,
            "low_savings_threshold": 8,
        },
    }
    PROFILE_SCENARIO_MAP = {
        "SECURITY": "conservative",
        "BALANCED": "baseline",
        "GROWTH": "optimistic",
    }

    @staticmethod
    def get_settings(user):
        obj, _created = UserSettings.objects.get_or_create(user=user)
        SavingsPotentialModel.objects.get_or_create(user_settings=obj)
        return obj

    @staticmethod
    def calculate_goals_progress(user, current_net_worth=0, current_annual_savings=0):
        settings = SettingsService.get_settings(user)

        current_nw = Decimal(str(current_net_worth))
        current_sav = Decimal(str(current_annual_savings))

        nw_target = settings.net_worth_target
        nw_percent = 0
        if nw_target > 0:
            nw_percent = (current_nw / nw_target) * 100

        sav_target = settings.annual_savings_target
        sav_percent = 0
        if sav_target > 0:
            sav_percent = (current_sav / sav_target) * 100

        days_left = None
        if settings.target_date:
            delta = settings.target_date - datetime.date.today()
            days_left = max(delta.days, 0)

        return {
            "settings": settings,
            "nw_progress": min(round(float(nw_percent), 1), 100),
            "sav_progress": min(round(float(sav_percent), 1), 100),
            "days_left": days_left,
            "is_date_passed": days_left == 0,
        }

    @staticmethod
    def get_phase3_insights(user):
        user_settings = SettingsService.get_settings(user)
        today = datetime.date.today()
        profile_config = SettingsService._get_profile_config(user_settings.financial_profile)
        window = SettingsService._get_trailing_window_data(user=user, today=today)

        months_count = window["months_count"]
        total_income = window["total_income"]
        total_expenses = window["total_expenses"]
        total_savings = total_income - total_expenses

        avg_monthly_income = (total_income / months_count) if months_count else 0.0
        avg_monthly_expenses = (total_expenses / months_count) if months_count else 0.0
        avg_monthly_savings = (total_savings / months_count) if months_count else 0.0
        actual_savings_rate = (total_savings / total_income * 100) if total_income > 0 else 0.0

        monthly_expenses = [float(item["expenses"]) for item in window["monthly_rows"] if float(item["expenses"]) > 0]
        expense_volatility = SettingsService._expense_volatility(monthly_expenses, avg_monthly_expenses)

        net_worth_data = calculate_net_worth(user)
        cash_total = float(net_worth_data.get("holdings_value", 0.0) or 0.0)
        configured_emergency_months = max(int(user_settings.emergency_fund_months or 0), 1)
        emergency_months_covered = (cash_total / avg_monthly_expenses) if avg_monthly_expenses > 0 else 0.0

        current_net_worth = float(net_worth_data.get("current_net_worth", 0.0) or 0.0)

        score = SettingsService._calculate_financial_score(
            settings=user_settings,
            current_net_worth=current_net_worth,
            actual_savings_rate=actual_savings_rate,
            avg_monthly_expenses=avg_monthly_expenses,
            emergency_months_covered=emergency_months_covered,
            profile_config=profile_config,
        )

        simulator = SettingsService._build_goal_simulator(
            settings=user_settings,
            current_net_worth=current_net_worth,
            avg_monthly_income=avg_monthly_income,
            avg_monthly_expenses=avg_monthly_expenses,
            avg_monthly_savings=avg_monthly_savings,
            actual_savings_rate=actual_savings_rate,
            emergency_months_covered=emergency_months_covered,
            expense_volatility=expense_volatility,
            today=today,
            profile_config=profile_config,
        )

        recommendations = SettingsService._build_smart_recommendations(
            settings=user_settings,
            avg_monthly_expenses=avg_monthly_expenses,
            avg_monthly_savings=avg_monthly_savings,
            actual_savings_rate=actual_savings_rate,
            expense_volatility=expense_volatility,
            profile_config=profile_config,
        )

        return {
            "score": score,
            "simulator": simulator,
            "recommendations": recommendations,
            "profile": {
                "code": user_settings.financial_profile,
                "label": profile_config["label"],
            },
            "snapshot": {
                "months_sampled": months_count,
                "window_start": window["window_start"],
                "window_end": window["window_end"],
                "window_total_savings": round(total_savings, 2),
                "avg_monthly_income": round(avg_monthly_income, 2),
                "avg_monthly_expenses": round(avg_monthly_expenses, 2),
                "avg_monthly_savings": round(avg_monthly_savings, 2),
                "actual_savings_rate": round(actual_savings_rate, 1),
                "cash_total": round(float(cash_total), 2),
                "emergency_months_covered": round(emergency_months_covered, 1),
                "configured_emergency_months": configured_emergency_months,
            },
            "market_status": {
                "last_market_date": net_worth_data.get("last_market_date"),
                "data_status": net_worth_data.get("data_status", "ok"),
            },
        }

    @staticmethod
    def _expense_volatility(monthly_expenses, avg_monthly_expenses):
        if not monthly_expenses or avg_monthly_expenses <= 0:
            return 0.0
        variance = sum((value - avg_monthly_expenses) ** 2 for value in monthly_expenses) / len(monthly_expenses)
        std_dev = math.sqrt(variance)
        return std_dev / avg_monthly_expenses

    @staticmethod
    def _build_goal_simulator(
        settings,
        current_net_worth,
        avg_monthly_income,
        avg_monthly_expenses,
        avg_monthly_savings,
        actual_savings_rate,
        emergency_months_covered,
        expense_volatility,
        today,
        profile_config=None,
    ):
        if profile_config is None:
            profile_config = SettingsService._get_profile_config(settings.financial_profile)

        savings_model = SettingsService._get_savings_model(settings)
        target_net_worth = float(settings.net_worth_target or 0.0)
        remaining_gap = max(target_net_worth - current_net_worth, 0.0)
        target_date = settings.target_date
        scenarios = SettingsService._build_potential_scenarios(
            settings=settings,
            savings_model=savings_model,
            avg_monthly_income=avg_monthly_income,
            avg_monthly_expenses=avg_monthly_expenses,
            avg_monthly_savings=avg_monthly_savings,
            actual_savings_rate=actual_savings_rate,
            emergency_months_covered=emergency_months_covered,
            expense_volatility=expense_volatility,
            remaining_gap=remaining_gap,
            target_date=target_date,
            today=today,
            profile_config=profile_config,
        )

        selected_scenario_key = SettingsService._resolve_default_scenario_key(settings.financial_profile)
        selected_scenario = next(
            (item for item in scenarios if item["key"] == selected_scenario_key),
            scenarios[1] if len(scenarios) > 1 else scenarios[0],
        )

        return {
            "current_net_worth": round(current_net_worth, 2),
            "target_net_worth": round(target_net_worth, 2),
            "remaining_gap": round(remaining_gap, 2),
            "suggested_monthly_contribution": selected_scenario["monthly_contribution"],
            "months_to_goal": selected_scenario["months_to_goal"],
            "projected_date": selected_scenario["projected_date"],
            "projected_days": selected_scenario["projected_days"],
            "target_date": target_date,
            "on_track": selected_scenario["on_track"],
            "is_target_reached": remaining_gap == 0,
            "scenarios": scenarios,
            "selected_scenario_key": selected_scenario["key"],
            "selected_scenario_label": selected_scenario["label"],
            "status_label": selected_scenario["status_label"],
            "status_tone": selected_scenario["status_tone"],
        }

    @staticmethod
    def _get_savings_model(settings):
        savings_model, _created = SavingsPotentialModel.objects.get_or_create(
            user_settings=settings,
        )
        return savings_model

    @staticmethod
    def _resolve_default_scenario_key(profile_code):
        return SettingsService.PROFILE_SCENARIO_MAP.get(profile_code, "baseline")

    @staticmethod
    def _build_potential_scenarios(
        settings,
        savings_model,
        avg_monthly_income,
        avg_monthly_expenses,
        avg_monthly_savings,
        actual_savings_rate,
        emergency_months_covered,
        expense_volatility,
        remaining_gap,
        target_date,
        today,
        profile_config,
    ):
        annual_target = float(settings.annual_savings_target or 0.0)
        monthly_from_target = (annual_target / 12.0) if annual_target > 0 else 0.0

        savings_rate_target = float(settings.savings_rate_target or 0.0)
        configured_rate = (savings_rate_target / 100.0) if savings_rate_target > 0 else 0.0
        minimum_rate = profile_config["minimum_savings_rate"]
        target_rate = max(configured_rate, minimum_rate)
        monthly_from_rate = max(avg_monthly_income, 0.0) * target_rate

        fallback_from_expenses = max(avg_monthly_expenses, 0.0) * minimum_rate
        base_monthly_capacity = max(
            max(avg_monthly_savings, 0.0),
            monthly_from_target,
            monthly_from_rate,
            fallback_from_expenses,
        )

        volatility_factor = 1.0 - min(max(expense_volatility, 0.0), 1.0) * float(savings_model.volatility_impact)
        volatility_factor = min(max(volatility_factor, 0.55), 1.0)

        configured_emergency_months = max(int(settings.emergency_fund_months or 0), 1)
        emergency_coverage_ratio = (
            emergency_months_covered / configured_emergency_months
            if configured_emergency_months > 0
            else 1.0
        )
        emergency_shortfall = max(0.0, 1.0 - min(emergency_coverage_ratio, 1.0))
        emergency_factor = 1.0 - (emergency_shortfall * float(savings_model.emergency_buffer_impact))
        emergency_factor = min(max(emergency_factor, 0.60), 1.0)

        if actual_savings_rate <= 0 and avg_monthly_savings <= 0:
            discipline_factor = 0.85
        elif actual_savings_rate < (minimum_rate * 100):
            discipline_factor = 0.92
        else:
            discipline_factor = 1.0

        profile_factor = profile_config["simulator_multiplier"]
        base_projection = base_monthly_capacity * volatility_factor * emergency_factor * discipline_factor * profile_factor
        base_projection = max(base_projection, 0.0)

        scenario_definitions = [
            {
                "key": "conservative",
                "label": "Conservative",
                "factor": float(savings_model.conservative_factor),
                "insight": "Preserves more cash buffer in unstable months.",
            },
            {
                "key": "baseline",
                "label": "Baseline",
                "factor": float(savings_model.baseline_factor),
                "insight": "Based on your current savings pace and targets.",
            },
            {
                "key": "optimistic",
                "label": "Optimistic",
                "factor": float(savings_model.optimistic_factor),
                "insight": "Assumes disciplined spending and stable income.",
            },
        ]

        scenarios = []
        for definition in scenario_definitions:
            monthly_contribution = round(max(base_projection * definition["factor"], 0.0), 2)
            projection = SettingsService._project_goal_timeline(
                remaining_gap=remaining_gap,
                monthly_contribution=monthly_contribution,
                target_date=target_date,
                today=today,
            )
            scenarios.append(
                {
                    "key": definition["key"],
                    "label": definition["label"],
                    "monthly_contribution": monthly_contribution,
                    "insight": definition["insight"],
                    **projection,
                }
            )

        return scenarios

    @staticmethod
    def _project_goal_timeline(remaining_gap, monthly_contribution, target_date, today):
        months_to_goal = None
        projected_date = None
        projected_days = None

        if remaining_gap == 0:
            months_to_goal = 0
            projected_date = today
            projected_days = 0
        elif monthly_contribution > 0:
            months_to_goal = math.ceil(remaining_gap / monthly_contribution)
            projected_date = SettingsService._add_months(today, months_to_goal)
            projected_days = (projected_date - today).days

        on_track = bool(projected_date and target_date and projected_date <= target_date)
        status_label, status_tone = SettingsService._get_timeline_status(
            remaining_gap=remaining_gap,
            monthly_contribution=monthly_contribution,
            projected_date=projected_date,
            target_date=target_date,
        )

        return {
            "months_to_goal": months_to_goal,
            "projected_date": projected_date,
            "projected_days": projected_days,
            "on_track": on_track,
            "status_label": status_label,
            "status_tone": status_tone,
        }

    @staticmethod
    def _get_timeline_status(remaining_gap, monthly_contribution, projected_date, target_date):
        if remaining_gap == 0:
            return "Target reached", "success"
        if monthly_contribution <= 0:
            return "No savings capacity", "danger"
        if not target_date:
            return "No target date", "muted"
        if projected_date and projected_date <= target_date:
            return "On track", "success"
        return "Behind schedule", "warning"

    @staticmethod
    def _calculate_financial_score(
        settings,
        current_net_worth,
        actual_savings_rate,
        avg_monthly_expenses,
        emergency_months_covered,
        profile_config,
    ):
        weights = profile_config["weights"]
        savings_target = float(settings.savings_rate_target or 0.0)
        if savings_target > 0:
            savings_rate_score = min(max(actual_savings_rate / savings_target * 100, 0), 100)
        else:
            savings_rate_score = min(max(actual_savings_rate / 20.0 * 100, 0), 100)

        emergency_target = max(int(settings.emergency_fund_months or 0), 1)
        emergency_score = min(max(emergency_months_covered / emergency_target * 100, 0), 100)

        configured_budget = float(settings.monthly_budget or 0.0)
        if configured_budget <= 0:
            budget_score = 50 if avg_monthly_expenses > 0 else 100
        elif avg_monthly_expenses <= configured_budget:
            budget_score = 100
        else:
            overshoot_ratio = (avg_monthly_expenses - configured_budget) / configured_budget
            budget_score = max(0, 100 - (overshoot_ratio * 100))

        net_worth_target = float(settings.net_worth_target or 0.0)
        if net_worth_target > 0:
            net_worth_score = min(max(current_net_worth / net_worth_target * 100, 0), 100)
        else:
            net_worth_score = 50

        total_score = round(
            (savings_rate_score * weights["savings_rate"]) +
            (emergency_score * weights["emergency"]) +
            (budget_score * weights["budget"]) +
            (net_worth_score * weights["net_worth"])
        )

        if total_score >= 85:
            status = "excellent"
            label = "Excellent"
            tone = "success"
        elif total_score >= 70:
            status = "strong"
            label = "Strong"
            tone = "primary"
        elif total_score >= 55:
            status = "moderate"
            label = "Moderate"
            tone = "warning"
        else:
            status = "high_risk"
            label = "High Risk"
            tone = "danger"

        components = [
            {
                "label": "Savings Rate",
                "score": round(savings_rate_score),
                "weight": round(weights["savings_rate"] * 100),
                "tone": SettingsService._score_tone(savings_rate_score),
            },
            {
                "label": "Emergency Buffer",
                "score": round(emergency_score),
                "weight": round(weights["emergency"] * 100),
                "tone": SettingsService._score_tone(emergency_score),
            },
            {
                "label": "Budget Discipline",
                "score": round(budget_score),
                "weight": round(weights["budget"] * 100),
                "tone": SettingsService._score_tone(budget_score),
            },
            {
                "label": "Net Worth Progress",
                "score": round(net_worth_score),
                "weight": round(weights["net_worth"] * 100),
                "tone": SettingsService._score_tone(net_worth_score),
            },
        ]

        return {
            "value": total_score,
            "status": status,
            "label": label,
            "tone": tone,
            "profile": profile_config["label"],
            "components": components,
        }

    @staticmethod
    def _score_tone(value):
        if value >= 80:
            return "success"
        if value >= 55:
            return "warning"
        return "danger"

    @staticmethod
    def _build_smart_recommendations(
        settings,
        avg_monthly_expenses,
        avg_monthly_savings,
        actual_savings_rate,
        expense_volatility,
        profile_config,
    ):
        recommended_monthly_budget = round(
            avg_monthly_expenses * (1 + profile_config["budget_margin"]),
            2,
        ) if avg_monthly_expenses > 0 else 0.0
        configured_budget = float(settings.monthly_budget or 0.0)
        budget_delta = round(recommended_monthly_budget - configured_budget, 2)

        fallback_monthly_savings = avg_monthly_expenses * profile_config["minimum_savings_rate"] if avg_monthly_expenses > 0 else 0.0
        base_monthly_savings = max(avg_monthly_savings, fallback_monthly_savings)
        recommended_annual_savings = round(
            base_monthly_savings * 12 * profile_config["savings_target_multiplier"],
            2,
        )

        volatility_months = 0
        if expense_volatility >= 0.45:
            volatility_months = 3
        elif expense_volatility >= 0.25:
            volatility_months = 2
        elif expense_volatility >= 0.12:
            volatility_months = 1

        savings_penalty = 1 if actual_savings_rate < profile_config["low_savings_threshold"] else 0
        recommended_emergency_months = (
            profile_config["base_emergency_months"] + volatility_months + savings_penalty
        )
        recommended_emergency_months = min(
            max(recommended_emergency_months, profile_config["min_emergency_months"]),
            profile_config["max_emergency_months"],
        )

        return [
            {
                "key": "monthly_budget",
                "label": "Monthly Budget",
                "suggested_value": recommended_monthly_budget,
                "current_value": configured_budget,
                "delta": budget_delta,
                "is_aligned": abs(budget_delta) <= max(recommended_monthly_budget * 0.05, 50),
                "insight": f"Based on the last 12 months and your {profile_config['label']} profile.",
            },
            {
                "key": "annual_savings_target",
                "label": "Annual Savings Target",
                "suggested_value": recommended_annual_savings,
                "current_value": float(settings.annual_savings_target or 0.0),
                "delta": round(recommended_annual_savings - float(settings.annual_savings_target or 0.0), 2),
                "is_aligned": abs(recommended_annual_savings - float(settings.annual_savings_target or 0.0)) <= max(recommended_annual_savings * 0.1, 250),
                "insight": f"Projected from your monthly pace, adjusted for {profile_config['label']}.",
            },
            {
                "key": "emergency_fund_months",
                "label": "Emergency Fund (Months)",
                "suggested_value": recommended_emergency_months,
                "current_value": int(settings.emergency_fund_months or 0),
                "delta": int(recommended_emergency_months - int(settings.emergency_fund_months or 0)),
                "is_aligned": int(settings.emergency_fund_months or 0) == recommended_emergency_months,
                "insight": f"Calibrated by profile plus spending volatility of your trailing window.",
            },
        ]

    @staticmethod
    def _get_profile_config(profile_code):
        return SettingsService.PROFILE_CONFIG.get(profile_code, SettingsService.PROFILE_CONFIG["BALANCED"])

    @staticmethod
    def _get_trailing_window_data(user, today):
        base_qs = finance_queries.get_base_transaction_qs(user).filter(date__lte=today)
        first_transaction = base_qs.order_by("date").first()
        nominal_start = SettingsService._subtract_one_year(today)

        if first_transaction:
            window_start = max(nominal_start, first_transaction.date)
            window_qs = base_qs.filter(date__gte=window_start)
            monthly_rows = SettingsService._collect_monthly_rows(
                window_qs=window_qs,
                window_start=window_start,
                window_end=today,
            )
        else:
            window_start = nominal_start
            monthly_rows = []

        total_income = float(sum(item["income"] for item in monthly_rows))
        total_expenses = float(sum(item["expenses"] for item in monthly_rows))

        return {
            "window_start": window_start,
            "window_end": today,
            "months_count": len(monthly_rows),
            "monthly_rows": monthly_rows,
            "total_income": total_income,
            "total_expenses": total_expenses,
        }

    @staticmethod
    def _collect_monthly_rows(window_qs, window_start, window_end):
        monthly_totals = (
            window_qs
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(
                income=Sum(
                    "amount",
                    filter=Q(
                        subcategory__parent_category__transaction_type=Category.TransactionType.INCOME
                    ),
                ),
                expenses=Sum(
                    "amount",
                    filter=Q(
                        subcategory__parent_category__transaction_type=Category.TransactionType.EXPENSE
                    ),
                ),
            )
        )
        totals_by_month = {}
        for item in monthly_totals:
            month_value = item["month"]
            month_start = month_value.date() if hasattr(month_value, "date") else month_value
            income = abs(item["income"] or 0)
            expenses = abs(item["expenses"] or 0)
            totals_by_month[month_start] = {
                "income": float(income),
                "expenses": float(expenses),
                "savings": float(income - expenses),
            }

        rows = []
        cursor = window_start.replace(day=1)
        end_cursor = window_end.replace(day=1)

        while cursor <= end_cursor:
            stats = totals_by_month.get(
                cursor,
                {
                    "income": 0.0,
                    "expenses": 0.0,
                    "savings": 0.0,
                },
            )
            rows.append(
                {
                    "month_start": cursor,
                    "income": stats["income"],
                    "expenses": stats["expenses"],
                    "savings": stats["savings"],
                }
            )
            cursor = SettingsService._add_months(cursor, 1)

        return rows

    @staticmethod
    def _subtract_one_year(source_date):
        return datetime.date(source_date.year - 1, source_date.month, 1)

    @staticmethod
    def _add_months(source_date, months):
        month_idx = source_date.month - 1 + months
        year = source_date.year + month_idx // 12
        month = month_idx % 12 + 1
        last_day = SettingsService._last_day_of_month(year, month)
        day = min(source_date.day, last_day)
        return datetime.date(year, month, day)

    @staticmethod
    def _last_day_of_month(year, month):
        if month == 12:
            next_month = datetime.date(year + 1, 1, 1)
        else:
            next_month = datetime.date(year, month + 1, 1)
        return (next_month - datetime.timedelta(days=1)).day
