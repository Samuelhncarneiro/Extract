# apps/product_shopify/views.py
import json
import logging
import requests
import threading

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from web_project import TemplateLayout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.messages import get_messages

from .models import ShopifyProduct, ShopifyVariant, ShopifyImage
from .services import ShopifyService
from apps.shopify.models import Shopify

logger = logging.getLogger(__name__)

class ProductShopifyView(LoginRequiredMixin, TemplateView):
    template_name = "product_shopify.html"

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        selected_store = None
        if hasattr(self.request.user, 'profile'):
            selected_store = self.request.user.profile.selected_shopify_store
        
        if not selected_store:
            thread = threading.Thread(
                target=self._sync_and_update_cache,
                args=(selected_store,)
            )
            thread.daemon = True
            thread.start()
            store = Shopify.objects.filter(users=self.request.user, is_active=True).first()
            if store:
                try:
                    self.request.user.profile.selected_shopify_store = store
                    self.request.user.profile.save()
                    selected_store = store
                    logger.info(f"Loja Shopify selecionada automaticamente para usuário {self.request.user}: {store}")
                except Exception as e:
                    logger.exception(f"Erro ao atualizar perfil com loja Shopify: {str(e)}")
        
        context['page_title'] = 'Produtos Shopify'
        context['has_shopify'] = selected_store is not None
        
        if selected_store:
            # Sincronizar produtos imediatamente a cada carregamento de página
            success, message, count = self.sync_products_immediately(selected_store)
            
            # Atualizar contadores após a sincronização
            context['products_count'] = ShopifyProduct.objects.filter(store=selected_store).count()
            context['variants_count'] = ShopifyVariant.objects.filter(product__store=selected_store).count()
            context['selected_store'] = selected_store
            
            # Informar que os produtos foram sincronizados
            context['sync_message'] = message if success else f"Erro na sincronização: {message}"
            context['sync_success'] = success
        else:
            context['products_count'] = 0
            context['variants_count'] = 0
            context['no_access'] = True
        
        return context
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        
        if context.get('no_access', False):
            storage = get_messages(request)
            for message in storage:
                pass 
            
            messages.error(request, "Você não tem acesso a esta página. Você precisa ter uma loja Shopify selecionada em seu perfil.")
            return redirect('/dashboard/')
        
        return self.render_to_response(context)
    
    def sync_products_immediately(self, shop):
        try:
            shop_domain = shop.shop_domain
            if '.myshopify.com' in shop_domain:
                shop_name = shop_domain.split('.myshopify.com')[0]
            else:
                shop_name = shop_domain.split('.')[0]
            
            if not shop.access_token:
                logger.warning(f"Loja Shopify {shop_name} não tem token de acesso válido")
                return False, "Token de acesso inválido", 0
            
            success, message, count = ShopifyService.fetch_and_store_products(
                shop_name=shop_name,
                access_token=shop.access_token,
                force_update=False,
                store_obj=shop
            )
            
            if success:
                logger.info(f"Sincronização automática concluída para {shop_name}: {message}")
            else:
                logger.error(f"Erro na sincronização automática para {shop_name}: {message}")
            
            return success, message, count
                
        except Exception as e:
            logger.exception(f"Erro ao sincronizar produtos: {str(e)}")
            return False, str(e), 0

    def _sync_and_update_cache(self, shop):
        try:
            cache.set(f'shopify_sync_status_{shop.id}', {
                'success': success,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }, timeout=3600)
        except Exception as e:
            logger.exception(f"Erro na sincronização em background: {str(e)}")

@login_required
def get_products(request):
    """API para obter produtos da loja selecionada no perfil"""
    try:
        selected_store = None
        if hasattr(request.user, 'profile'):
            selected_store = request.user.profile.selected_shopify_store
        
        if not selected_store:
            return JsonResponse({
                'success': False,
                'message': 'Você não tem loja Shopify selecionada no seu perfil',
                'products': []
            })
        
        products = []
        product_objects = ShopifyProduct.objects.filter(store=selected_store).prefetch_related('variants', 'images').all()
        
        logger.info(f"Encontrados {product_objects.count()} produtos para loja {selected_store}")
        
        for product in product_objects:
            first_image = product.images.first()
            image_url = first_image.src if first_image else None
            
            first_variant = product.variants.first()
            
            product_data = {
                'shopify_id': product.shopify_id,
                'title': product.title,
                'handle': product.handle or '-',
                'image': image_url,
                'price': float(first_variant.price) if first_variant else 0,
                'status': product.status,
                'variants_count': product.variants.count(),
                'product_type': product.product_type or '-',
                'vendor': product.vendor or '-'
            }
            products.append(product_data)
        
        current_count = len(products)
        
        logger.info(f"Retornando {current_count} produtos via API")

        return JsonResponse({
            'products': products,
            'total_count': current_count,
            'success': True
        })
    except Exception as e:
        logger.exception(f"Erro ao obter produtos: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f"Erro ao obter produtos: {str(e)}",
            'products': []
        }, status=500)

@login_required
def get_product_details(request, product_id):
    """API endpoint para obter detalhes de um produto específico"""
    try:
        # Obter loja selecionada no perfil
        selected_store = None
        if hasattr(request.user, 'profile'):
            selected_store = request.user.profile.selected_shopify_store
        
        if not selected_store:
            return JsonResponse({
                'success': False,
                'message': 'Você não tem loja Shopify selecionada no seu perfil'
            })
        
        # Filtrar produto pela loja selecionada
        try:
            product = ShopifyProduct.objects.filter(store=selected_store, shopify_id=product_id).prefetch_related('variants', 'images').get()
        except ShopifyProduct.DoesNotExist:
            return JsonResponse({'error': 'Produto não encontrado ou você não tem permissão para acessá-lo', 'success': False}, status=404)
        
        # Formatar variantes
        variants = []
        for variant in product.variants.all():
            variant_data = {
                'variant_id': variant.variant_id,
                'title': variant.title,
                'price': float(variant.price),
                'sku': variant.sku or '-',
                'barcode': variant.barcode or '-',
                'inventory_quantity': variant.inventory_quantity,
                'option1': variant.option1,
                'option2': variant.option2,
                'option3': variant.option3
            }
            variants.append(variant_data)
        
        # Formatar imagens
        images = []
        for image in product.images.all():
            image_data = {
                'image_id': image.image_id,
                'position': image.position,
                'src': image.src,
                'alt': image.alt or ''
            }
            images.append(image_data)
        
        product_data = {
            'shopify_id': product.shopify_id,
            'title': product.title,
            'handle': product.handle,
            'body_html': product.body_html,
            'vendor': product.vendor,
            'product_type': product.product_type,
            'status': product.status,
            'tags': product.tags,
            'variants': variants,
            'images': images
        }
        
        return JsonResponse({'product': product_data, 'success': True})
    except Exception as e:
        logger.exception(f"Erro ao obter detalhes do produto: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500)

@login_required
def sync_products(request):
    """API endpoint para sincronizar produtos com o Shopify"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Obter loja selecionada no perfil
        selected_store = None
        if hasattr(request.user, 'profile'):
            selected_store = request.user.profile.selected_shopify_store
        
        if not selected_store:
            return JsonResponse({
                'success': False, 
                'message': 'Você não tem loja Shopify selecionada no seu perfil'
            }, status=400)
        
        # Extrair nome da loja a partir do domínio
        shop_domain = selected_store.shop_domain
        if '.myshopify.com' in shop_domain:
            shop_name = shop_domain.split('.myshopify.com')[0]
        else:
            shop_name = shop_domain.split('.')[0]
        
        access_token = selected_store.access_token
        
        force_update = json.loads(request.body).get('force_update', False) if request.body else False
        
        success, message, count = ShopifyService.fetch_and_store_products(
            shop_name,
            access_token,
            force_update=force_update
        )
        
        if success:
            return JsonResponse({
                'success': True, 
                'message': message,
                'count': count
            })
        else:
            return JsonResponse({
                'success': False, 
                'message': message
            }, status=400)
            
    except Exception as e:
        logger.exception(f"Erro ao sincronizar produtos: {str(e)}")
        return JsonResponse({
            'success': False, 
            'message': f"Erro ao sincronizar produtos: {str(e)}"
        }, status=500)

@login_required
def delete_product(request, product_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Obter loja selecionada no perfil
        selected_store = None
        if hasattr(request.user, 'profile'):
            selected_store = request.user.profile.selected_shopify_store
        
        if not selected_store:
            return JsonResponse({
                'success': False, 
                'message': 'Você não tem loja Shopify selecionada no seu perfil'
            }, status=400)
        
        shop_domain = selected_store.shop_domain
        if '.myshopify.com' in shop_domain:
            shop_name = shop_domain.split('.myshopify.com')[0]
        else:
            shop_name = shop_domain.split('.')[0]
        
        access_token = selected_store.access_token
        
        api_url = ShopifyService.get_api_url(shop_name)
        headers = ShopifyService.get_headers(access_token)
        
        url = f"{api_url}/products/{product_id}.json"
        
        response = requests.delete(url, headers=headers)
        
        if response.status_code not in [200, 204]:
            logger.error(f"Erro ao excluir produto: HTTP {response.status_code} - {response.text}")
            return JsonResponse({
                'success': False, 
                'message': f"Erro ao excluir produto: {response.status_code}"
            }, status=400)
        
        # Excluir o produto do banco de dados local (apenas se for da loja selecionada)
        try:
            product = ShopifyProduct.objects.filter(store=selected_store, shopify_id=product_id).get()
            product.delete()
            logger.info(f"Produto {product_id} excluído com sucesso")
        except ShopifyProduct.DoesNotExist:
            logger.warning(f"Produto {product_id} não encontrado na base local ou não pertence à loja selecionada")
        
        return JsonResponse({
            'success': True, 
            'message': "Produto excluído com sucesso"
        })
            
    except Exception as e:
        logger.exception(f"Erro ao excluir produto: {str(e)}")
        return JsonResponse({
            'success': False, 
            'message': f"Erro ao excluir produto: {str(e)}"
        }, status=500)