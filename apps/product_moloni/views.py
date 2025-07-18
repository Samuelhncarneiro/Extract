# apps/product_moloni/views.py
import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from web_project import TemplateLayout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Q
from django.views.decorators.http import require_http_methods

from .models import Product, ProductVariant
from .services import ProductMoloniService, BackgroundSyncService
from apps.moloni.models import Moloni

logger = logging.getLogger(__name__)

class ProductMoloniView(LoginRequiredMixin, TemplateView):
    template_name = "product_moloni.html"

    # apps/product_moloni/views.py - ATUALIZAR A VIEW PRINCIPAL

import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from web_project import TemplateLayout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta

from .models import Product, ProductVariant
from .services import ProductMoloniService, BackgroundSyncService
from apps.moloni.models import Moloni

logger = logging.getLogger(__name__)

class ProductMoloniView(LoginRequiredMixin, TemplateView):
    template_name = "product_moloni.html"

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        user_profile = self.request.user.profile
        selected_company = user_profile.selected_moloni_company
        
        if not selected_company:
            messages.error(self.request, "Você não tem uma empresa Moloni selecionada no seu perfil.")
            context['no_access'] = True
            return context
            
        products_count = cache.get(f'products_count_{selected_company.id}')
        if products_count is None:
            products_count = Product.objects.filter(company=selected_company).count()
            cache.set(f'products_count_{selected_company.id}', products_count, timeout=300) 
        
        should_auto_sync = self.should_start_auto_sync(selected_company)
        
        context['page_title'] = 'Produtos Moloni'
        context['products_count'] = products_count
        context['variants_count'] = ProductVariant.objects.count()
        context['selected_company'] = selected_company
        context['auto_sync'] = should_auto_sync
        
        return context
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        
        if context.get('no_access', False):
            return redirect('/dashboard/') 
        
        if context.get('auto_sync', False):
            selected_company = request.user.profile.selected_moloni_company
            self.start_auto_background_sync(selected_company, request.user.id)
        
        return self.render_to_response(context)
    
    def should_start_auto_sync(self, company):
        """Determina se deve iniciar sincronização automática"""
        try:
            # Verificar se já existe uma sincronização em andamento
            sync_progress = BackgroundSyncService.get_sync_progress(company.id)
            if sync_progress and sync_progress.get('status') in ['started', 'processing']:
                logger.info(f"Sincronização já em andamento para empresa {company.name}")
                return False
            
            # Verificar quando foi a última sincronização
            last_sync_key = f'last_auto_sync_{company.id}'
            last_sync_time = cache.get(last_sync_key)
            
            if last_sync_time:
                # Se a última sync foi há menos de 10 minutos, não sincronizar novamente
                if isinstance(last_sync_time, str):
                    last_sync_time = timezone.datetime.fromisoformat(last_sync_time.replace('Z', '+00:00'))
                
                time_since_sync = timezone.now() - last_sync_time
                if time_since_sync < timedelta(minutes=10):
                    logger.info(f"Última sincronização foi há {time_since_sync}. Pulando sync automático.")
                    return False
            
            # Verificar se há produtos locais
            local_products_count = Product.objects.filter(company=company).count()
            
            # Sempre sincronizar se:
            # 1. Não há produtos locais (primeira vez)
            # 2. Não houve sincronização nas últimas 10 minutos
            if local_products_count == 0:
                logger.info(f"Nenhum produto local encontrado. Iniciando sync automático para {company.name}")
                return True
            elif not last_sync_time:
                logger.info(f"Nenhuma sincronização anterior registrada. Iniciando sync automático para {company.name}")
                return True
            else:
                logger.info(f"Iniciando sync automático periódico para {company.name}")
                return True
                
        except Exception as e:
            logger.exception(f"Erro ao verificar necessidade de sync automático: {str(e)}")
            return False
    
    def start_auto_background_sync(self, company, user_id):
        """Inicia sincronização automática em background"""
        try:
            success, message = BackgroundSyncService.start_sync(
                company, 
                force_delete=True,
                user_id=user_id
            )
            
            if success:
                logger.info(f"Sincronização automática iniciada para {company.name}: {message}")
                last_sync_key = f'last_auto_sync_{company.id}'
                cache.set(last_sync_key, timezone.now().isoformat(), timeout=86400)
            else:
                logger.warning(f"Falha ao iniciar sincronização automática para {company.name}: {message}")
                
        except Exception as e:
            logger.exception(f"Erro ao iniciar sincronização automática: {str(e)}")

@login_required
def quick_sync_status(request):
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False,
                'message': 'Empresa não selecionada'
            })
        
        last_sync_key = f'last_sync_company_{selected_company.id}'
        last_sync = cache.get(last_sync_key)
        
        local_count = Product.objects.filter(company=selected_company).count()
        
        return JsonResponse({
            'success': True,
            'needs_sync': not last_sync,
            'local_products': local_count,
            'last_sync': bool(last_sync)
        })
        
    except Exception as e:
        logger.exception(f"Erro ao verificar status de sincronização: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def get_products(request):
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False,
                'message': 'Você não tem empresa Moloni selecionada no seu perfil',
                'products': []
            })
        
        query = Product.objects.filter(company=selected_company)
        company_total = query.count()
        
        search_term = request.GET.get('search', '')
        
        if search_term:
            query = query.filter(
                Q(name__icontains=search_term) | 
                Q(reference__icontains=search_term) |
                Q(ean__icontains=search_term)
            )
        
        filtered_total = query.count()
        page = int(request.GET.get('page', 1))
        
        limit = request.GET.get('limit')
        if limit:
            limit = int(limit)
            if limit <= 0:
                limit = company_total
        else:
            limit = company_total
        
        if company_total == 0:
            limit = 100
        
        offset = (page - 1) * limit
        products = query.order_by('-updated_at')[offset:offset+limit]

        product_data = []
        for product in products:
            product_data.append({
                'product_id': product.product_id,
                'reference': product.reference,
                'name': product.name,
                'ean': product.ean,
                'category': product.category.name if product.category else '',
                'supplier': product.supplier.name if product.supplier else '',
                'price': str(product.price),
                'created_at': product.created_at.isoformat() if product.created_at else '',
                'company_id': product.company.company_id if product.company else None,
                'company_name': product.company.name if product.company else '',
            })
        
        return JsonResponse({
            'success': True,
            'products': product_data,
            'total': filtered_total,
            'company_total': company_total, 
            'page': page,
            'limit': limit,
            'pages': max(1, (filtered_total + limit - 1) // limit),
            'showing': len(product_data),
            'is_filtered': bool(search_term) 
        })
    
    except Exception as e:
        logger.exception(f"Erro ao obter produtos: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao obter produtos: {str(e)}',
            'products': []
        })

@login_required
def get_product_details(request, product_id):
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False,
                'message': 'Você não tem empresa Moloni selecionada no seu perfil'
            })
        
        try:
            product = Product.objects.get(product_id=product_id, company=selected_company)
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Produto não encontrado ou você não tem permissão para acessá-lo'
            })
        
        product_data = {
            'product_id': product.product_id,
            'reference': product.reference,
            'name': product.name,
            'ean': product.ean,
            'summary': product.summary,
            'type': product.type,
            'price': str(product.price),
            'unit_id': product.unit_id,
            'has_stock': product.has_stock,
            'stock': str(product.stock),
            'category': product.category.name if product.category else '',
            'supplier': product.supplier.name if product.supplier else '',
            'created_at': product.created_at.isoformat() if product.created_at else '',
            'updated_at': product.updated_at.isoformat() if product.updated_at else '',
            'company': product.company.name if product.company else '',
        }
        
        variants = []
        for variant in product.variants.all():
            variants.append({
                'variant_id': variant.variant_id,
                'reference': variant.reference,
                'name': variant.name,
                'price': str(variant.price),
                'stock': str(variant.stock)
            })
        
        return JsonResponse({
            'success': True,
            'product': product_data,
            'variants': variants
        })
    
    except Exception as e:
        logger.exception(f"Erro ao obter detalhes do produto {product_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao obter detalhes do produto: {str(e)}'
        })

@login_required
@require_http_methods(["POST"])
def start_background_sync(request):
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False,
                'message': 'Você não tem empresa Moloni selecionada no seu perfil'
            })
        
        data = json.loads(request.body) if request.body else {}
        force_delete = data.get('force_delete', False)
        
        success, message = BackgroundSyncService.start_sync(
            selected_company, 
            force_delete=force_delete,
            user_id=request.user.id
        )
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.exception(f"Erro ao iniciar sincronização em background: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao iniciar sincronização: {str(e)}'
        })

@login_required
def get_sync_progress(request):
    """Retorna o progresso da sincronização em background"""
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False, 
                'message': 'Empresa não selecionada'
            })
        
        progress = BackgroundSyncService.get_sync_progress(selected_company.id)
        
        if not progress:
            return JsonResponse({
                'success': True,
                'progress': None,
                'message': 'Nenhuma sincronização em andamento'
            })
        
        return JsonResponse({
            'success': True,
            'progress': progress
        })
        
    except Exception as e:
        logger.exception(f"Erro ao obter progresso da sincronização: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao obter progresso: {str(e)}'
        })

@login_required
@require_http_methods(["POST"])
def cancel_background_sync(request):
    """Cancela a sincronização em background"""
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False, 
                'message': 'Empresa não selecionada'
            })
        
        success = BackgroundSyncService.cancel_sync(selected_company.id)
        
        return JsonResponse({
            'success': success,
            'message': 'Sincronização cancelada com sucesso' if success else 'Nenhuma sincronização em andamento para cancelar'
        })
        
    except Exception as e:
        logger.exception(f"Erro ao cancelar sincronização: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao cancelar sincronização: {str(e)}'
        })

@login_required
def sync_status_page(request):
    """Página para acompanhar o status da sincronização"""
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            messages.error(request, "Você não tem uma empresa Moloni selecionada no seu perfil.")
            return redirect('/dashboard/')
        
        context = TemplateLayout.init(request, {})
        context.update({
            'page_title': 'Status da Sincronização',
            'selected_company': selected_company,
        })
        
        return render(request, 'product_moloni_sync_status.html', context)
        
    except Exception as e:
        logger.exception(f"Erro na página de status: {str(e)}")
        messages.error(request, f"Erro ao carregar página: {str(e)}")
        return redirect('/dashboard/')


@login_required
@require_http_methods(["POST"])
def sync_products(request):
    """Sincronização de produtos - agora com opção background"""
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False,
                'message': 'Você não tem empresa Moloni selecionada no seu perfil'
            })
        
        data = json.loads(request.body) if request.body else {}
        force_delete = data.get('force_delete', False)
        use_background = data.get('background', True)
        
        if use_background:
            success, message = BackgroundSyncService.start_sync(
                selected_company,
                force_delete=force_delete,
                user_id=request.user.id
            )
            
            response_data = {
                'success': success,
                'message': message,
                'background': True
            }
        else:
            success, message, stats = ProductMoloniService.fetch_and_store_products(
                selected_company,
                force_delete=force_delete
            )
            
            response_data = {
                'success': success,
                'message': message,
                'stats': stats,
                'background': False
            }
        
        # Limpar cache
        cache.delete('products_count')
        cache.delete(f'last_sync_company_{selected_company.id}')
        
        return JsonResponse(response_data)
    
    except Exception as e:
        logger.exception(f"Erro na sincronização: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao sincronizar produtos: {str(e)}'
        })

@login_required
def check_auto_sync_status(request):
    """Verifica se deve iniciar sync automático (para chamadas AJAX)"""
    try:
        selected_company = request.user.profile.selected_moloni_company
        
        if not selected_company:
            return JsonResponse({
                'success': False,
                'message': 'Empresa não selecionada'
            })
        
        sync_progress = BackgroundSyncService.get_sync_progress(selected_company.id)
        
        if sync_progress and sync_progress.get('status') in ['started', 'processing']:
            return JsonResponse({
                'success': True,
                'sync_in_progress': True,
                'progress': sync_progress,
                'message': 'Sincronização já em andamento'
            })
        
        last_sync_key = f'last_auto_sync_{selected_company.id}'
        last_sync_time = cache.get(last_sync_key)
        
        should_start = False
        reason = ""
        
        local_products_count = Product.objects.filter(company=selected_company).count()
        
        if local_products_count == 0:
            should_start = True
            reason = "Nenhum produto local encontrado"
        elif not last_sync_time:
            should_start = True
            reason = "Primeira sincronização"
        elif last_sync_time:
            if isinstance(last_sync_time, str):
                last_sync_time = timezone.datetime.fromisoformat(last_sync_time.replace('Z', '+00:00'))
            
            time_since_sync = timezone.now() - last_sync_time
            if time_since_sync > timedelta(minutes=10):
                should_start = True
                reason = f"Última sincronização há {time_since_sync}"
        
        if should_start:
            success, message = BackgroundSyncService.start_sync(
                selected_company,
                force_delete=True,
                user_id=request.user.id
            )
            
            if success:
                cache.set(last_sync_key, timezone.now().isoformat(), timeout=86400)
                return JsonResponse({
                    'success': True,
                    'sync_started': True,
                    'message': f'Sincronização automática iniciada: {reason}',
                    'reason': reason
                })
            else:
                return JsonResponse({
                    'success': False,
                    'sync_started': False,
                    'message': f'Erro ao iniciar sincronização: {message}'
                })
        else:
            return JsonResponse({
                'success': True,
                'sync_started': False,
                'message': 'Sincronização não necessária no momento',
                'local_products': local_products_count
            })
        
    except Exception as e:
        logger.exception(f"Erro ao verificar status de sync automático: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao verificar status: {str(e)}'
        })
