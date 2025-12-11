from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.conf import settings
import datetime
from zoneinfo import ZoneInfo
from .models import Booking, WorkingHour


# ІНТЕГРАЦІЯ З GOOGLE CALENDAR

def get_google_calendar_service(user):
    """
    Отримання сервісу Google Calendar для користувача
    Повертає None, якщо Google OAuth не підключено
    """
    if not hasattr(user, 'social_auth'):
        return None

    try:
        social_auth = user.social_auth.get(provider='google-oauth2')
    except:
        return None

    access_token = social_auth.extra_data.get('access_token')
    refresh_token = social_auth.extra_data.get('refresh_token')

    # Створення credentials для Google API
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        client_secret=settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
    )

    return build('calendar', 'v3', credentials=creds)


def get_busy_periods(user, date_str):
    """
    Отримання зайнятих періодів з Google Calendar користувача
    Повертає список dict з ключами 'start' та 'end' (ISO format)
    """
    service = get_google_calendar_service(user)
    if not service:
        return []

    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    kyiv_tz = ZoneInfo('Europe/Kyiv')

    # Визначаємо початок і кінець дня у київському часі
    local_start = datetime.datetime.combine(date_obj, datetime.time.min, tzinfo=kyiv_tz)
    local_end = datetime.datetime.combine(date_obj, datetime.time.max, tzinfo=kyiv_tz)

    # Конвертуємо у UTC для Google API
    time_min = local_start.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    time_max = local_end.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

    # Запит до Google Calendar FreeBusy API
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": "primary"}]
    }

    try:
        events_result = service.freebusy().query(body=body).execute()
        return events_result['calendars']['primary']['busy']
    except Exception as e:
        print(f"Google API Error: {e}")
        return []


def create_google_event(user, start_dt, duration_minutes, summary, description=None):
    """
    Створення події в Google Calendar користувача
    Повертає event_id або None у разі помилки
    """
    service = get_google_calendar_service(user)
    if not service:
        return None

    end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

    event_body = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Europe/Kyiv'
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'Europe/Kyiv'
        },
    }

    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return event['id']
    except Exception as e:
        print(f"Error creating event: {e}")
        return None


# РОЗРАХУНОК ДОСТУПНИХ СЛОТІВ

def is_time_busy(slot_start, slot_end, busy_intervals):
    """
    Перевірка, чи перетинається слот з зайнятими інтервалами
    Повертає True, якщо слот зайнятий
    """
    for busy in busy_intervals:
        busy_start = busy['start']
        busy_end = busy['end']

        # Перевірка перетину інтервалів
        if slot_start < busy_end and slot_end > busy_start:
            return True

    return False


def get_available_slots(user, date_obj, duration_minutes):
    """
    Отримання списку доступних часових слотів для бронювання

    Алгоритм:
    1. Отримуємо робочий графік ментора на цей день
    2. Отримуємо зайняті періоди з Google Calendar
    3. Отримуємо локальні бронювання з БД
    4. Генеруємо слоти з інтервалом (duration + 15 хв перерва)
    5. Фільтруємо зайняті слоти

    Returns:
        list: Список доступних слотів у форматі 'HH:MM'
    """
    # ===== КРОК 1: ОТРИМАННЯ РОБОЧОГО ГРАФІКУ =====
    day_num = date_obj.weekday()
    working_hour = WorkingHour.objects.filter(
        mentor__user=user,
        day_of_week=day_num
    ).first()

    # Якщо ментор не працює в цей день
    if not working_hour:
        return []

    work_start = datetime.datetime.combine(date_obj, working_hour.start_time)
    work_end = datetime.datetime.combine(date_obj, working_hour.end_time)

    # ===== КРОК 2: ЗБІР ЗАЙНЯТИХ ІНТЕРВАЛІВ =====
    all_busy_intervals = []
    kyiv_tz = ZoneInfo('Europe/Kyiv')

    # 2.1 Зайняті періоди з Google Calendar
    google_busy = get_busy_periods(user, date_obj.strftime('%Y-%m-%d'))

    for item in google_busy:
        # Конвертуємо UTC -> Київський час
        s_utc = datetime.datetime.fromisoformat(item['start'].replace('Z', '+00:00'))
        e_utc = datetime.datetime.fromisoformat(item['end'].replace('Z', '+00:00'))

        s_local_aware = s_utc.astimezone(kyiv_tz)
        e_local_aware = e_utc.astimezone(kyiv_tz)

        # Видаляємо timezone info для порівняння
        s_local = s_local_aware.replace(tzinfo=None)
        e_local = e_local_aware.replace(tzinfo=None)

        all_busy_intervals.append({'start': s_local, 'end': e_local})

    # 2.2 Локальні бронювання з БД
    local_bookings = Booking.objects.filter(
        mentor__user=user,
        start_time__date=date_obj,
        status='confirmed'
    )

    for booking in local_bookings:
        all_busy_intervals.append({
            'start': booking.start_time.replace(tzinfo=None),
            'end': booking.end_time.replace(tzinfo=None)
        })

    # ===== КРОК 3: ГЕНЕРАЦІЯ ДОСТУПНИХ СЛОТІВ =====
    available_slots = []
    current_slot = work_start

    # Крок між слотами: тривалість заняття + 15 хв перерва
    step_minutes = duration_minutes + 15

    while current_slot + datetime.timedelta(minutes=duration_minutes) <= work_end:
        slot_end = current_slot + datetime.timedelta(minutes=duration_minutes)

        # Перевіряємо, чи не зайнятий цей слот
        if not is_time_busy(current_slot, slot_end, all_busy_intervals):
            available_slots.append(current_slot.strftime('%H:%M'))

        # Переходимо до наступного слоту
        current_slot += datetime.timedelta(minutes=step_minutes)

    return available_slots