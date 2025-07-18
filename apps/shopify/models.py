# apps/shopify/models.py
from django.db import models
from django.conf import settings

class Shopify(models.Model):
    """Modelo para armazenar informações da loja Shopify"""
    shop_domain = models.CharField(max_length=255, unique=True, help_text="Domínio da loja Shopify (exemplo: loja.myshopify.com)")
    access_token = models.CharField(max_length=255, help_text="Token de acesso à API do Shopify")
    email = models.EmailField(null=True, blank=True, help_text="Email associado à conta Shopify")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Data de criação do registro")
    updated_at = models.DateTimeField(auto_now=True, help_text="Data da última atualização")
    is_active = models.BooleanField(default=True, help_text="Indica se a loja está ativa")
    
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='shopify_stores')

    def __str__(self):
        """Representação em string do modelo"""
        return self.shop_domain
    
    class Meta:
        verbose_name = "Loja Shopify"
        verbose_name_plural = "Lojas Shopify"
        ordering = ['-created_at']