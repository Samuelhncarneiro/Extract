from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.sechic.models import Category, Supplier, Brand, Color, Size
from .cache_manager import AitigosCacheManager
import logging

logger = logging.getLogger(__name__)

@receiver([post_save, post_delete], sender=Category)
def invalidate_categories_cache_aitigos(sender, instance, **kwargs):
    AitigosCacheManager.invalidate_dropdown_cache(instance.company.id, 'categories')
    AitigosCacheManager.invalidate_company_config(instance.company.id)

@receiver([post_save, post_delete], sender=Supplier)
def invalidate_suppliers_cache_aitigos(sender, instance, **kwargs):
    AitigosCacheManager.invalidate_dropdown_cache(instance.company.id, 'suppliers')
    AitigosCacheManager.invalidate_company_config(instance.company.id)

@receiver([post_save, post_delete], sender=Brand)
def invalidate_brands_cache_aitigos(sender, instance, **kwargs):
    AitigosCacheManager.invalidate_dropdown_cache(instance.company.id, 'brands')

@receiver([post_save, post_delete], sender=Color)
def invalidate_colors_cache_aitigos(sender, instance, **kwargs):
    AitigosCacheManager.invalidate_dropdown_cache(instance.company.id, 'colors')

@receiver([post_save, post_delete], sender=Size)
def invalidate_sizes_cache_aitigos(sender, instance, **kwargs):
    AitigosCacheManager.invalidate_dropdown_cache(instance.company.id, 'sizes')
