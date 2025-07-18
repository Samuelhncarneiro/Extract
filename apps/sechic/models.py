#apps/sechic/models.py
from django.db import models
from apps.moloni.models import Moloni
from apps.shopify.models import Shopify

class Color(models.Model):
    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=50)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='colors')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='colors', null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        verbose_name = "Color"
        verbose_name_plural = "Colors"
        ordering = ['code']

class Size(models.Model):
    value = models.CharField(max_length=10)
    code = models.CharField(max_length=3, primary_key=True)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='sizes')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='sizes', null=True, blank=True)

    def __str__(self):
        return f"{self.value} ({self.code})"
    
    class Meta:
        verbose_name = "Size"
        verbose_name_plural = "Sizes"
        ordering = ['code']

class Category(models.Model):
    name = models.CharField(max_length=50)
    category_id = models.IntegerField(primary_key=True)
    parent_id = models.IntegerField(null=True, blank=True)
    num_categories = models.IntegerField(default=0)
    num_products = models.IntegerField(default=0)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='categories')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='categories', null=True, blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

class Brand(models.Model):
    name = models.CharField(max_length=100, primary_key=True)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='brands')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='brands', null=True, blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"
        ordering = ['name']

class Supplier(models.Model):
    supplier_id = models.IntegerField(primary_key=True)
    code = models.CharField(max_length=2)
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='suppliers')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='suppliers', null=True, blank=True)

    @property
    def current_markup(self):
        active_markup = self.markups.filter(is_active=True).first()
        if active_markup:
            return active_markup.markup
        
        latest_markup = self.markups.first()
        return latest_markup.markup if latest_markup else None
    
    @property
    def active_markup_obj(self):
        active_markup = self.markups.filter(is_active=True).first()
        if active_markup:
            return active_markup
        return self.markups.first()

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering = ['code']
        
class SupplierMarkup(models.Model):
    """Model to store supplier markup history with dates"""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='markups')
    markup = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        status = " (ATIVO)" if self.is_active else ""
        return f"{self.supplier.name} - {self.markup} ({self.created_at.strftime('%d/%m/%Y %H:%M')}){status}"
    
    def save(self, *args, **kwargs):
        if self.is_active:
            SupplierMarkup.objects.filter(
                supplier=self.supplier
            ).exclude(
                pk=self.pk if self.pk else None
            ).update(is_active=False)
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Supplier Markup"
        verbose_name_plural = "Supplier Markups"
        ordering = ['-created_at']
        
class Tax(models.Model):
    tax_id = models.CharField(max_length=10)
    name = models.CharField(max_length=15)
    value = models.CharField(max_length=10)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='taxes')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='taxes', null=True, blank=True)

    class Meta:
        verbose_name = 'Tax'
        verbose_name_plural = 'Taxes'

    def __str__(self):
        return self.name

class Unit(models.Model):
    unit_id = models.CharField(max_length=10)
    name = models.CharField(max_length=15)
    short_name = models.CharField(max_length=6)
    company = models.ForeignKey(Moloni,  on_delete=models.CASCADE, related_name='units')
    store = models.ForeignKey(Shopify,  on_delete=models.CASCADE, related_name='units', null=True, blank=True)

    class Meta:
        verbose_name = 'unit'
        verbose_name_plural = 'units'

    def __str__(self):
        return self.name