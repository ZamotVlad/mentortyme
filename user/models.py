from django.db import models
from django.db.models import Avg
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils.text import slugify


# КОРИСТУВАЧ

class User(AbstractUser):
    """Розширена модель користувача (на майбутнє)"""
    pass


# ПРОФІЛЬ КОРИСТУВАЧА

class Profile(models.Model):
    """
    Профіль користувача з роллю (клієнт або ментор)
    Містить додаткову інформацію: аватар, біо, вік, стать, місто, посада
    """
    ROLE_CHOICES = (
        ('client', 'Клієнт'),
        ('mentor', 'Ментор'),
    )

    GENDER_CHOICES = (
        ('male', 'Чоловік'),
        ('female', 'Жінка'),
        ('other', 'Стать не вказана'),
    )

    # ===== ОСНОВНІ ПОЛЯ =====
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='client'
    )

    # ===== ПУБЛІЧНА ІНФОРМАЦІЯ =====
    avatar = models.ImageField(
        upload_to='avatars/',
        default='avatars/default.png',
        blank=True
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
        default='',
        verbose_name="Про себе"
    )

    # ===== ОСОБИСТІ ДАНІ =====
    age = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Вік"
    )
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True,
        null=True,
        verbose_name="Стать"
    )
    city = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Місто"
    )

    # ===== ДЛЯ МЕНТОРІВ =====
    position = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Посада"
    )

    # ===== SLUG ДЛЯ URL =====
    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        """Автоматичне створення slug при збереженні"""
        if not self.slug:
            base_slug = slugify(self.user.first_name + " " + self.user.last_name)
            if not base_slug:
                base_slug = slugify(self.user.username)
            self.slug = base_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} Profile"

    def get_average_rating(self):
        """Розрахунок середнього рейтингу ментора"""
        reviews = Review.objects.filter(booking__mentor=self)
        if reviews.exists():
            return round(reviews.aggregate(Avg('rating'))['rating__avg'], 1)
        return None


# ПОСЛУГИ МЕНТОРІВ

class Service(models.Model):
    """
    Послуга, яку пропонує ментор
    Містить назву, опис, тривалість, ціну та статус активності
    """
    mentor = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='services'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=500, blank=True, default='')
    duration = models.PositiveIntegerField(help_text="Тривалість у хвилинах")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} - {self.price} грн"


# ГРАФІК РОБОТИ МЕНТОРА

class WorkingHour(models.Model):
    """
    Робочі години ментора для конкретного дня тижня
    Використовується для розрахунку доступних слотів
    """
    DAY_CHOICES = (
        (0, 'Понеділок'),
        (1, 'Вівторок'),
        (2, 'Середа'),
        (3, 'Четвер'),
        (4, 'П\'ятниця'),
        (5, 'Субота'),
        (6, 'Неділя'),
    )

    mentor = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='working_hours'
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.get_day_of_week_display()}: {self.start_time}-{self.end_time}"


# БРОНЮВАННЯ

class Booking(models.Model):
    """
    Бронювання заняття між клієнтом і ментором
    Містить інформацію про час, статус, ціну та зв'язок з Google Calendar
    """
    STATUS_CHOICES = (
        ('confirmed', 'Підтверджено'),
        ('cancelled', 'Скасовано'),
        ('completed', 'Завершено'),
    )

    # ===== ХТО ТА ЩО =====
    client = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='client_bookings'
    )
    mentor = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='mentor_bookings'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # ===== КОЛИ =====
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='confirmed'
    )

    # ===== ІНТЕГРАЦІЯ З GOOGLE CALENDAR =====
    google_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID події в календарі ментора"
    )
    client_google_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID події в календарі клієнта"
    )

    # ===== ФІНАНСИ ТА ПРИМІТКИ =====
    price_at_booking = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Ціна на момент бронювання (фіксується)"
    )
    note = models.TextField(
        blank=True,
        null=True,
        verbose_name="Контакти або примітка"
    )

    def save(self, *args, **kwargs):
        """Автоматичне збереження ціни при створенні"""
        if not self.price_at_booking and self.service:
            self.price_at_booking = self.service.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking {self.id}"


# ВІДГУКИ ТА ОЦІНКИ

class Review(models.Model):
    """
    Відгук клієнта про проведене заняття
    Один відгук на одне бронювання (OneToOne)
    """
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='review'
    )
    rating = models.PositiveIntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Оцінка (1-5)"
    )
    comment = models.TextField(verbose_name="Коментар")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for Booking {self.booking.id} - {self.rating}★"