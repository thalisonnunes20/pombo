from django.urls import path
from . import views

urlpatterns = [
    path('api/upload/', views.upload_file_api, name='api_storage_upload'),
    path('api/scan/', views.scan_storage_api, name='api_storage_scan'),
    path('api/delete/<int:file_id>/', views.delete_file_api, name='api_storage_delete'),
    path('download/<int:file_id>/', views.admin_download_file, name='admin_download_file'),
]
