# apps/shopify/urls.py
from django.urls import path
from . import views
from .views import ShopifyConnectionView, ShopifyAuthenticateView, ShopifyCallbackView

app_name = 'shopify'

urlpatterns = [
    path('connect/', ShopifyConnectionView.as_view(), name='connect'),
    path('authenticate/<str:shop_domain>/', ShopifyAuthenticateView.as_view(), name='authenticate'),
    path('callback/', ShopifyCallbackView.as_view(), name='callback'),
]   