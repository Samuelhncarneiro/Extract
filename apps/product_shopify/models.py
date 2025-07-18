# apps/product_shopify/models.py

from django.db import models
from apps.sechic.models import Category, Supplier

class ShopifyProduct(models.Model):
    """Model to store products from Shopify"""
    shopify_id = models.BigIntegerField(primary_key=True)
    title = models.CharField(max_length=255)
    handle = models.CharField(max_length=255, blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    vendor = models.CharField(max_length=255, blank=True, null=True)
    product_type = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=50, default='active')
    published_at = models.DateTimeField(blank=True, null=True)
    tags = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    store = models.ForeignKey('shopify.Shopify', on_delete=models.CASCADE, related_name='products')
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "Shopify Product"
        verbose_name_plural = "Shopify Products"
        ordering = ['title']

class ShopifyVariant(models.Model):
    """Model to store product variants from Shopify"""
    variant_id = models.BigIntegerField(primary_key=True)
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='variants')
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sku = models.CharField(max_length=255, blank=True, null=True)
    barcode = models.CharField(max_length=255, blank=True, null=True)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    position = models.IntegerField(default=1)
    option1 = models.CharField(max_length=255, blank=True, null=True)
    option2 = models.CharField(max_length=255, blank=True, null=True)
    option3 = models.CharField(max_length=255, blank=True, null=True)
    inventory_quantity = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.product.title} - {self.title}"
    
    class Meta:
        verbose_name = "Shopify Variant"
        verbose_name_plural = "Shopify Variants"

class ShopifyImage(models.Model):
    """Model to store product images from Shopify"""
    image_id = models.BigIntegerField(primary_key=True)
    product = models.ForeignKey(ShopifyProduct, on_delete=models.CASCADE, related_name='images')
    position = models.IntegerField(default=1)
    src = models.URLField(max_length=2000)
    alt = models.CharField(max_length=255, blank=True, null=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Image {self.position} for {self.product.title}"
    
    class Meta:
        verbose_name = "Shopify Image"
        verbose_name_plural = "Shopify Images"
        ordering = ['product', 'position']