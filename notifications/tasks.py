from celery import shared_task
from django.core.mail import send_mail, mail_admins
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_confirmation_email(self, registration_id, recipient_email):
    """
    Отправка подтверждения регистрации на email
    
    Args:
        registration_id: ID регистрации
        recipient_email: Email получателя
    """
    try:
        from core.models import Registration
        
        registration = Registration.objects.select_related('event').get(id=registration_id)
        
        subject = f'✅ Регистрация на мероприятие: {registration.event.title}'
        
        context = {
            'registration': registration,
            'event': registration.event,
            'full_name': registration.full_name,
            'event_date': registration.event.date.strftime('%d.%m.%Y %H:%M'),
            'location': registration.event.location,
        }
        
        html_message = render_to_string('emails/registration_confirmation.html', context)
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f'Email sent to {recipient_email} for registration {registration_id}')
        return True
        
    except Registration.DoesNotExist:
        logger.error(f'Registration {registration_id} not found')
        return False
    except Exception as exc:
        logger.error(f'Error sending email to {recipient_email}: {exc}')
        self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_admin_notification(self, registration_id):
    """
    Уведомление администраторов о новой регистрации
    """
    try:
        from core.models import Registration
        
        registration = Registration.objects.select_related('event').get(id=registration_id)
        
        subject = f'🔔 Новая регистрация: {registration.full_name}'
        
        message = f"""
        Новая регистрация на мероприятие:
        
        Мероприятие: {registration.event.title}
        Дата: {registration.event.date.strftime('%d.%m.%Y %H:%M')}
        
        Участник: {registration.full_name}
        Email: {registration.email}
        Телефон: {registration.phone}
        Мест: {registration.spots}
        
        Статус: {registration.get_status_display()}
        Дата регистрации: {registration.created_at.strftime('%d.%m.%Y %H:%M')}
        
        Админка: {settings.SITE_URL}/admin/core/registration/{registration.id}/change/
        """
        
        mail_admins(
            subject=subject,
            message=message,
            fail_silently=False,
        )
        
        logger.info(f'Admin notification sent for registration {registration_id}')
        return True
        
    except Exception as exc:
        logger.error(f'Error sending admin notification: {exc}')
        self.retry(exc=exc)


@shared_task
def cleanup_old_registrations():
    """
    Очистка старых отмененных регистраций (старше 30 дней)
    """
    from core.models import Registration
    from django.utils import timezone
    
    cutoff_date = timezone.now() - timezone.timedelta(days=30)
    
    deleted_count, _ = Registration.objects.filter(
        status='cancelled',
        updated_at__lt=cutoff_date
    ).delete()
    
    logger.info(f'Cleaned up {deleted_count} old cancelled registrations')
    return deleted_count


@shared_task
def send_event_reminder(event_id):
    """
    Напоминание о мероприятии за 24 часа
    """
    from core.models import Event, Registration
    from django.utils import timezone
    
    try:
        event = Event.objects.get(id=event_id)
        
        registrations = Registration.objects.filter(
            event=event,
            status='confirmed'
        ).select_related('event')
        
        for reg in registrations:
            subject = f'⏰ Напоминание: {event.title} завтра!'
            
            message = f"""
            Здравствуйте, {reg.full_name}!
            
            Напоминаем о мероприятии завтра:
            
            {event.title}
            Дата: {event.date.strftime('%d.%m.%Y %H:%M')}
            Место: {event.location}
            
            До встречи!
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reg.email],
                fail_silently=False,
            )
        
        logger.info(f'Sent reminders for event {event_id} to {registrations.count()} users')
        return registrations.count()
        
    except Exception as exc:
        logger.error(f'Error sending reminders for event {event_id}: {exc}')
        return 0