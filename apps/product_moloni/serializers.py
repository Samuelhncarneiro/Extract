# apps/product_moloni/serializers.py
from rest_framework import serializers

class ProductVariantSerializer(serializers.Serializer):
    """Serializer para variantes de produto (detalhes)"""
    reference = serializers.CharField(required=False, allow_blank=True)
    color_code = serializers.CharField(required=False, allow_blank=True)
    color_name = serializers.CharField(required=False, allow_blank=True)
    size = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.FloatField(required=False, default=0)
    unit_price = serializers.FloatField(required=False, default=0)
    sales_price = serializers.FloatField(required=False, default=0)
    barcode = serializers.CharField(required=False, allow_blank=True)

class ProductSerializer(serializers.Serializer):
    """Serializer para produtos completos"""
    material_code = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=True)
    composition = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.CharField(required=False, allow_blank=True, default="Homem")
    brand = serializers.CharField(required=False, allow_blank=True)
    supplier = serializers.CharField(required=False, allow_blank=True)
    date = serializers.CharField(required=False, allow_blank=True)
    integrated = serializers.CharField(required=False, allow_blank=True, default="0")
    details = ProductVariantSerializer(many=True, required=False)

class ExtractionColorSerializer(serializers.Serializer):
    """Serializer para cores nos resultados de extração"""
    color_code = serializers.CharField(required=False, allow_blank=True)
    color_name = serializers.CharField(required=False, allow_blank=True)
    sizes = serializers.ListField(required=False, default=list)
    unit_price = serializers.FloatField(required=False, default=0)
    sales_price = serializers.FloatField(required=False, default=0)
    subtotal = serializers.FloatField(required=False, default=0)

class ExtractionProductSerializer(serializers.Serializer):
    """Serializer para produtos nos resultados de extração"""
    name = serializers.CharField(required=False, allow_blank=True)
    material_code = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    model = serializers.CharField(required=False, allow_blank=True)
    composition = serializers.CharField(required=False, allow_blank=True)
    colors = ExtractionColorSerializer(many=True, required=False)
    total_price = serializers.FloatField(required=False)

class OrderInfoSerializer(serializers.Serializer):
    """Serializer para informações do pedido"""
    order_number = serializers.CharField(required=False, allow_blank=True)
    date = serializers.CharField(required=False, allow_blank=True)
    total_pieces = serializers.IntegerField(required=False)
    total_value = serializers.FloatField(required=False)
    supplier = serializers.CharField(required=False, allow_blank=True)
    brand = serializers.CharField(required=False, allow_blank=True)
    document_type = serializers.CharField(required=False, allow_blank=True)
    customer = serializers.CharField(required=False, allow_blank=True)
    season = serializers.CharField(required=False, allow_blank=True)

class ExtractionResultSerializer(serializers.Serializer):
    """Serializer para o resultado completo da extração"""
    products = ExtractionProductSerializer(many=True, required=False, default=list)
    order_info = OrderInfoSerializer(required=False, default=dict)