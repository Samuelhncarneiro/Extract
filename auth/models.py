#auth/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    email = models.EmailField(max_length=100, unique=True)
    email_token = models.CharField(max_length=100, blank=True, null=True)
    forget_password_token = models.CharField(max_length=100, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    selected_moloni_company = models.ForeignKey(
        'moloni.Moloni',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='selected_by_profiles'
    )
    selected_shopify_store = models.ForeignKey(
        'shopify.Shopify',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='selected_by_profiles'
    )

    def __str__(self):
        return self.user.username

    @receiver(post_save, sender=User)
    def create_profile(sender, instance, created, **kwargs):
        if created:
            Profile.objects.create(user=instance, email=instance.email)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
