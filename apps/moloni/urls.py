# apps/moloni/urls.py

from django.urls import path
from .views import SelectCompanyView, moloni_login, moloni_user_callback, select_company, ConfigMoloniView, save_credentials

app_name = 'moloni'

urlpatterns = [
    path('select/', SelectCompanyView.as_view(), name='select-company'),
    path('login-moloni/', moloni_login, name='moloni-login'),
    path('callback-moloni/', moloni_user_callback, name='moloni-user-callback'),
    path('select/<int:company_id>/', select_company, name='select_company_id'), 
    path('config/', ConfigMoloniView.as_view(), name='config'),
    path('save-credentials/', save_credentials, name='save_credentials'),
]
