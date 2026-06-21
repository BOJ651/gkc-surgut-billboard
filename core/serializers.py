from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from .models import Event, Registration


class EventListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка мероприятий"""
    available_spots = serializers.ReadOnlyField()
    is_free = serializers.ReadOnlyField()
    date_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'date', 'date_formatted', 
            'location', 'price', 'category', 'available_spots', 
            'is_free', 'status', 'image'
        ]
        read_only_fields = ['slug', 'available_spots', 'is_free']
    
    def get_date_formatted(self, obj):
        return obj.date.strftime('%d.%m.%Y %H:%M')


class EventDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детальной информации о мероприятии"""
    available_spots = serializers.ReadOnlyField()
    is_free = serializers.ReadOnlyField()
    registrations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['slug', 'available_spots', 'is_free', 'registered_count']
    
    def get_registrations_count(self, obj):
        return obj.registrations.filter(status='confirmed').count()


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления мероприятия"""
    
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['slug', 'registered_count', 'created_at', 'updated_at']
    
    def validate_date(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Дата мероприятия не может быть в прошлом")
        return value
    
    def validate(self, data):
        if data.get('end_date') and data.get('date'):
            if data['end_date'] <= data['date']:
                raise serializers.ValidationError({
                    'end_date': "Дата окончания должна быть позже даты начала"
                })
        return data


class RegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации на мероприятие"""
    event_title = serializers.CharField(source='event.title', read_only=True)
    event_date = serializers.DateTimeField(source='event.date', read_only=True)
    
    class Meta:
        model = Registration
        fields = [
            'id', 'event', 'event_title', 'event_date',
            'full_name', 'email', 'phone', 'spots',
            'status', 'comment', 'created_at'
        ]
        read_only_fields = ['status', 'created_at', 'event_title', 'event_date']
    
    def validate_phone(self, value):
        """Валидация номера телефона"""
        cleaned = re.sub(r'[^\d+]', '', value)
        
        if not re.match(r'^\+?[1-9]\d{0,15}$', cleaned):
            raise serializers.ValidationError(
                "Неверный формат телефона. Используйте формат: +7XXXXXXXXXX"
            )
        return cleaned
    
    def validate_email(self, value):
        """Проверка email на уникальность в рамках мероприятия"""
        event_id = self.initial_data.get('event')
        if event_id:
            if Registration.objects.filter(
                event_id=event_id,
                email=value,
                status__in=['pending', 'confirmed']
            ).exists():
                raise serializers.ValidationError(
                    "На это мероприятие уже есть регистрация с данным email"
                )
        return value
    
    def validate(self, data):
        """Дополнительная валидация"""
        event = data.get('event')
        spots = data.get('spots', 1)
        
        if event:
            if spots > event.available_spots:
                raise serializers.ValidationError({
                    'spots': f"Доступно только {event.available_spots} мест"
                })
            
            if event.status == 'cancelled':
                raise serializers.ValidationError({
                    'event': "Мероприятие отменено"
                })
            
            if event.date < timezone.now():
                raise serializers.ValidationError({
                    'event': "Мероприятие уже прошло"
                })
        
        return data


class RegistrationAdminSerializer(serializers.ModelSerializer):
    """Сериализатор для административной панели"""
    event_title = serializers.CharField(source='event.title', read_only=True)
    
    class Meta:
        model = Registration
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']