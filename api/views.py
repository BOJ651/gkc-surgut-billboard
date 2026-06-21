from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class APIInfoView(APIView):
    """Информация о API"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response({
            'name': 'GKC Surgut API',
            'version': '1.0.0',
            'description': 'API для Городского культурного центра Сургута',
            'endpoints': {
                'events': '/api/events/',
                'registrations': '/api/registrations/',
                'auth': '/api/auth/token/',
            }
        })