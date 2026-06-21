from django import forms
from .models import Registration


class RegistrationForm(forms.ModelForm):
    """Форма регистрации на мероприятие"""
    
    class Meta:
        model = Registration
        fields = ['full_name', 'email', 'phone', 'spots', 'comment']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Иванов Иван Иванович'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'example@mail.ru'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+7 (999) 999-99-99'
            }),
            'spots': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительная информация (необязательно)'
            }),
        }