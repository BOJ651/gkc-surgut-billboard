from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('events/', views.events_list, name='events'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('events/<int:event_id>/registration/', views.registration, name='registration'),
]