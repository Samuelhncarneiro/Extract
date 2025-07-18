#apps/sechic/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from web_project import TemplateLayout
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_page
from django.core.cache import cache
from django.conf import settings

import json
import logging
import threading

from .models import Color, Size, Category, Brand, Supplier, SupplierMarkup
from auth.models import Profile
from .services import MoloniService
from .cache_manager import SechicCacheManager

logger = logging.getLogger(__name__)

def get_user_company(user):
    try:
        profile = user.profile
        return profile.selected_moloni_company
    except Profile.DoesNotExist:
        return None

class SechicView(LoginRequiredMixin, TemplateView):
    template_name = "sechic.html"

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        try:
            profile = self.request.user.profile
            selected_company = profile.selected_moloni_company

            if selected_company:
                cached_counts = SechicCacheManager.get_cached_counts(selected_company.id)
                
                if cached_counts:
                    logger.info(f"📦 Contadores do cache para empresa {selected_company.name}")
                    context.update(cached_counts)
                else:
                    logger.info(f"🔄 Calculando contadores para empresa {selected_company.name}")
                    counts = {
                        'colors_count': Color.objects.filter(company=selected_company).count(),
                        'sizes_count': Size.objects.filter(company=selected_company).count(),
                        'suppliers_count': Supplier.objects.filter(company=selected_company).count(),
                        'categories_count': Category.objects.filter(company=selected_company).count(),
                        'brands_count': Brand.objects.filter(company=selected_company).count()
                    }
                    context.update(counts)
                    
                    SechicCacheManager.cache_counts(selected_company.id, counts)
                
                self.trigger_smart_background_sync(selected_company)
                    
            else:
                context.update({
                    'colors_count': 0, 'sizes_count': 0, 'suppliers_count': 0,
                    'categories_count': 0, 'brands_count': 0
                })
                
        except Profile.DoesNotExist:
            context.update({
                'colors_count': 0, 'sizes_count': 0, 'suppliers_count': 0,
                'categories_count': 0, 'brands_count': 0
            })

        context['page_title'] = 'Definições'
        return context

    def trigger_smart_background_sync(self, company):
        def background_sync():
            try:
                logger.info(f"🤖 Verificando sincronização para {company.name}")
                
                success, message, count = MoloniService.sync_categories_with_moloni(
                    company, force_sync=False
                )
                
                if success and count > 0:
                    SechicCacheManager.invalidate_after_data_change(company.id, 'categories')
                else:
                    logger.info(f"Verificação background: {message}")
                    
            except Exception as e:
                logger.error(f"Erro na sincronização background: {str(e)}")
        
        sync_thread = threading.Thread(target=background_sync, daemon=True)
        sync_thread.start()

@login_required
@never_cache
def get_colors(request):
    company = get_user_company(request.user)
    if not company:
        return JsonResponse({'colors': []})
    
    cached_colors = SechicCacheManager.get_cached_colors(company.id)
    
    if cached_colors:
        return JsonResponse({'colors': cached_colors})
    
    colors = list(Color.objects.filter(company=company).values('code', 'name'))
    SechicCacheManager.cache_colors(company.id, colors)

    return JsonResponse({'colors': colors})

@login_required
@never_cache
def get_sizes(request):
    company = get_user_company(request.user)
    if not company:
        return JsonResponse({'sizes': []})
    
    cached_sizes = SechicCacheManager.get_cached_sizes(company.id)
    
    if cached_sizes:
        return JsonResponse({'sizes': cached_sizes})
        
    sizes = list(Size.objects.filter(company=company).values('code', 'value'))
    SechicCacheManager.cache_sizes(company.id, sizes)

    return JsonResponse({'sizes': sizes})

@login_required
@never_cache
def get_categories(request):
    company = get_user_company(request.user)
    if not company:
        return JsonResponse({'categories': []})
    
    cached_categories = SechicCacheManager.get_cached_categories(company.id)
    
    if cached_categories:
        return JsonResponse({'categories': cached_categories})
    
    try:
        success, message, operations_count = MoloniService.sync_categories_with_moloni(company)
        
        if not success:
            logger.warning(f"Sincronização falhou para empresa {company.name}: {message}")
        elif operations_count > 0:
            logger.info(f"Sincronização concluída para empresa {company.name}: {message}")
            
    except Exception as e:
        logger.error(f"Erro na sincronização de categorias: {str(e)}")
    
    categories = list(Category.objects.filter(company=company).values('category_id', 'name', 'num_categories', 'num_products'))
    
    SechicCacheManager.cache_categories(company.id, categories)
    
    return JsonResponse({'categories': categories})

@login_required
@never_cache
def get_brands(request):
    company = get_user_company(request.user)
    if not company:
        return JsonResponse({'brands': []})
    
    cached_brands = SechicCacheManager.get_cached_brands(company.id)
    
    if cached_brands:
        return JsonResponse({'brands': cached_brands})
        
    brands = list(Brand.objects.filter(company=company).values('name'))
    SechicCacheManager.cache_brands(company.id, brands)
    
    return JsonResponse({'brands': brands})

@login_required
@never_cache
def get_suppliers(request):
    company = get_user_company(request.user)
    if not company:
        return JsonResponse({'suppliers': []})
    
    cached_suppliers = SechicCacheManager.get_cached_suppliers(company.id)
    
    if cached_suppliers:
        return JsonResponse({'suppliers': cached_suppliers})
    
    suppliers_data = []
    suppliers = Supplier.objects.filter(company=company).prefetch_related('markups')
    
    for supplier in suppliers:
        markup_count = supplier.markups.count()
        
        # MUDANÇA: Sempre buscar pelo is_active=True primeiro
        active_markup = supplier.markups.filter(is_active=True).first()
        
        # Se não há markup ativo, pegar o mais recente
        if not active_markup:
            active_markup = supplier.markups.order_by('-created_at').first()
            # Se encontrou um markup mas não está ativo, ativá-lo
            if active_markup:
                active_markup.is_active = True
                active_markup.save()
        
        suppliers_data.append({
            'code': supplier.code,
            'name': supplier.name,
            'current_markup': active_markup.markup if active_markup else None,
            'markup_count': markup_count
        })
    
    SechicCacheManager.cache_suppliers(company.id, suppliers_data)
    
    return JsonResponse({'suppliers': suppliers_data})


def invalidate_cache_for_company(company_id, data_type=None):
    if data_type:
        SechicCacheManager.invalidate_after_data_change(company_id, data_type)
    else:
        SechicCacheManager.invalidate_after_data_change(company_id)
        
class ColorCreateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            code = data.get('code')
            name = data.get('name')

            if not code or not name:
                return JsonResponse({'error': 'Código e nome são obrigatórios'}, status=400)

            if Color.objects.filter(code=code, company=company).exists():
                return JsonResponse({'error': 'Já existe uma cor com este código nesta empresa'}, status=400)

            color = Color.objects.create(code=code, name=name, company=company)

            SechicCacheManager.invalidate_after_data_change(company.id, 'colors')

            return JsonResponse({
                'code': color.code,
                'name': color.name,
                'message': 'Cor criada com sucesso'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class ColorDetailView(LoginRequiredMixin, View):
    def get(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            color = Color.objects.get(code=code, company=company)
            return JsonResponse({
                'code': color.code,
                'name': color.name
            })
        except Color.DoesNotExist:
            return JsonResponse({'error': 'Cor não encontrada'}, status=404)

class ColorUpdateView(LoginRequiredMixin, View):
    def put(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            name = data.get('name')

            if not name:
                return JsonResponse({'error': 'Nome é obrigatório'}, status=400)

            color = get_object_or_404(Color, code=code, company=company)
            color.name = name
            color.save()

            SechicCacheManager.invalidate_after_data_change(company.id, 'colors')

            return JsonResponse({
                'code': color.code,
                'name': color.name,
                'message': 'Cor atualizada com sucesso'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class ColorDeleteView(LoginRequiredMixin, View):
    def delete(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            color = get_object_or_404(Color, code=code, company=company)
            color.delete()

            SechicCacheManager.invalidate_after_data_change(company.id, 'colors')

            return JsonResponse({'message': 'Cor eliminada com sucesso'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class SizeCreateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            code = data.get('code')
            value = data.get('value')

            if not code or not value:
                return JsonResponse({'error': 'Código e valor são obrigatórios'}, status=400)

            if Size.objects.filter(code=code, company=company).exists():
                return JsonResponse({'error': 'Já existe um tamanho com este código nesta empresa'}, status=400)

            size = Size.objects.create(code=code, value=value, company=company)

            SechicCacheManager.invalidate_after_data_change(company.id, 'sizes')

            return JsonResponse({
                'code': size.code,
                'value': size.value,
                'message': 'Tamanho criado com sucesso'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class SizeDetailView(LoginRequiredMixin, View):
    def get(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            size = Size.objects.get(code=code, company=company)
            return JsonResponse({
                'code': size.code,
                'value': size.value
            })
        except Size.DoesNotExist:
            return JsonResponse({'error': 'Tamanho não encontrado'}, status=404)

class SizeUpdateView(LoginRequiredMixin, View):
    def put(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            value = data.get('value')

            if not value:
                return JsonResponse({'error': 'Valor é obrigatório'}, status=400)

            size = get_object_or_404(Size, code=code, company=company)
            size.value = value
            size.save()

            SechicCacheManager.invalidate_after_data_change(company.id, 'sizes')

            return JsonResponse({
                'code': size.code,
                'value': size.value,
                'message': 'Tamanho atualizado com sucesso'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class SizeDeleteView(LoginRequiredMixin, View):
    def delete(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            size = get_object_or_404(Size, code=code, company=company)
            size.delete()

            SechicCacheManager.invalidate_after_data_change(company.id, 'sizes')

            return JsonResponse({'message': 'Tamanho eliminado com sucesso'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class BrandCreateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            name = data.get('name')

            if not name:
                return JsonResponse({'error': 'Nome é obrigatório'}, status=400)

            if Brand.objects.filter(name=name, company=company).exists():
                return JsonResponse({'error': 'Já existe uma marca com este nome nesta empresa'}, status=400)

            brand = Brand.objects.create(name=name, company=company)

            SechicCacheManager.invalidate_after_data_change(company.id, 'brands')

            return JsonResponse({
                'name': brand.name,
                'message': 'Marca criada com sucesso'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class BrandDetailView(LoginRequiredMixin, View):
    def get(self, request, name):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            brand = Brand.objects.get(name=name, company=company)
            return JsonResponse({
                'name': brand.name
            })
        except Brand.DoesNotExist:
            return JsonResponse({'error': 'Marca não encontrada'}, status=404)

class BrandUpdateView(LoginRequiredMixin, View):
    def put(self, request, name):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            new_name = data.get('name')

            if not new_name:
                return JsonResponse({'error': 'Nome é obrigatório'}, status=400)

            brand = get_object_or_404(Brand, name=name, company=company)

            if new_name != name and Brand.objects.filter(name=new_name, company=company).exists():
                return JsonResponse({'error': 'Já existe uma marca com este nome nesta empresa'}, status=400)

            brand.name = new_name
            brand.save()

            SechicCacheManager.invalidate_after_data_change(company.id, 'brands')

            return JsonResponse({
                'name': brand.name,
                'message': 'Marca atualizada com sucesso'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class BrandDeleteView(LoginRequiredMixin, View):
    def delete(self, request, name):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            brand = get_object_or_404(Brand, name=name, company=company)
            brand.delete()

            SechicCacheManager.invalidate_after_data_change(company.id, 'brands')

            return JsonResponse({'message': 'Marca eliminada com sucesso'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class SupplierDetailView(LoginRequiredMixin, View):
    def get(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            supplier = Supplier.objects.get(code=code, company=company)
            
            markups = supplier.markups.all()
            markups_data = []
            
            for markup in markups:
                markups_data.append({
                    'id': markup.id, 
                    'markup': markup.markup,
                    'created_at': markup.created_at.strftime('%d/%m/%Y %H:%M'),
                    'created_by': markup.created_by.get_full_name() or markup.created_by.username,
                    'is_active': markup.is_active
                })
            
            active_markup = supplier.markups.filter(is_active=True).first()
            if not active_markup:
                active_markup = supplier.markups.first()
            
            return JsonResponse({
                'code': supplier.code,
                'name': supplier.name,
                'current_markup': active_markup.markup if active_markup else None,
                'active_markup_id': active_markup.id if active_markup else None,
                'markups': markups_data
            })
        except Supplier.DoesNotExist:
            return JsonResponse({'error': 'Fornecedor não encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class SupplierAddMarkupView(LoginRequiredMixin, View):
    def post(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            markup = data.get('markup')
            make_active = data.get('make_active', True)

            if markup is None:
                return JsonResponse({'error': 'Markup é obrigatório'}, status=400)

            supplier = get_object_or_404(Supplier, code=code, company=company)
            
            # Se este markup vai ser ativo, desativar todos os outros
            if make_active:
                supplier.markups.update(is_active=False)
            
            # Criar o novo markup
            new_markup = SupplierMarkup.objects.create(
                supplier=supplier,
                markup=markup,
                created_by=request.user,
                is_active=make_active
            )
            
            # Invalidar cache
            SechicCacheManager.invalidate_after_data_change(company.id, 'suppliers')
            
            # Buscar o markup ativo atual (que deve ser o que acabámos de criar)
            active_markup = supplier.markups.filter(is_active=True).first()
            if not active_markup:
                active_markup = supplier.markups.order_by('-created_at').first()

            return JsonResponse({
                'code': supplier.code,
                'name': supplier.name,
                'current_markup': active_markup.markup if active_markup else None,
                'new_markup_id': new_markup.id,
                'active_markup_id': active_markup.id if active_markup else None,
                'message': 'Markup adicionado com sucesso'
            })
        except Exception as e:
            logger.error(f"Erro ao adicionar markup: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

class SupplierSetActiveMarkupView(LoginRequiredMixin, View):
    def post(self, request, code):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            markup_id = data.get('markup_id')

            if not markup_id:
                return JsonResponse({'error': 'ID do markup é obrigatório'}, status=400)
            
            try:
                markup_id = int(markup_id)
            except (ValueError, TypeError):
                return JsonResponse({'error': 'ID do markup deve ser um número'}, status=400)

            supplier = get_object_or_404(Supplier, code=code, company=company)
            markup = get_object_or_404(SupplierMarkup, id=markup_id, supplier=supplier)
            
            # PRIMEIRA: Desativar TODOS os markups do fornecedor
            SupplierMarkup.objects.filter(supplier=supplier).update(is_active=False)
            
            # SEGUNDA: Ativar apenas o markup selecionado
            markup.is_active = True
            markup.save()
            
            # TERCEIRA: Limpar o cache do fornecedor
            SechicCacheManager.invalidate_after_data_change(company.id, 'suppliers')
            
            # QUARTA: Verificar se ficou realmente ativo
            updated_markup = SupplierMarkup.objects.get(id=markup_id)
            
            return JsonResponse({
                'code': supplier.code,
                'name': supplier.name,
                'current_markup': updated_markup.markup,
                'active_markup_id': updated_markup.id,
                'message': 'Markup ativo alterado com sucesso'
            })
            
        except SupplierMarkup.DoesNotExist: 
            return JsonResponse({'error': 'Markup não encontrado'}, status=404)
        except Exception as e:
            logger.error(f"Erro ao alterar markup ativo: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

class CategoryDetailView(LoginRequiredMixin, View):
    def get(self, request, name):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            category = Category.objects.get(name=name, company=company)
            return JsonResponse({
                'name': category.name
            })
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Categoria não encontrada'}, status=404)

class CategoryUpdateView(LoginRequiredMixin, View):
    def put(self, request, name):
        try:
            company = get_user_company(request.user)
            if not company:
                return JsonResponse({'error': 'Nenhuma empresa selecionada'}, status=400)
                
            data = json.loads(request.body)
            new_name = data.get('name')

            if not new_name:
                return JsonResponse({'error': 'Nome é obrigatório'}, status=400)

            category = get_object_or_404(Category, name=name, company=company)

            if new_name != name and Category.objects.filter(name=new_name, company=company).exists():
                return JsonResponse({'error': 'Já existe uma categoria com este nome nesta empresa'}, status=400)

            category.name = new_name
            category.save()

            SechicCacheManager.invalidate_after_data_change(company.id, 'categories')

            return JsonResponse({
                'name': category.name,
                'message': 'Categoria atualizada com sucesso'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)