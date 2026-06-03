import pytest
import datetime
from django.urls import reverse
from django.contrib.auth import get_user_model
from user.models import WorkingHour
from user.utils import get_available_slots

User = get_user_model()


@pytest.mark.django_db
def test_home_view_returns_200(client):
    """Перевіряє, що головна сторінка успішно завантажується"""
    url = reverse('home')
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_get_available_slots_logic():
    """Перевіряє, чи правильно функція формує слоти за графіком ментора"""

    mentor_user = User.objects.create_user(
        username='test_mentor',
        first_name='Ivan',
        last_name='Petrenko'
    )

    mentor_profile = mentor_user.profile
    mentor_profile.role = 'mentor'
    mentor_profile.save()

    test_date = datetime.date(2026, 6, 3)

    WorkingHour.objects.create(
        mentor=mentor_profile,
        day_of_week=2,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(11, 0)
    )

    slots = get_available_slots(mentor_user, test_date, duration_minutes=60)

    assert len(slots) == 1
    assert slots[0] == '09:00'