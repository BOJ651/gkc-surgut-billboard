from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Event(models.Model):
    """Модель мероприятия"""
    
    CATEGORY_CHOICES = [
        ('concert', 'Концерты'),
        ('theater', 'Театр'),
        ('workshop', 'Мастер-классы'),
        ('exhibition', 'Выставки'),
        ('festival', 'Фестивали'),
        ('other', 'Другое'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликовано'),
        ('cancelled', 'Отменено'),
        ('completed', 'Завершено'),
    ]
    
    title = models.CharField(
        max_length=255,
        verbose_name='Название мероприятия',
        db_index=True
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        blank=True,
        verbose_name='URL'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    date = models.DateTimeField(
        verbose_name='Дата и время проведения',
        db_index=True
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата окончания'
    )
    location = models.CharField(
        max_length=500,
        verbose_name='Место проведения'
    )
    location_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name='Широта'
    )
    location_lon = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name='Долгота'
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Стоимость билета',
        validators=[MinValueValidator(0)]
    )
    max_capacity = models.PositiveIntegerField(
        default=0,
        verbose_name='Максимальное количество мест'
    )
    registered_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Зарегистрировано участников'
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        blank=True,
        verbose_name='Категория'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='Статус'
    )
    image = models.ImageField(
        upload_to='events/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name='Изображение'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        verbose_name = 'Мероприятие'
        verbose_name_plural = 'Мероприятия'
        ordering = ['date']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['category', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.date.strftime('%d.%m.%Y')})"
    
    @property
    def available_spots(self):
        """Доступные места"""
        if self.max_capacity == 0:
            return 999  # Неограничено
        return max(0, self.max_capacity - self.registered_count)
    
    @property
    def is_free(self):
        """Бесплатное ли мероприятие"""
        return self.price is None or self.price == 0
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.title, allow_unicode=False)
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Registration(models.Model):
    """Модель регистрации на мероприятие"""
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает подтверждения'),
        ('confirmed', 'Подтверждено'),
        ('rejected', 'Отклонено'),
        ('cancelled', 'Отменено пользователем'),
    ]
    
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='registrations',
        verbose_name='Мероприятие'
    )
    full_name = models.CharField(
        max_length=255,
        verbose_name='ФИО'
    )
    email = models.EmailField(
        verbose_name='Email'
    )
    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон'
    )
    spots = models.PositiveIntegerField(
        default=1,
        verbose_name='Количество мест',
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус'
    )
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Ключ идемпотентности'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата подтверждения'
    )
    
    class Meta:
        verbose_name = 'Регистрация'
        verbose_name_plural = 'Регистрации'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'email'],
                name='unique_email_per_event',
                violation_error_message='На это мероприятие уже зарегистрирован данный email'
            ),
        ]
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['email', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.full_name} → {self.event.title}"
    
    def confirm(self):
        """Подтвердить регистрацию"""
        self.status = 'confirmed'
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'updated_at'])
    
    def reject(self):
        """Отклонить регистрацию"""
        self.status = 'rejected'
        self.save(update_fields=['status', 'updated_at'])