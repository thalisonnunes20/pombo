from django.urls import path
from . import views

urlpatterns = [
    # APIs internas do painel
    path('api/create/', views.create_link_api, name='api_create_link'),
    path('api/toggle/<int:link_id>/', views.toggle_link_status_api, name='api_toggle_link'),
    path('api/delete/<int:link_id>/', views.delete_link_api, name='api_delete_link'),

    # Rotas públicas de entrega
    path('s/<str:token>/', views.public_landing_view, name='public_landing'),
    path('d/<str:token>/', views.direct_download_view, name='direct_download'),
]

