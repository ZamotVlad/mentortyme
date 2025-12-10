from django.contrib import admin
from django.urls import path, include
from user import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('service/<int:service_id>/', views.service_detail, name='service_detail'),
    path('oauth/', include('social_django.urls', namespace='social')),  # Google Auth
    path('accounts/', include('django.contrib.auth.urls')),
    path('register/', views.register, name='register'),
    path('pro/<slug:slug>/', views.mentor_profile, name='mentor_profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('booking/cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('settings/', views.profile_settings, name='profile_settings'),
    path('my-services/', views.my_services, name='my_services'),
    path('my-services/delete/<int:service_id>/', views.delete_service, name='delete_service'),
    path('schedule/', views.schedule_settings, name='schedule_settings'),
    path('booking/<int:booking_id>/review/', views.add_review, name='add_review'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
