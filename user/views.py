import datetime
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator  # <--- ВАЖЛИВИЙ ІМПОРТ

# Імпорти наших форм та моделей
from .forms import (
    CustomUserCreationForm, UserUpdateForm, ProfileUpdateForm,
    ServiceForm, ReviewForm
)
from .models import Service, Profile, Booking, WorkingHour, Review
from .utils import get_available_slots, create_google_event, get_google_calendar_service


# --- ГОЛОВНА ТА РЕЄСТРАЦІЯ ---

def home(request: HttpRequest) -> HttpResponse:
    return render(request, 'user/home.html')


def register(request: HttpRequest) -> HttpResponse:
    if request.method == 'GET':
        role_param = request.GET.get('role')
        if role_param == 'mentor':
            request.session['registration_role'] = 'mentor'
        elif role_param == 'client':
            request.session['registration_role'] = 'client'

        form = CustomUserCreationForm()
        return render(request, 'registration/register.html', {'form': form})

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # 1. Створюємо юзера.
            # В цей момент СИГНАЛ автоматично створює порожній профіль.
            user = form.save()

            # 2. Беремо роль із сесії
            role = request.session.get('registration_role', 'client')

            # 3. Просто оновлюємо роль у вже існуючому профілі
            # (Ми впевнені, що user.profile існує завдяки signals.py)
            user.profile.role = role
            user.profile.save()

            if 'registration_role' in request.session:
                del request.session['registration_role']

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home')

    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


# --- ОСОБИСТИЙ КАБІНЕТ (З ПАГІНАЦІЄЮ) ---

@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    profile = request.user.profile
    now = timezone.now()

    # --- АВТОМАТИЧНЕ ЗАВЕРШЕННЯ МИНУЛИХ УРОКІВ ---
    # Знаходимо всі заняття, які мають статус 'confirmed' (підтверджено),
    # але час закінчення яких вже минув (end_time < now).
    # Масово змінюємо їх статус на 'completed' (завершено).
    Booking.objects.filter(
        status='confirmed',
        end_time__lt=now
    ).update(status='completed')
    # ---------------------------------------------

    # --- 1. КЛІЄНТ ---
    # Активні (майбутні)
    client_active = Booking.objects.filter(
        client=profile,
        start_time__gte=now,
        status='confirmed' # Додатково фільтруємо, щоб показувати тільки підтверджені
    ).select_related('mentor__user', 'service').order_by('start_time')

    # Історія (минулі)
    client_history_list = Booking.objects.filter(
        client=profile,
        start_time__lt=now
    ).select_related('mentor__user', 'service', 'review').order_by('-start_time').distinct()

    paginator_client = Paginator(client_history_list, 10)
    page_number_client = request.GET.get('client_page')
    client_history = paginator_client.get_page(page_number_client)

    # --- 2. МЕНТОР ---
    mentor_active = []
    mentor_history = []
    is_mentor = profile.role == 'mentor'

    if is_mentor:
        # Активні (майбутні)
        mentor_active = Booking.objects.filter(
            mentor=profile,
            start_time__gte=now,
            status='confirmed'
        ).select_related('client__user', 'service').order_by('start_time')

        # Історія (минулі)
        mentor_history_list = Booking.objects.filter(
            mentor=profile,
            start_time__lt=now
        ).select_related('client__user', 'service', 'review').order_by('-start_time').distinct()

        paginator_mentor = Paginator(mentor_history_list, 10)
        page_number_mentor = request.GET.get('mentor_page')
        mentor_history = paginator_mentor.get_page(page_number_mentor)

    return render(request, 'user/dashboard.html', {
        'client_active': client_active,
        'client_history': client_history,
        'mentor_active': mentor_active,
        'mentor_history': mentor_history,
        'is_mentor': is_mentor
    })


# --- НАЛАШТУВАННЯ ПРОФІЛЮ ---

@login_required
def profile_settings(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Ваш профіль оновлено! 🌟')
            return redirect('profile_settings')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    return render(request, 'user/profile_settings.html', {
        'u_form': u_form,
        'p_form': p_form
    })


# --- УПРАВЛІННЯ ПОСЛУГАМИ ---

@login_required
def my_services(request: HttpRequest) -> HttpResponse:
    if request.user.profile.role != 'mentor':
        return redirect('dashboard')

    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.mentor = request.user.profile
            service.save()
            messages.success(request, 'Послугу успішно додано! 🚀')
            return redirect('my_services')
    else:
        form = ServiceForm()

    services = request.user.profile.services.all().order_by('-is_active', '-id')

    return render(request, 'user/my_services.html', {
        'form': form,
        'services': services
    })


@login_required
def delete_service(request: HttpRequest, service_id: int) -> HttpResponse:
    service = get_object_or_404(Service, id=service_id, mentor=request.user.profile)
    service.delete()
    messages.warning(request, 'Послугу видалено.')
    return redirect('my_services')


# --- ГРАФІК РОБОТИ ---

@login_required
def schedule_settings(request: HttpRequest) -> HttpResponse:
    if request.user.profile.role != 'mentor':
        return redirect('dashboard')

    days_names = ['Понеділок', 'Вівторок', 'Середа', 'Четвер', 'П\'ятниця', 'Субота', 'Неділя']

    if request.method == 'POST':
        for day_num in range(7):
            is_active = request.POST.get(f'day_{day_num}_active')
            start_time = request.POST.get(f'day_{day_num}_start')
            end_time = request.POST.get(f'day_{day_num}_end')

            existing_hour = WorkingHour.objects.filter(mentor=request.user.profile, day_of_week=day_num).first()

            if is_active and start_time and end_time:
                if existing_hour:
                    existing_hour.start_time = start_time
                    existing_hour.end_time = end_time
                    existing_hour.save()
                else:
                    WorkingHour.objects.create(
                        mentor=request.user.profile,
                        day_of_week=day_num,
                        start_time=start_time,
                        end_time=end_time
                    )
            else:
                if existing_hour:
                    existing_hour.delete()

        messages.success(request, 'Графік роботи оновлено! 📅')
        return redirect('schedule_settings')

    schedule_data = []
    for day_num in range(7):
        wh = WorkingHour.objects.filter(mentor=request.user.profile, day_of_week=day_num).first()
        schedule_data.append({
            'num': day_num,
            'name': days_names[day_num],
            'is_active': wh is not None,
            'start': wh.start_time.strftime('%H:%M') if wh else '09:00',
            'end': wh.end_time.strftime('%H:%M') if wh else '18:00',
        })

    return render(request, 'user/schedule_settings.html', {'schedule': schedule_data})


# --- ПУБЛІЧНА СТОРІНКА МЕНТОРА ---

def mentor_profile(request: HttpRequest, slug: str) -> HttpResponse:
    mentor = get_object_or_404(Profile, slug=slug, role='mentor')
    services = mentor.services.filter(is_active=True)

    return render(request, 'user/mentor_profile.html', {
        'mentor': mentor,
        'services': services
    })


# --- БРОНЮВАННЯ ---

@login_required
def service_detail(request: HttpRequest, service_id: int) -> HttpResponse:
    service = get_object_or_404(Service, id=service_id)
    available_slots = []
    selected_date = request.GET.get('date')
    error_message = None

    if selected_date:
        try:
            date_obj = datetime.datetime.strptime(selected_date, '%Y-%m-%d')
            available_slots = get_available_slots(service.mentor.user, date_obj, service.duration)
        except ValueError:
            pass

    if request.method == 'POST':
        # 1. АНТИ-СПАМ
        has_active = Booking.objects.filter(
            client=request.user.profile,
            mentor=service.mentor,
            status='confirmed',
            start_time__gte=timezone.now()
        ).exists()

        if has_active:
            # Це повідомлення тепер з'явиться в dashboard.html!
            messages.warning(request, '⚠️ Ви вже маєте активний запис до цього ментора. Дочекайтесь завершення.')
            return redirect('dashboard')

        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        note_text = request.POST.get('note', '')[:500]

        if date_str and time_str:
            start_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

            summary = f"{service.title} - {request.user.first_name}"
            google_description = f"Клієнт: {request.user.first_name}\nEmail: {request.user.email}\n📞 {note_text}"

            # 2. КАЛЕНДАР МЕНТОРА
            mentor_event_id = None
            if service.mentor.user.social_auth.exists():
                try:
                    mentor_event_id = create_google_event(
                        service.mentor.user,
                        start_dt,
                        service.duration,
                        summary,
                        description=google_description
                    )
                except Exception:
                    pass

            # 3. КАЛЕНДАР КЛІЄНТА (Зберігаємо ID!)
            client_event_id = None
            if request.user.social_auth.exists():
                try:
                    client_event_id = create_google_event(
                        request.user,
                        start_dt,
                        service.duration,
                        f"{service.title} - {service.mentor.user.first_name}",
                        description=f"Ментор: {service.mentor.user.first_name}\nПослуга: {service.title}"
                    )
                except Exception:
                    pass

            # 4. ЗБЕРІГАЄМО ОБИДВА ID
            Booking.objects.create(
                client=request.user.profile,
                mentor=service.mentor,
                service=service,
                start_time=start_dt,
                end_time=start_dt + datetime.timedelta(minutes=service.duration),
                google_event_id=mentor_event_id,  # ID Ментора
                client_google_event_id=client_event_id,  # ID Клієнта (НОВЕ)
                price_at_booking=service.price,
                status='confirmed',
                note=note_text
            )

            messages.success(request, 'Бронювання успішне! 🎉')
            return redirect('dashboard')

    return render(request, 'user/service_detail.html', {
        'service': service,
        'slots': available_slots,
        'selected_date': selected_date,
        'error_message': error_message
    })


@login_required
def cancel_booking(request: HttpRequest, booking_id: int) -> HttpResponse:
    booking = get_object_or_404(Booking, id=booking_id, client=request.user.profile)

    if booking.start_time < timezone.now():
        messages.error(request, "Не можна скасувати минуле заняття.")
        return redirect('dashboard')

    # 1. Видаляємо у МЕНТОРА
    if booking.google_event_id and booking.mentor.user.social_auth.exists():
        try:
            service = get_google_calendar_service(booking.mentor.user)
            if service:
                service.events().delete(calendarId='primary', eventId=booking.google_event_id).execute()
        except Exception as e:
            print(f"Помилка видалення у ментора: {e}")

    # 2. Видаляємо у КЛІЄНТА (Тепер це спрацює!)
    if booking.client_google_event_id and request.user.social_auth.exists():
        try:
            service = get_google_calendar_service(request.user)
            if service:
                service.events().delete(calendarId='primary', eventId=booking.client_google_event_id).execute()
        except Exception as e:
            print(f"Помилка видалення у клієнта: {e}")

    booking.delete()
    messages.info(request, "Бронювання скасовано, календар оновлено.")
    return redirect('dashboard')


# --- ВІДГУКИ ---

@login_required
def add_review(request: HttpRequest, booking_id: int) -> HttpResponse:
    booking = get_object_or_404(Booking, id=booking_id, client=request.user.profile)

    if hasattr(booking, 'review'):
        messages.warning(request, "Ви вже залишили відгук для цього заняття.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.save()
            messages.success(request, 'Дякуємо за ваш відгук! ⭐')
            return redirect('dashboard')
    else:
        form = ReviewForm()

    return render(request, 'user/add_review.html', {'form': form, 'booking': booking})