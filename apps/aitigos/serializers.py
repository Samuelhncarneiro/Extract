# apps/aitigos/serializers.py
from rest_framework import serializers
import logging

logger = logging.getLogger(__name__)

class SizeSerializer(serializers.Serializer):
    size = serializers.CharField(default='')
    quantity = serializers.IntegerField(default=0)

class ColorSerializer(serializers.Serializer):
    color_code = serializers.CharField(default='')
    color_name = serializers.CharField(default='', allow_blank=True,allow_null=True)
    sizes = SizeSerializer(many=True, default=list)
    unit_price = serializers.FloatField(default=0)
    sales_price = serializers.FloatField(allow_null=True, default=None)
    subtotal = serializers.FloatField(allow_null=True, default=None)

class ReferenceSerializer(serializers.Serializer):
    reference = serializers.CharField(default='')
    counter = serializers.IntegerField(default=0)
    color_code = serializers.CharField(default='')
    color_name = serializers.CharField(default='', allow_null=True)
    size = serializers.CharField(default='')
    quantity = serializers.IntegerField(default=0)
    barcode = serializers.CharField(default='')

class ProductSerializer(serializers.Serializer):
    name = serializers.CharField(default='')
    material_code = serializers.CharField(default='')
    category = serializers.CharField(default='')
    model = serializers.CharField(allow_null=True,allow_blank=True, default='')
    composition = serializers.CharField(allow_null=True, allow_blank=True, default='')
    colors = ColorSerializer(many=True, default=list)
    total_price = serializers.FloatField(allow_null=True, default=None)
    brand = serializers.CharField(allow_null=True, default='')
    supplier = serializers.CharField(allow_null=True, allow_blank=True, default='')
    gender = serializers.CharField(allow_null=True, allow_blank=True, default='')
    details = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    references = ReferenceSerializer(many=True, required=False, default=list)

class OrderInfoSerializer(serializers.Serializer):
    supplier = serializers.CharField(allow_null=True, default='')
    document_type = serializers.CharField(allow_null=True, default='')
    order_number = serializers.CharField(allow_null=True, default='')
    date = serializers.CharField(allow_null=True, default='')
    customer = serializers.CharField(allow_null=True, default='')
    brand = serializers.CharField(allow_null=True, default='')
    season = serializers.CharField(allow_null=True, default='')
    total_pieces = serializers.IntegerField(allow_null=True, default=None)
    total_value = serializers.FloatField(allow_null=True, default=None)

class ExtractionResultSerializer(serializers.Serializer):
    products = ProductSerializer(many=True, required=False, default=list)
    order_info = OrderInfoSerializer(required=False, default=dict)
    _metadata = serializers.DictField(required=False, default=dict)
    
    def to_internal_value(self, data):
        try:
            for product in data.get('products', []):
                supplier = product.get('supplier', '')
                for color in product.get('colors', []):
                    if 'supplier' not in color or not color['supplier']:
                        color['supplier'] = supplier

            return super().to_internal_value(data)
        except Exception as e:
            logger.warning(f"Erro na validação: {str(e)}")
            result = {}
            
            result['products'] = data.get('products', [])
            result['order_info'] = data.get('order_info', {})
            
            return result