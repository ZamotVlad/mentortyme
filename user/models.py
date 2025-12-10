from django.db import models
from django.db.models import Avg
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils.text import slugify


class User(AbstractUser):
    pass


class Profile(models.Model):
    ROLE_CHOICES = (
        ('client', 'Клієнт'),
        ('mentor', 'Ментор'),
    )

    GENDER_CHOICES = (
        ('male', 'Чоловік'),
        ('female', 'Жінка'),
        ('other', 'Стать не вказана'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')

    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png', blank=True)

    bio = models.TextField(max_length=500, blank=True, default='', verbose_name="Про себе")

    age = models.PositiveIntegerField(blank=True, null=True, verbose_name="Вік")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True, verbose_name="Стать")
    city = models.CharField(max_length=50, blank=True, null=True, verbose_name="Місто")

    position = models.CharField(max_length=50, blank=True, null=True, verbose_name="Посада")

    slug = models.SlugField(unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.user.first_name + " " + self.user.last_name)
            if not base_slug:
                base_slug = slugify(self.user.username)
            self.slug = base_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} Profile"

    def get_average_rating(self):
        reviews = Review.objects.filter(booking__mentor=self)
        if reviews.exists():
            return round(reviews.aggregate(Avg('rating'))['rating__avg'], 1)
        return None


class Service(models.Model):
    mentor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='services')
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=500, blank=True, default='')
    duration = models.PositiveIntegerField(help_text="Тривалість у хвилинах")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} - {self.price} грн"


class WorkingHour(models.Model):
    DAY_CHOICES = (
        (0, 'Понеділок'), (1, 'Вівторок'), (2, 'Середа'), (3, 'Четвер'),
        (4, 'П\'ятниця'), (5, 'Субота'), (6, 'Неділя'),
    )
    mentor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.get_day_of_week_display()}: {self.start_time}-{self.end_time}"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('confirmed', 'Підтверджено'),
        ('cancelled', 'Скасовано'),
        ('completed', 'Завершено'),
    )
    client = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='client_bookings')
    mentor = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='mentor_bookings')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    google_event_id = models.CharField(max_length=255, blank=True, null=True)
    client_google_event_id = models.CharField(max_length=255, blank=True, null=True)
    price_at_booking = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    note = models.TextField(blank=True, null=True, verbose_name="Контакти або примітка")

    def save(self, *args, **kwargs):
        if not self.price_at_booking and self.service:
            self.price_at_booking = self.service.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking {self.id}"


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)