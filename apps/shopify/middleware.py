# apps/shopify/middleware.py
from .models import Shopify

class ShopifyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and 'selected_shopify_domain' not in request.session:
            try:
                # Usar relacionamento many-to-many
                shopify_store = request.user.shopify_stores.latest('created_at')
                if shopify_store:
                    request.session['selected_shopify_domain'] = shopify_store.shop_domain
                    request.session['selected_shopify_name'] = getattr(shopify_store, 'name', shopify_store.shop_domain)
                    request.session['selected_shopify_email'] = shopify_store.email
            except Shopify.DoesNotExist:
                pass

        response = self.get_response(request)
        return response