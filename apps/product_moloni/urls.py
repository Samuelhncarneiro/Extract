# apps/product_moloni/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProductMoloniView.as_view(), name='product_moloni'),
    
    path('api/products/', views.get_products, name='get_products'),
    path('api/products/<int:product_id>/', views.get_product_details, name='get_product_details'),
    path('api/sync-products/', views.sync_products, name='sync_products'),
    path('api/quick-sync-status/', views.quick_sync_status, name='api_quick_sync_status'),

    # APIs para processamento em background
    path('api/start-background-sync/', views.start_background_sync, name='api_start_background_sync'),
    path('api/sync-progress/', views.get_sync_progress, name='api_sync_progress'),
    path('api/cancel-background-sync/', views.cancel_background_sync, name='api_cancel_background_sync'),
    
    # NOVA API para verificação de sync automático
    path('api/check-auto-sync/', views.check_auto_sync_status, name='api_check_auto_sync'),
    
    # Página de status (opcional)
    path('sync-status/', views.sync_status_page, name='sync_status_page'),
]
