from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Event, Registration


@admin.action(description='Опубликовать выбранные мероприятия')
def publish_events(modeladmin, request, queryset):
    queryset.update(status='published')


@admin.action(description='Снять с публикации')
def unpublish_events(modeladmin, request, queryset):
    queryset.update(status='draft')


@admin.action(description='Отменить мероприятия')
def cancel_events(modeladmin, request, queryset):
    queryset.update(status='cancelled')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'date', 'category', 'status', 
        'available_spots_display', 'price_display',
        'created_at'
    ]
    list_filter = ['category', 'status', 'date', 'created_at']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['slug', 'created_at', 'updated_at', 'registered_count', 'available_spots']
    date_hierarchy = 'date'
    list_editable = ['status']
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'description', 'category', 'status')
        }),
        ('Дата и место', {
            'fields': ('date', 'end_date', 'location', 'location_lat', 'location_lon')
        }),
        ('Билеты', {
            'fields': ('price', 'max_capacity', 'registered_count')
        }),
        ('Медиа', {
            'fields': ('image',)
        }),
        ('Мета-информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [publish_events, unpublish_events, cancel_events]
    
    def available_spots_display(self, obj):
        available = obj.available_spots
        if available == 0:
            return format_html('<span style="color: red;">Мест нет</span>')
        elif available < 10:
            return format_html('<span style="color: orange;">{} мест</span>', available)
        return format_html('<span style="color: green;">{} мест</span>', available)
    available_spots_display.short_description = 'Доступно мест'
    
    def price_display(self, obj):
        if obj.is_free:
            return format_html('<span style="color: green;">Бесплатно</span>')
        return f"{obj.price} ₽"
    price_display.short_description = 'Цена'
    
    def available_spots(self, obj):
        return obj.available_spots
    available_spots.short_description = 'Доступно мест'


@admin.action(description='Подтвердить выбранные регистрации')
def confirm_registrations(modeladmin, request, queryset):
    updated = 0
    for reg in queryset.filter(status='pending'):
        reg.confirm()
        updated += 1
    modeladmin.message_user(request, f'Подтверждено {updated} регистраций')


@admin.action(description='Отклонить выбранные регистрации')
def reject_registrations(modeladmin, request, queryset):
    updated = 0
    for reg in queryset.filter(status='pending'):
        reg.reject()
        updated += 1
    modeladmin.message_user(request, f'Отклонено {updated} регистраций')


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'event_link', 
        'spots', 'status', 'created_at', 'confirmed_at'
    ]
    list_filter = ['status', 'event__category', 'created_at']
    search_fields = ['full_name', 'email', 'event__title']
    readonly_fields = ['idempotency_key', 'created_at', 'updated_at', 'confirmed_at']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Информация о регистрации', {
            'fields': ('event', 'full_name', 'email', 'phone', 'spots')
        }),
        ('Статус', {
            'fields': ('status', 'comment')
        }),
        ('Техническая информация', {
            'fields': ('idempotency_key', 'created_at', 'updated_at', 'confirmed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [confirm_registrations, reject_registrations]
    
    def event_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:core_event_change', args=[obj.event.id])
        return format_html('<a href="{}">{}</a>', url, obj.event.title)
    event_link.short_description = 'Мероприятие'