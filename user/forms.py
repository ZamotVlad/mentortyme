from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import Profile, Service, Review

User = get_user_model()


# РЕЄСТРАЦІЯ

class CustomUserCreationForm(UserCreationForm):
    """Форма реєстрації з додатковими полями (ім'я, прізвище, email)"""

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


# РЕДАГУВАННЯ ПРОФІЛЮ

class UserUpdateForm(forms.ModelForm):
    """Форма для редагування базової інформації користувача"""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Іван',
                'maxlength': '70'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Петренко',
                'maxlength': '70'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
        }

        labels = {
            'first_name': "Ім'я",
            'last_name': "Прізвище",
            'email': "Email адреса",
        }


class ProfileUpdateForm(forms.ModelForm):
    """
    Форма для редагування додаткової інформації профілю
    Динамічно змінюється в залежності від ролі (клієнт/ментор)
    """

    class Meta:
        model = Profile
        fields = ['avatar', 'position', 'age', 'gender', 'city', 'bio']

        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'form-control'
            }),

            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Senior Python Developer',
                'maxlength': '50'
            }),

            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Київ, Україна',
                'maxlength': '50'
            }),

            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '25',
                'max': '100'
            }),

            'gender': forms.Select(attrs={
                'class': 'form-select'
            }),

            'bio': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Розкажіть про свій досвід...',
                'maxlength': '500'
            }),
        }

        labels = {
            'avatar': 'Фото профілю',
            'position': 'Ваша посада / Спеціалізація',
            'age': 'Вік',
            'gender': 'Стать',
            'city': 'Місто / Локація',
            'bio': 'Біографія',
        }

    def __init__(self, *args, **kwargs):
        """
        Динамічна зміна полів в залежності від ролі користувача
        Клієнти не мають поля 'position'
        """
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # ===== ДЛЯ КЛІЄНТІВ =====
            if self.instance.role == 'client':
                # Видаляємо поле "Посада" для клієнтів
                if 'position' in self.fields:
                    del self.fields['position']

                # Змінюємо назву і placeholder для біо
                self.fields['bio'].label = "Про себе"
                self.fields['bio'].widget.attrs['placeholder'] = "Кілька слів про ваші інтереси..."

            # ===== ДЛЯ МЕНТОРІВ =====
            else:
                self.fields['bio'].label = "Біографія (те, що побачать клієнти)"
                self.fields['bio'].help_text = "Це перше, що прочитає ваш потенційний учень."


# УПРАВЛІННЯ ПОСЛУГАМИ (тільки для менторів)

class ServiceForm(forms.ModelForm):
    """Форма створення/редагування послуги ментора"""

    class Meta:
        model = Service
        fields = ['title', 'description', 'duration', 'price', 'is_active']

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Напр. Менторська сесія Python',
                'maxlength': '50'
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Коротко опишіть, що входить у вартість (необов\'язково)',
                'maxlength': '500'
            }),

            'duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '60',
                'min': '15',
                'max': '180',
                'step': '15'
            }),

            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '500',
                'min': '0'
            }),

            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

        labels = {
            'title': 'Назва послуги',
            'description': 'Опис послуги',
            'duration': 'Тривалість (хв)',
            'price': 'Вартість (грн)',
            'is_active': 'Активна (показувати в профілі)',
        }


# ВІДГУКИ ТА ОЦІНКИ

class ReviewForm(forms.ModelForm):
    """Форма для залишення відгуку після завершення заняття"""

    class Meta:
        model = Review
        fields = ['rating', 'comment']

        widgets = {
            'rating': forms.Select(
                attrs={'class': 'form-select'},
                choices=[(i, f'{i} ⭐') for i in range(5, 0, -1)]
            ),

            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Як пройшло заняття? Що сподобалось?',
                'maxlength': '500',
                'style': 'resize: none'
            }),
        }

        labels = {
            'rating': 'Оцінка',
            'comment': 'Ваш відгук',
        }