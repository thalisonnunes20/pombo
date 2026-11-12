from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/users/create/', views.create_user_api, name='api_create_user'),
    path('api/users/toggle/<int:user_id>/', views.toggle_user_status_api, name='api_toggle_user'),
]

