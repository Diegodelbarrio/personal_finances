from decimal import Decimal # Asegúrate de tener esta importación
from settings.models import UserSettings
import datetime

class SettingsService:
    @staticmethod
    def get_settings(user):
        obj, created = UserSettings.objects.get_or_create(user=user)
        return obj

    @staticmethod
    def calculate_goals_progress(user, current_net_worth=0, current_annual_savings=0):
        settings = SettingsService.get_settings(user)
        
        # Convertimos los inputs a Decimal para evitar el error de tipos
        current_nw = Decimal(str(current_net_worth))
        current_sav = Decimal(str(current_annual_savings))
        
        # 1. Progreso Patrimonio
        nw_target = settings.net_worth_target # Esto ya es Decimal por el modelo
        nw_percent = 0
        if nw_target > 0:
            # Ahora ambos son Decimal y la operación funciona
            nw_percent = (current_nw / nw_target) * 100

        # 2. Progreso Ahorro
        sav_target = settings.annual_savings_target # Esto ya es Decimal
        sav_percent = 0
        if sav_target > 0:
            sav_percent = (current_sav / sav_target) * 100

        # 3. Días restantes
        days_left = None
        if settings.target_date:
            delta = settings.target_date - datetime.date.today()
            days_left = max(delta.days, 0)

        return {
            'settings': settings,
            'nw_progress': min(round(float(nw_percent), 1), 100), 
            'sav_progress': min(round(float(sav_percent), 1), 100),
            'days_left': days_left,
            'is_date_passed': days_left == 0
        }