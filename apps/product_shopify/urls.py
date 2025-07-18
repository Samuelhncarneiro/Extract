# apps/product_shopify/urls.py
from django.urls import path
from . import views


urlpatterns = [
    # Views para interface
    path('', views.ProductShopifyView.as_view(), name='product_shopify'),
    path('api/products/', views.get_products, name='api_products'),
    path('api/products/<int:product_id>/', views.get_product_details, name='api_product_details'),
    path('api/sync/', views.sync_products, name='api_sync'),
    path('api/products/<int:product_id>/delete/', views.delete_product, name='api_delete_product'),
]