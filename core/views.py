from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework import renderers, parsers
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator
from django.contrib import messages
import uuid

from .models import Event, Registration
from .serializers import (
    EventListSerializer,
    EventDetailSerializer,
    EventCreateUpdateSerializer,
    RegistrationSerializer,
)
from .forms import RegistrationForm

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'date']
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['date', 'created_at', 'price']
    ordering = ['date']
    
    renderer_classes = [renderers.JSONRenderer]
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EventListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return EventCreateUpdateSerializer
        return EventDetailSerializer
    
    def get_queryset(self):
        queryset = Event.objects.all()
        if self.action == 'list' and not self.request.user.is_staff:
            queryset = queryset.filter(status='published', date__gte=timezone.now())
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date__date__lte=date_to)
            
        if self.request.query_params.get('has_spots') == 'true':
            queryset = queryset.filter(Q(max_capacity=0) | Q(registered_count__lt=F('max_capacity')))
            
        if self.request.query_params.get('is_free') == 'true':
            queryset = queryset.filter(Q(price__isnull=True) | Q(price=0))
            
        return queryset
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['get'])
    def registrations(self, request, pk=None):
        event = self.get_object()
        registrations = event.registrations.all().select_related('event')
        serializer = RegistrationSerializer(registrations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        event = self.get_object()
        stats = {
            'total_registrations': event.registrations.count(),
            'confirmed_registrations': event.registrations.filter(status='confirmed').count(),
            'pending_registrations': event.registrations.filter(status='pending').count(),
            'total_spots': event.registered_count,
            'available_spots': event.available_spots,
            'revenue': float(event.price * event.registrations.filter(status='confirmed').count()) if event.price else 0,
        }
        return Response(stats)


class RegistrationViewSet(viewsets.ModelViewSet):
    queryset = Registration.objects.all().select_related('event')
    serializer_class = RegistrationSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event', 'status']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff and hasattr(self.request.user, 'email'):
            queryset = queryset.filter(email=self.request.user.email)
        return queryset
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        idempotency_key = request.headers.get('Idempotency-Key')
        if idempotency_key:
            try:
                uuid.UUID(idempotency_key)
            except ValueError:
                return Response({'error': 'Invalid Idempotency-Key format'}, status=status.HTTP_400_BAD_REQUEST)
            
            existing = Registration.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return Response({'message': 'Запрос уже обработан', 'id': existing.id, 'status': existing.status}, status=status.HTTP_200_OK)
        
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=serializer.validated_data['event'].pk)
            if serializer.validated_data['spots'] > event.available_spots:
                return Response({'spots': 'Недостаточно свободных мест'}, status=status.HTTP_409_CONFLICT)
            
            registration = serializer.save(idempotency_key=idempotency_key)
            event.registered_count += registration.spots
            event.save(update_fields=['registered_count', 'updated_at'])
        
        from notifications.tasks import send_confirmation_email
        send_confirmation_email.delay(registration.id, registration.email)
        
        headers = self.get_success_headers(serializer.data)
        return Response({'message': 'Заявка успешно создана', 'id': registration.id, 'status': registration.status, **serializer.data}, status=status.HTTP_201_CREATED, headers=headers)


@api_view(['GET'])
@permission_classes([AllowAny])
def upcoming_events(request):
    events = Event.objects.filter(status='published', date__gte=timezone.now()).order_by('date')[:5]
    serializer = EventListSerializer(events, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_events(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return Response({'error': 'Запрос слишком короткий'}, status=status.HTTP_400_BAD_REQUEST)
    
    events = Event.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query)
    ).filter(status='published', date__gte=timezone.now())[:10]
    
    serializer = EventListSerializer(events, many=True)
    return Response(serializer.data)

def index(request):
    """Главная страница"""
    upcoming = Event.objects.filter(
        status='published',
        date__gte=timezone.now()
    ).order_by('date')[:6]
    return render(request, 'core/index.html', {'upcoming_events': upcoming})


def events_list(request):
    """Страница афиши с фильтрами и пагинацией"""
    events = Event.objects.filter(status='published', date__gte=timezone.now()).order_by('date')
    
    category = request.GET.get('category')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if category:
        events = events.filter(category=category)
    if date_from:
        events = events.filter(date__date__gte=date_from)
    if date_to:
        events = events.filter(date__date__lte=date_to)
        
    paginator = Paginator(events, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/events.html', {'events': page_obj, 'page_obj': page_obj})


def event_detail(request, pk):
    """Детальная страница мероприятия"""
    event = get_object_or_404(Event, pk=pk, status='published')
    return render(request, 'core/event_detail.html', {'event': event})


def registration(request, event_id):
    """Форма регистрации на мероприятие"""
    event = get_object_or_404(Event, pk=event_id, status='published')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            spots = form.cleaned_data['spots']
            if spots > event.available_spots:
                form.add_error('spots', f'Доступно только {event.available_spots} мест')
            else:
                try:
                    reg = form.save(commit=False)
                    reg.event = event
                    reg.save()
                    
                    event.registered_count += spots
                    event.save(update_fields=['registered_count'])
                    
                    messages.success(request, 'Вы успешно зарегистрированы! Проверьте почту для подтверждения.')
                    return redirect('core:event_detail', pk=event.pk)
                except Exception as e:
                    messages.error(request, f'Ошибка при регистрации: {str(e)}')
    else:
        form = RegistrationForm()
        
    return render(request, 'core/registration.html', {'event': event, 'form': form})