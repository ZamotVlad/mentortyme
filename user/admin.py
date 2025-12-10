from django.contrib import admin
from django.contrib import admin
from .models import User, Profile, Service, WorkingHour, Booking, Review

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'slug')
    list_filter = ('role',) # Фільтр збоку (Ментор/Клієнт)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'mentor', 'price', 'duration', 'is_active')
    list_filter = ('is_active',)

@admin.register(WorkingHour)
class WorkingHourAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week',)

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'mentor', 'client', 'service', 'start_time', 'status')
    list_filter = ('status', 'start_time')
    readonly_fields = ('price_at_booking',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('booking', 'rating', 'created_at')
