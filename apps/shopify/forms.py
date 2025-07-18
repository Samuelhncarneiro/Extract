# apps/shopify/forms.py
from django import forms
from .models import Shopify

class ShopifyCredentialsForm(forms.ModelForm):
    class Meta:
        model = Shopify
        fields = ['shop_domain', 'access_token', 'email']
        widgets = {
            'shop_domain': forms.TextInput(attrs={'placeholder': 'sua-loja.myshopify.com'}),
            'access_token': forms.TextInput(attrs={'placeholder': 'shpat_...'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
        }
        labels = {
            'shop_domain': 'Domínio da Loja',
            'access_token': 'Token de Acesso',
            'email': 'Email de Contato',
        }
        help_texts = {
            'shop_domain': 'Ex: sua-loja.myshopify.com',
            'access_token': 'Você pode encontrar isso nas configurações do app Shopify',
        }