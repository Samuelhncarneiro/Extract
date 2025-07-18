# apps/moloni/models.py
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User 
from django.utils import timezone
from datetime import timedelta

class MoloniCredentials(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='moloni_credentials')
    client_id = models.CharField(max_length=100)
    client_secret = models.CharField(max_length=255)
    redirect_uri = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Credencial Moloni"
        verbose_name_plural = "Credenciais Moloni"
    
    def __str__(self):
        return f"Credenciais do Moloni para {self.user.username}"

class Moloni(models.Model):
    company_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, null=True, blank=True)
    vat = models.CharField(max_length=50, null=True, blank=True)
    url_image = models.URLField(max_length=500, null=True, blank=True)
    
    moloni_access_token = models.CharField(max_length=100, null=True, blank=True)
    moloni_refresh_token = models.CharField(max_length=100, null=True, blank=True)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='companies')

    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_last_refreshed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at
    
    def is_token_expiring_soon(self, minutes=30):
        if not self.token_expires_at:
            return True
        return timezone.now() >= (self.token_expires_at - timedelta(minutes=minutes))
    
    def is_token_expiring_soon(self, minutes=45):
        if not self.token_expires_at:
            return True
        return timezone.now() >= (self.token_expires_at - timedelta(minutes=minutes))

    def is_refresh_token_expiring_soon(self, days=13):
        if not self.token_last_refreshed:
            return True
        refresh_expires_at = self.token_last_refreshed + timedelta(days=14)
        warning_time = refresh_expires_at - timedelta(days=(14-days))
        return timezone.now() >= warning_time

    def needs_access_token_refresh(self):
        return self.is_token_expiring_soon(minutes=15)

    def needs_reauth(self):
        return self.is_refresh_token_expiring_soon(days=13)

    def get_token_status(self):
        if not self.moloni_access_token:
            return 'no_token'
        elif self.is_token_expired():
            return 'expired'
        elif self.needs_reauth():
            return 'refresh_expiring'
        elif self.needs_access_token_refresh():
            return 'access_expiring'
        else:
            return 'valid'

    def days_until_refresh_expires(self):
        if not self.token_last_refreshed:
            return 0
        refresh_expires_at = self.token_last_refreshed + timedelta(days=14)
        delta = refresh_expires_at - timezone.now()
        return max(0, delta.days)

    def minutes_until_access_expires(self):
        if not self.token_expires_at:
            return 0
        delta = self.token_expires_at - timezone.now()
        return max(0, int(delta.total_seconds() / 60))