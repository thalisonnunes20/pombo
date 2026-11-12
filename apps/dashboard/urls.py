from django.urls import path
from . import views

urlpatterns = [
    path('', views.overview_view, name='dashboard_overview'),
    path('upload/', views.upload_view, name='dashboard_upload'),
    path('explorer/', views.explorer_view, name='dashboard_explorer'),
    path('links/', views.links_view, name='dashboard_links'),
    path('users/', views.users_view, name='dashboard_users'),
    path('logs/', views.logs_view, name='dashboard_logs'),
    path('api/logs/clear/', views.clear_logs_api, name='api_clear_logs'),
]

