# apps/product_moloni/models.py

from django.db import models
from apps.sechic.models import Category, Supplier
from apps.moloni.models import Moloni

class Product(models.Model):
    product_id = models.IntegerField(primary_key=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    ean = models.CharField(max_length=30, blank=True, null=True)
    name = models.CharField(max_length=255)
    summary = models.TextField(blank=True, null=True)
    type = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_id = models.IntegerField(blank=True, null=True)
    has_stock = models.BooleanField(default=False)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    company = models.ForeignKey(Moloni, on_delete=models.CASCADE, null=True, blank=True) 
    
    def __str__(self):
        return f"{self.name} ({self.reference})"
    
    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['name']

class ProductVariant(models.Model):
    variant_id = models.IntegerField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    reference = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.name} - {self.reference}"
    
    class Meta:
        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"