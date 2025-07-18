#apps/aitigos/views.py
from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from web_project import TemplateLayout
from django.contrib.auth.mixins import LoginRequiredMixin
from typing import Dict, Any, List, Tuple, Optional
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

#from django.db import modelsclass

import requests
import os
import traceback
import uuid
import json
import pandas as pd
import re
import logging
import time
import traceback

from .serializers import ExtractionResultSerializer, ProductSerializer
from .services import MoloniSyncService, ShopifySyncService, ProductComparisonService
from apps.product_moloni.services import ProductMoloniService
from apps.sechic.services import MoloniService
from apps.product_moloni.models import Product, ProductVariant
from apps.sechic.models import Category, Supplier, Unit, Tax, Color, Size, Brand, SupplierMarkup
from apps.moloni.models import Moloni
from apps.shopify.models import Shopify
from .cache_manager import AitigosCacheManager
from apps.sechic.cache_manager import SechicCacheManager

logger = logging.getLogger(__name__)

class AitigosView(LoginRequiredMixin, TemplateView):
    template_name = "aitigos.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        try:
            company = None
            if hasattr(self.request.user, 'profile') and self.request.user.profile.selected_moloni_company:
                company = self.request.user.profile.selected_moloni_company
                logger.info(f"🏢 Empresa selecionada: {company.name} (ID: {company.id})")
            
            if company:
                context['categories'] = self._get_cached_categories(company)
                context['suppliers'] = self._get_cached_suppliers(company)
                context['brands'] = self._get_cached_brands(company)
                context['colors'] = self._get_cached_colors(company)
                context['sizes'] = self._get_cached_sizes(company)

            else:
                logger.warning("Nenhuma empresa selecionada")
                context.update({
                    'categories': [], 'suppliers': [], 'brands': [], 'colors': [], 'sizes': []
                })
            
            context['supplier_markups'] = {}
            if company:
                for sup in context['suppliers']:
                    code = sup['code']
                    qs = SupplierMarkup.objects.filter(
                        supplier__company=company,
                        supplier__code=code
                    ).order_by('-created_at')
                    context['supplier_markups'][code] = [
                        {
                            'markup':     m.markup,
                            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M'),
                            'is_active':  m.is_active
                        }
                        for m in qs
                    ]
            if context['suppliers']:
                sup = context['suppliers'][0]     # ou filtre pelo que o usuário escolheu
                code = sup['code']
                context['current_supplier'] = sup['name']
                # buscar o markup ativo daquele fornecedor no supplier_markups
                markups = context['supplier_markups'].get(code, [])
                ativo = next((m for m in markups if m['is_active']), None) or (markups[0] if markups else None)
                context['current_markup'] = ativo['markup'] if ativo else None
            else:
                context['current_supplier'] = None
                context['current_markup']  = None

        except Exception as e:
            logger.exception(f"Erro ao buscar dados para dropdowns: {str(e)}")
            context.update({
                'categories': [], 'suppliers': [], 'brands': [], 'colors': [], 'sizes': []
            })
       
        return context
    
    def _get_cached_categories(self, company):
        cached_data = AitigosCacheManager.get_cached_categories(company.id)
        if cached_data:
            return cached_data
        
        try:
            from apps.sechic.models import Category
            categories = Category.objects.filter(company=company).order_by('name')
            categories_data = [{"name": cat.name, "id": cat.category_id} for cat in categories]
            
            AitigosCacheManager.cache_categories(company.id, categories_data)
            
            return categories_data
        except Exception as e:
            logger.error(f"Erro ao buscar categorias: {str(e)}")
            return []
    
    def _get_cached_suppliers(self, company):
        """Busca fornecedores com cache Redis"""
        cached_data = AitigosCacheManager.get_cached_suppliers(company.id)
        if cached_data:
            return cached_data
        
        # Cache miss - buscar da base de dados
        try:
            suppliers = Supplier.objects.filter(company=company).order_by('name')
            suppliers_data = [{"name": sup.name, "code": sup.code.zfill(2)} for sup in suppliers]
            
            # Guardar no cache
            AitigosCacheManager.cache_suppliers(company.id, suppliers_data)
            
            return suppliers_data
        except Exception as e:
            logger.error(f"Erro ao buscar fornecedores: {str(e)}")
            return []
    
    def _get_cached_brands(self, company):
        """Busca marcas com cache Redis"""
        cached_data = AitigosCacheManager.get_cached_brands(company.id)
        if cached_data:
            return cached_data
        
        # Cache miss - buscar da base de dados
        try:
            from apps.sechic.models import Brand
            brands = Brand.objects.filter(company=company).order_by('name')
            brands_data = [{"name": brand.name} for brand in brands]
            
            # Guardar no cache
            AitigosCacheManager.cache_brands(company.id, brands_data)
            
            return brands_data
        except Exception as e:
            logger.error(f"Erro ao buscar marcas: {str(e)}")
            return []
    
    def _get_cached_colors(self, company):
        """Busca cores com cache Redis"""
        cached_data = AitigosCacheManager.get_cached_colors(company.id)
        if cached_data:
            return cached_data
        
        # Cache miss - buscar da base de dados
        try:
            from apps.sechic.models import Color
            colors = Color.objects.filter(company=company).order_by('name')
            colors_data = [{"name": color.name, "code": color.code.zfill(3)} for color in colors]
            
            # Guardar no cache
            AitigosCacheManager.cache_colors(company.id, colors_data)
            
            return colors_data
        except Exception as e:
            logger.error(f"Erro ao buscar cores: {str(e)}")
            return []
    
    def _get_cached_sizes(self, company):
        cached_data = AitigosCacheManager.get_cached_sizes(company.id)
        if cached_data:
            return cached_data
        
        try:
            from apps.sechic.models import Size
            sizes = Size.objects.filter(company=company).order_by('value')
            sizes_data = [{"name": size.value, "value": size.value, "code": size.code.zfill(3)} for size in sizes]
            
            # Guardar no cache
            AitigosCacheManager.cache_sizes(company.id, sizes_data)
            
            return sizes_data
        except Exception as e:
            logger.error(f"Erro ao buscar tamanhos: {str(e)}")
            return []

    def normalize_gender(self, gender_value):
        """
        Normaliza o valor do campo gender para os valores permitidos:
        - Homem, Senhora, Crianças
        """
        if not gender_value or not isinstance(gender_value, str):
            return 'Homem'
        
        normalized_value = gender_value.lower().strip()
        
        # Tratamento para "Homem"
        if normalized_value in ['homem', 'masculino', 'male', 'man', 'men']:
            return 'Homem'
        
        # Tratamento para "Senhora"
        if normalized_value in ['senhora', 'mulher', 'feminino', 'female', 'woman', 'women']:
            return 'Senhora'
        
        # Tratamento para "Crianças"
        if normalized_value in ['crianças', 'criancas', 'criança', 'crianca', 'kids', 'children', 'infantil', 'child']:
            return 'Crianças'
        
        # Se já está no formato correto
        if gender_value in ['Homem', 'Senhora', 'Crianças']:
            return gender_value
        
        return 'Homem'
    
    def determine_gender_from_category(self, category):

        if not category or not isinstance(category, str):
            return 'Homem'
        
        category_upper = category.upper()
        
        # Verificar termos femininos
        feminine_terms = ['WOMAN', 'WOMEN', 'SENHORA', 'FEMININO', 'MULHER', 'FEMALE', 'LADY', 'LADIES']
        if any(term in category_upper for term in feminine_terms):
            return 'Senhora'
        
        # Verificar termos infantis
        children_terms = ['KIDS', 'CHILDREN', 'CRIANÇA', 'CRIANÇAS', 'INFANTIL', 'CHILD', 'BABY', 'BEBÊ']
        if any(term in category_upper for term in children_terms):
            return 'Crianças'
        
        return 'Homem'
    
    def post(self, request, *args, **kwargs):
        try:
            uploaded_file = request.FILES.get('file')
            
            if not uploaded_file.name.lower().endswith('.pdf'):
                raise ValidationError('Extensão de ficheiro inválida')
            
            uploaded_file.seek(0)
            header = uploaded_file.read(4)
            if header != b'%PDF':
                raise ValidationError('Ficheiro não é um PDF válido')
            
            if uploaded_file.size > 10 * 1024 * 1024:
                raise ValidationError('Ficheiro demasiado grande')
            
            extraction_result = self._process_file_extraction(uploaded_file)
            
            serializer = ExtractionResultSerializer(data=extraction_result)
            if not serializer.is_valid():
                return JsonResponse({'error': 'Dados inválidos', 'details': serializer.errors}, status=400)
            
            validated_data = serializer.validated_data
            
            company = None
            if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
                company = request.user.profile.selected_moloni_company

            products_df, variants_df, order_info = self._convert_to_dataframes(validated_data)
            
            supplier_name = order_info.get('supplier', '').strip()
            supplier = None

            company = None
            if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
                company = request.user.profile.selected_moloni_company
            
            if company and supplier_name:
                supplier = Supplier.objects.filter(company=company, name=supplier_name).first()

            if supplier:
                markup = supplier.current_markup or 1.0
                variants_df['sales_price'] = variants_df['unit_price'] * markup

                logger.info(f"[AitigosView] sales_price recalculado: unit_price × {markup}")
            else:
                logger.warning(f"[AitigosView] fornecedor '{supplier_name}' não encontrado; sales_price não recalculado")

            processed_products = self._dataframes_to_json(products_df, variants_df)
            
            return JsonResponse({
                'success': True,
                'products': processed_products,
                'order_info': order_info
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Erro ao processar documento: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)

    def put(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            response_data: Dict[str, Any] = {}
            action = data.get('action', '')
            
            products_data = data.get('products', [])
                        
            shared_date = self._extract_shared_date(products_data)
            markup_value = None

            company = None
            if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
                        company = request.user.profile.selected_moloni_company

            if products_data:
                serializer = ProductSerializer(data=products_data, many=True)
                if not serializer.is_valid():
                    return JsonResponse({'error': 'Dados de produtos inválidos', 'details': serializer.errors}, status=400)
                products_data = serializer.validated_data
            
            products_df, variants_df, _ = self._json_to_dataframes(products_data)

            if action == 'update_markups':
                raw_markup    = data.get('markup')               
                markup_float  = float(raw_markup)            
                markup_value  = Decimal(str(raw_markup))  
                supplier_code = data.get('supplierCode')
                variants_df['sales_price'] = variants_df['sales_price'].astype(float)

                if supplier_code:
                    mask = variants_df['supplier'] == supplier_code
                    variants_df.loc[mask, 'sales_price'] = variants_df.loc[mask, 'unit_price'] * markup_float
                supplier_code = data.get('supplierCode')
                if supplier_code:
                    prod_ids = products_df.loc[
                       products_df['supplier'] == supplier_code,
                       'product_id'
                    ]
                    mask = variants_df['product_id'].isin(prod_ids)
                    variants_df.loc[mask, 'sales_price'] = (
                        variants_df.loc[mask, 'unit_price'] * markup_float
                    )
                else:
                    variants_df['sales_price'] = variants_df['unit_price'] * markup_float

                message = f'Preços de venda recalculados x {markup_value}'
            
                if company and supplier_code:
                    try:
                        sup = Supplier.objects.get(company=company, code=supplier_code)

                        SupplierMarkup.objects.filter(supplier=sup, is_active=True)\
                                                .update(is_active=False)
                        
                        markup_obj, created = SupplierMarkup.objects.get_or_create(
                            supplier    = sup,
                            markup      = markup_value,
                            defaults    = {
                                'created_by': request.user,
                                'is_active' : True
                            }
                        )
                        if not created:
                            markup_obj.is_active = True
                            markup_obj.save(update_fields=['is_active'])

                        SechicCacheManager.invalidate_after_data_change(company.id, 'suppliers')
    
                    except Supplier.DoesNotExist:
                        logger.warning(f"Fornecedor {supplier_code} não encontrado para persistir markup")
                else:
                    logger.warning("Company ou supplier_code ausente — não persisti o markup")
            
            elif action == 'update_supplier_and_markup':
                markup_value = Decimal(str(data.get('markup')))
                supplier_code = data.get('supplierCode')
                change_supplier = data.get('changeSupplier', False)
                new_supplier_name = data.get('newSupplierName', '')
                
                # Se o fornecedor foi alterado, atualizar todos os produtos
                if change_supplier and new_supplier_name:
                    products_df['supplier'] = new_supplier_name
                    # Atualizar também o supplier code nas variantes (se necessário)
                    if 'supplier' in variants_df.columns:
                        variants_df['supplier'] = supplier_code
                
                # Aplicar markup baseado no novo fornecedor
                if supplier_code:
                    # Filtrar produtos do fornecedor (agora todos terão o mesmo fornecedor se foi alterado)
                    if change_supplier:
                        # Se mudou o fornecedor, aplicar a todos
                        variants_df['sales_price'] = variants_df['unit_price'].astype(float) * float(markup_value)
                    else:
                        # Se não mudou, aplicar apenas aos do fornecedor específico
                        prod_ids = products_df.loc[
                            products_df['supplier'] == products_df.iloc[0]['supplier'],
                            'product_id'
                        ]
                        mask = variants_df['product_id'].isin(prod_ids)
                        variants_df.loc[mask, 'sales_price'] = (
                            variants_df.loc[mask, 'unit_price'].astype(float) * float(markup_value)
                        )
                else:
                    # Aplicar markup a todos se não houver código de fornecedor
                    variants_df['sales_price'] = variants_df['unit_price'].astype(float) * float(markup_value)
                
                # Persistir o markup no banco de dados
                if company and supplier_code:
                    try:
                        sup = Supplier.objects.get(company=company, code=supplier_code)
                        
                        # Desativar markups anteriores
                        SupplierMarkup.objects.filter(supplier=sup, is_active=True)\
                                                .update(is_active=False)
                        
                        # Criar ou ativar o novo markup
                        markup_obj, created = SupplierMarkup.objects.get_or_create(
                            supplier=sup,
                            markup=markup_value,
                            defaults={
                                'created_by': request.user,
                                'is_active': True
                            }
                        )
                        if not created:
                            markup_obj.is_active = True
                            markup_obj.save(update_fields=['is_active'])
                            
                        SechicCacheManager.invalidate_after_data_change(company.id, 'suppliers')

                    except Supplier.DoesNotExist:
                        logger.warning(f"Fornecedor {supplier_code} não encontrado para persistir markup")
                
                messages = []
                if change_supplier:
                    messages.append(f'Fornecedor alterado para {new_supplier_name}')
                messages.append(f'Preços de venda recalculados com marcação {markup_value}')
                message = '. '.join(messages)
                
                # Adicionar informações extras à resposta
                response_data['supplier_name'] = new_supplier_name if change_supplier else products_df.iloc[0]['supplier'] if len(products_df) > 0 else ''
                response_data['active_markup'] = str(markup_value)

            elif action == 'update_barcode_prefix':
                barcode_prefix = data.get('barcodePrefix', '')
                if not barcode_prefix or len(barcode_prefix) != 2 or not barcode_prefix.isdigit():
                    return JsonResponse({'error': 'Prefixo de código de barras inválido'}, status=400)
                
                products_df, variants_df = self._update_barcode_prefix_df(
                    barcode_prefix, products_df, variants_df)
                
                message = f'Prefixo atualizado com sucesso em {len(variants_df)} códigos de barras'
                
            elif action == 'edit_product':
                product_index = data.get('productIndex', -1)
                product_data = data.get('product', {})
                products_df, variants_df = self._edit_product_df(
                    product_index, product_data, products_df, variants_df)
                message = 'Produto atualizado com sucesso'
                
            elif action == 'delete_product':
                product_index = data.get('productIndex', -1)
                products_df, variants_df = self._delete_product_df(
                    product_index, products_df, variants_df)
                message = 'Produto excluído com sucesso'
                
            elif action == 'delete_variant':
                product_index = data.get('productIndex', -1)
                variant_index = data.get('variantIndex', -1)
                variants_df = self._delete_variant_df(
                    product_index, variant_index, variants_df)
                message = 'Variante excluída com sucesso'
            
            if shared_date:
                products_df = self._apply_shared_date_to_dataframe(products_df, shared_date)
            
            processed_products = self._dataframes_to_json(products_df, variants_df)
            
            if shared_date:
                for product in processed_products:
                    if not product.get('date') or product.get('date') == '':
                        logger.warning(f"[PUT] Corrigindo data vazia no produto {product.get('name', 'SEM_NOME')}")
                        product['date'] = shared_date
            
            final_dates = [p.get('date', '') for p in processed_products]
            valid_final = len([d for d in final_dates if d and d.strip()])
            
            logger.info(f"[PUT] RESPOSTA FINAL: {len(processed_products)} produtos, {valid_final} com data válida")
            
            response_data = {
                'success': True,
                'message': message,
                'products': processed_products,
            }
            if action == 'update_markups':
                response_data['active_markup'] = markup_value
            return JsonResponse(response_data)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
        except Exception as e:
            logger.error(f"[PUT] ERRO: {str(e)}")
            return JsonResponse({
                'error': f'Erro ao processar requisição: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
    ##### Teste
    def _process_file_extraction(self, uploaded_file):
        """
        Processa a extração do arquivo enviando para o serviço de IA
        """
        # Preparar para envio ao serviço
        files = {'file': (uploaded_file.name, uploaded_file, 'application/pdf')}
        #API_BASE_URL = 'http://localhost:8001'
        API_BASE_URL = os.getenv("API_BASE_URL", "http://172.20.141.28:8011")
        
        # Etapa 1: Submeter o arquivo para processamento
        logger.info(f"Enviando arquivo {uploaded_file.name} para processamento")
        process_response = requests.post(f'{API_BASE_URL}/process', files=files)
        
        if process_response.status_code != 200:
            raise Exception(f'Erro ao enviar arquivo: {process_response.text}')
        
        # Obter o ID do job
        job_data = process_response.json()
        job_id = job_data.get('job_id')
        
        if not job_id:
            raise Exception('ID do job não encontrado na resposta')
        
        logger.info(f"Job criado com ID: {job_id}")
        
        # Etapa 2: Aguardar processamento completo
        max_attempts = 30
        poll_interval = 2
        
        for attempt in range(max_attempts):
            # Check job status
            status_response = requests.get(f'{API_BASE_URL}/job/{job_id}')
            
            if status_response.status_code != 200:
                raise Exception(f'Erro ao verificar status: {status_response.text}')
            
            status_data = status_response.json()
            
            # Check if job is complete
            if status_data.get('status') == 'completed':
                logger.info(f"Job {job_id} concluído após {attempt+1} tentativas")
                break
                    
            # Check if job failed
            if status_data.get('status') == 'failed':
                raise Exception('Processamento falhou')
            
            logger.debug(f"Job em processamento. Tentativa {attempt+1}/{max_attempts}. Progresso: {status_data.get('progress', 0)}%")
            
            # Wait before next poll
            time.sleep(poll_interval)
        else:
            # Loop completed without breaking - timeout
            raise Exception('Tempo limite excedido aguardando processamento')
        
        # Etapa 3: Get the results
        logger.info(f"Obtendo resultados para o job {job_id}")
        results_response = requests.get(f'{API_BASE_URL}/job/{job_id}/json')
        
        if results_response.status_code != 200:
            raise Exception(f'Erro ao obter resultados: {results_response.text}')
        
        # Get the extraction data
        job_data = results_response.json()
        
        # Extract products, handling different possible structures
        extraction_data = None
        
        # Full structure (model_results -> gemini -> result)
        if job_data.get('model_results') and job_data['model_results'].get('gemini') and job_data['model_results']['gemini'].get('result'):
            logger.info("Estrutura completa detectada (model_results -> gemini -> result)")
            extraction_data = job_data['model_results']['gemini']['result']
        # Direct structure (products array at root)
        elif job_data.get('products') and isinstance(job_data['products'], list):
            logger.info("Estrutura direta detectada (produtos na raiz)")
            extraction_data = job_data
        else:
            logger.warning("Estrutura desconhecida, usando dados brutos")
            extraction_data = job_data
        
        # Log para depuração
        logger.debug(f"Número de produtos recebidos: {len(extraction_data.get('products', []))}")
        
        # Garantir estrutura mínima antes da validação
        if 'products' not in extraction_data:
            extraction_data['products'] = []
        if 'order_info' not in extraction_data:
            extraction_data['order_info'] = {}
        
        serializer = ExtractionResultSerializer(data=extraction_data)
        if serializer.is_valid():
            logger.info("Dados validados com sucesso pelo serializer")
            
            # Garantir que os produtos têm variantes e campo details antes de retornar
            valid_data = serializer.validated_data
            
            if 'products' in valid_data and isinstance(valid_data['products'], list):
                # Primeiro garantir variantes
                valid_data['products'] = [self._ensure_product_has_variants(p) for p in valid_data['products']]
                # Depois garantir campo details
                valid_data['products'] = self._ensure_details_field(valid_data['products'])
            
            return valid_data
        else:
            # Log detalhado dos erros
            logger.warning(f"Erros de validação no serializer: {serializer.errors}")
            
            # Tentar identificar campos específicos com problemas
            for field, errors in serializer.errors.items():
                if field == 'products' and isinstance(errors, list) and errors:
                    for i, product_errors in enumerate(errors):
                        if product_errors:
                            logger.warning(f"Erro no produto {i}: {product_errors}")
            
            # Em ambiente de desenvolvimento, pode ser útil ver a estrutura exata
            # dos dados que estão causando problemas
            if settings.DEBUG:
                try:
                    # Limitar o tamanho para evitar logs enormes
                    data_str = json.dumps(extraction_data)[:1000]
                    logger.debug(f"Primeiros 1000 caracteres dos dados: {data_str}...")
                except:
                    logger.debug("Não foi possível serializar os dados para log")
            
            logger.info("Usando dados originais sem validação completa")
            
            # Tentar criar um dicionário válido para retornar
            valid_data = {
                'products': [],
                'order_info': {}
            }
            
            # Copiar produtos se existirem
            if 'products' in extraction_data and isinstance(extraction_data['products'], list):
                valid_data['products'] = extraction_data['products']
            
            # Copiar order_info se existir
            if 'order_info' in extraction_data and isinstance(extraction_data['order_info'], dict):
                valid_data['order_info'] = extraction_data['order_info']
            
            # Garantir que os produtos têm variantes e campo details
            if 'products' in valid_data and isinstance(valid_data['products'], list):
                # Primeiro garantir variantes
                valid_data['products'] = [self._ensure_product_has_variants(p) for p in valid_data['products']]
                # Depois garantir campo details
                valid_data['products'] = self._ensure_details_field(valid_data['products'])
            
            # Adicionar logs para depuração final
            for idx, product in enumerate(valid_data.get('products', [])):
                details_count = len(product.get('details', []))
                logger.debug(f"Produto {idx}: {product.get('name')}, {details_count} detalhes")
                if details_count == 0:
                    logger.warning(f"Produto sem detalhes após processamento: {product.get('name')}")
            
            return valid_data
    
    def _ensure_details_field(self, products):
        for product in products:
            product['details'] = []
            ref_counter = 0
            
            # Se tiver cores, usar para gerar details
            if 'colors' in product and isinstance(product['colors'], list):
                for color in product['colors']:
                    color_code = color.get('color_code', '')
                    color_name = color.get('color_name', '')
                    
                    # Adicionar cada tamanho como um detalhe separado
                    for size_item in color.get('sizes', []):
                        size = size_item.get('size', '')
                        quantity = size_item.get('quantity', 0)
                        
                        if not size or quantity <= 0:
                            continue
                            
                        # Gerar referência sequencial e código de barras
                        ref_counter += 1
                        reference = f"{product.get('material_code', '')}.{ref_counter}"
                        
                        # Use a função existente para gerar código de barras
                        try:
                            # Extrair apenas dígitos do código de material
                            material_code = product.get('material_code', '')
                            ref_digits = re.sub(r'\D', '', material_code).zfill(7)[-7:]
                            color_digits = str(color_code).zfill(3)[-3:]
                            counter_str = str(ref_counter).zfill(3)
                            
                            # Formar o código de barras
                            barcode = f"{ref_digits}{color_digits}{counter_str}"
                        except:
                            # Fallback em caso de erro
                            barcode = f"{product.get('material_code', '')}-{color_code}-{ref_counter}"
                        
                        product['details'].append({
                            'reference': reference,
                            'color_code': color_code,
                            'color_name': color_name,
                            'size': size,
                            'description': f"{product.get('name', '')}[{color_code}/{size}]",
                            'quantity': quantity,
                            'unit_price': color.get('unit_price', 0),
                            'sales_price': color.get('sales_price', 0),
                            'barcode': barcode
                        })
        return products

    def _ensure_product_has_variants(self,product):
        """Garante que cada produto tenha pelo menos uma variante básica"""
        if 'details' in product and product['details']:
            return product
            
        if 'references' in product and product['references']:
            return product
        
        if 'colors' in product and any(color.get('sizes') for color in product.get('colors', [])):
            return product
        
        logger.warning(f"Adicionando variante padrão para produto sem variantes: {product.get('name')}")
        
        if 'colors' not in product or not isinstance(product['colors'], list) or not product['colors']:
            product['colors'] = [{
                'color_code': '100', 
                'color_name': 'Padrão',
                'sizes': [{'size': 'M', 'quantity': 1}],
                'unit_price': 0.0,
                'sales_price': 0.0
            }]
        
        # Garantir que a primeira cor tem tamanhos
        if not product['colors'][0].get('sizes'):
            product['colors'][0]['sizes'] = [{'size': 'M', 'quantity': 1}]
        
        return product

    def _convert_to_dataframes(self, extraction_data):
        # Extrair produtos e informações do pedido
        products = extraction_data.get('products', [])
        order_info = extraction_data.get('order_info', {})
        
        # Criar listas para popular os DataFrames
        products_data = []
        variants_data = []
        
        # Processar cada produto e suas variantes
        for product_idx, product in enumerate(products):
            # Dados básicos do produto
            material_code = product.get('material_code', '')
            name = product.get('name', '')
            composition = product.get('composition', '')
            category = product.get('category', '')
            brand = product.get('brand', order_info.get('brand', ''))
            
            # Determinar gênero baseado na categoria
            gender = self.determine_gender_from_category(category)
            
            if 'gender' in product:
                gender = self.normalize_gender(product['gender'])

            # Aplicar tratamento final
            gender = self.normalize_gender(gender)

            # Adicionar produto ao DataFrame de produtos
            products_data.append({
                'product_id': product_idx,  # ID interno para relacionamento
                'material_code': material_code,
                'name': name,
                'composition': composition,
                'category': category,
                'gender': gender,
                'brand': brand,
                'supplier': order_info.get('supplier', ''),
                'date': order_info.get('date', ''),
                'integrated': '0'  # Valor padrão
            })
            
            # Criar um mapeamento de referências para acessar os códigos de barras originais
            reference_barcode_map = {}
            if 'references' in product and isinstance(product['references'], list):
                for ref in product['references']:
                    key = f"{ref.get('color_code')}_{ref.get('size')}"
                    reference_barcode_map[key] = ref.get('barcode', '')
            
            # Processar cores e tamanhos
            variant_counter = 0
            for color in product.get('colors', []):
                color_code = color.get('color_code', '')
                color_name = color.get('color_name', '')
                
                for size_item in color.get('sizes', []):
                    size = size_item.get('size', '')
                    quantity = size_item.get('quantity', 0)
                    
                    # Pular itens sem tamanho ou quantidade <= 0
                    if not size or quantity <= 0:
                        continue
                    
                    variant_counter += 1
                    reference = f"{material_code}.{variant_counter}"
                    
                    # Verificar se temos um código de barras original para esta combinação de cor/tamanho
                    key = f"{color_code}_{size}"
                    barcode = reference_barcode_map.get(key, '')
                    
                    # Se não temos um código de barras original, gerar um
                    if not barcode:
                        barcode = self._generate_barcode(material_code, color_code, variant_counter)
                    
                    variants_data.append({
                        'product_id': product_idx,
                        'variant_id': variant_counter - 1,  # ID 0-indexed
                        'reference': reference,
                        'color_code': color_code,
                        'color_name': color_name,
                        'size': size,
                        'description': f"{name}[{color_code}/{size}]",
                        'quantity': quantity,
                        'unit_price': color.get('unit_price', 0),
                        'sales_price': color.get('sales_price'),
                        'barcode': barcode
                    })
        
        # Criar os DataFrames
        products_df = pd.DataFrame(products_data) if products_data else pd.DataFrame(columns=[
            'product_id', 'material_code', 'name', 'composition', 'category', 
            'gender', 'brand', 'supplier', 'date', 'integrated'
        ])
        
        variants_df = pd.DataFrame(variants_data) if variants_data else pd.DataFrame(columns=[
            'product_id', 'variant_id', 'reference', 'color_code', 'color_name', 
            'size', 'description', 'quantity', 'unit_price', 'sales_price', 'barcode'
        ])
        
        return products_df, variants_df, order_info
    
    def _json_to_dataframes(self, products_data):
        # Criar listas para popular os DataFrames
        products_list = []
        variants_list = []
        
        # Primeiro identificar qualquer data disponível em todos os produtos
        shared_date = None
        for product in products_data:
            if product.get('date'):
                shared_date = product.get('date')
                break
        
        # Processar cada produto
        for product_idx, product in enumerate(products_data):
            # Garantir que todos os produtos tenham a mesma data (quando aplicável)
            date_value = product.get('date', shared_date or '')
            
            # Adicionar produto ao DataFrame
            products_list.append({
                'product_id': product_idx,
                'material_code': product.get('material_code', ''),
                'name': product.get('name', ''),
                'composition': product.get('composition', ''),
                'category': product.get('category', ''),
                'gender': self.normalize_gender(product.get('gender', 'Homem')),
                'brand': product.get('brand', ''),
                'supplier': product.get('supplier', ''),
                'date': date_value,
                'integrated': product.get('integrated', '0')
            })
            
            # Processar variantes/detalhes
            for var_idx, detail in enumerate(product.get('details', [])):
                variants_list.append({
                    'product_id': product_idx,
                    'variant_id': var_idx,
                    'reference': detail.get('reference', ''),
                    'color_code': detail.get('color_code', ''),
                    'color_name': detail.get('color_name', ''),
                    'size': detail.get('size', ''),
                    'description': detail.get('description', ''),
                    'quantity': detail.get('quantity', 0),
                    'unit_price': detail.get('unit_price', 0),
                    'sales_price': detail.get('sales_price', 0),
                    'barcode': detail.get('barcode', ''),
                    'supplier': product.get('supplier','')
                })
        
        # Criar DataFrames
        products_df = pd.DataFrame(products_list) if products_list else pd.DataFrame(columns=[
            'product_id', 'material_code', 'name', 'composition', 'category', 
            'gender', 'brand', 'supplier', 'date', 'integrated'
        ])
        
        variants_df = pd.DataFrame(variants_list) if variants_list else pd.DataFrame(columns=[
            'product_id', 'variant_id', 'reference', 'color_code', 'color_name', 
            'size', 'description', 'quantity', 'unit_price', 'sales_price', 'barcode'
        ])
        
        # Garantir a mesma data em todos os produtos, se houver pelo menos uma disponível
        if shared_date and not products_df.empty:
            mask = (products_df['date'].isna()) | (products_df['date'] == '')
            products_df.loc[mask, 'date'] = shared_date
        
        return products_df, variants_df, {}
    
    def _generate_barcode(self, material_code, color_code, counter):
        """
        Gera um código de barras para o produto
        
        O formato é: [dígitos do material_code][dígitos do color_code][contador]
        """
        try:
            ref_digits = re.sub(r'\D', '', material_code).zfill(7)[-7:]
            color_digits = str(color_code).zfill(3)[-3:]
            counter_str = str(counter).zfill(3)
            
            barcode = f"{ref_digits}{color_digits}{counter_str}"
            return barcode
        except:
            return f"{material_code}-{color_code}-{counter}"
    
    def _update_barcode_prefix_df(self, barcode_prefix, products_df, variants_df):
        if not barcode_prefix or len(barcode_prefix) != 2 or not barcode_prefix.isdigit():
            raise ValueError('O prefixo do código de barras deve conter exatamente 2 dígitos')
        
        shared_date = None
        if not products_df.empty:
            for idx, row in products_df.iterrows():
                date_val = row.get('date', '')
                if (date_val and 
                    str(date_val).strip() and 
                    str(date_val).strip().lower() not in ['', 'none', 'null', 'nan']):
                    shared_date = str(date_val).strip()
                    logger.info(f"[_update_barcode_prefix_df] Data capturada: '{shared_date}' do produto índice {idx}")
                    break
        
        if not shared_date:
            logger.warning("[_update_barcode_prefix_df] NENHUMA DATA ENCONTRADA! Isso pode ser um problema.")
        
        def update_barcode(barcode):
            try:
                if pd.isna(barcode) or str(barcode).strip() == '':
                    return barcode
                
                barcode_str = str(barcode).strip().zfill(13)
                updated_barcode = barcode_prefix + barcode_str[2:]
                return updated_barcode
                
            except Exception as e:
                logger.error(f"[update_barcode] Erro: {e}")
                return barcode

        # Aplicar atualização
        original_count = len(variants_df)
        variants_df['barcode'] = variants_df['barcode'].apply(update_barcode)
        
        if shared_date:
            # FORÇA a aplicação da data em TODOS os produtos
            products_df['date'] = shared_date
            logger.info(f"[_update_barcode_prefix_df] Data '{shared_date}' FORÇADA em todos os {len(products_df)} produtos")
            
            # Verificação adicional
            null_dates = products_df['date'].isna().sum()
            empty_dates = (products_df['date'] == '').sum()
            
            if null_dates > 0 or empty_dates > 0:
                logger.error(f"[_update_barcode_prefix_df] ERRO: Ainda existem {null_dates} datas nulas e {empty_dates} datas vazias!")
                # Tentar corrigir novamente
                products_df['date'] = products_df['date'].fillna(shared_date)
                products_df.loc[products_df['date'] == '', 'date'] = shared_date
        else:
            logger.error("[_update_barcode_prefix_df] ERRO CRÍTICO: Não foi possível preservar a data!")
        
        logger.info(f"[_update_barcode_prefix_df] FIM - {original_count} códigos atualizados")
        
        return products_df, variants_df

    def _dataframes_to_json(self, products_df, variants_df):

        logger.info("[_dataframes_to_json] INÍCIO da conversão")
        
        if products_df.empty:
            return []
        
        shared_date = None
        if not products_df.empty:
            # Procurar primeira data válida
            for idx, row in products_df.iterrows():
                date_val = row.get('date', '')
                if (date_val and 
                    str(date_val).strip() and 
                    str(date_val).strip().lower() not in ['', 'none', 'null', 'nan']):
                    shared_date = str(date_val).strip()
                    logger.info(f"[_dataframes_to_json] Data identificada: '{shared_date}'")
                    break
        
        if not shared_date:
            logger.error("[_dataframes_to_json] ERRO: Nenhuma data válida encontrada!")
        
        result = []
        products_dict = products_df.to_dict('records')
        
        for product in products_dict:
            product_id = product['product_id']
            
            date_to_use = shared_date if shared_date else ''
            
            logger.debug(f"[_dataframes_to_json] Produto {product.get('name', 'SEM_NOME')}: usando data '{date_to_use}'")
            
            # Filtrar variantes
            product_variants = variants_df[variants_df['product_id'] == product_id].to_dict('records')
            
            # Criar produto formatado
            formatted_product = {
                'material_code': product.get('material_code', ''),
                'name': product.get('name', ''),
                'composition': product.get('composition', ''),
                'category': product.get('category', ''),
                'gender': self.normalize_gender(product.get('gender', 'Homem')),                
                'brand': product.get('brand', ''),
                'supplier': product.get('supplier', ''),
                'date': date_to_use,
                'warehouse': product.get('warehouse', '1'),
                'integrated': product.get('integrated', '0'),
                'details': []
            }
            
            # Adicionar variantes
            for variant in product_variants:
                formatted_product['details'].append({
                    'reference': variant.get('reference', ''),
                    'color_code': variant.get('color_code', ''),
                    'color_name': variant.get('color_name', ''),
                    'size': variant.get('size', ''),
                    'description': variant.get('description', ''),
                    'quantity': variant.get('quantity', 0),
                    'unit_price': variant.get('unit_price', 0),
                    'sales_price': variant.get('sales_price', 0),
                    'barcode': variant.get('barcode', '')
                })
            
            result.append(formatted_product)
        
        # ===== STEP 3: VERIFICAÇÃO FINAL =====
        dates_in_result = [p.get('date', 'VAZIO') for p in result]
        empty_dates = dates_in_result.count('')
        valid_dates = len([d for d in dates_in_result if d and d != 'VAZIO'])
        
        logger.info(f"[_dataframes_to_json] FIM - {len(result)} produtos, {valid_dates} com data válida, {empty_dates} vazios")
        
        if empty_dates > 0:
            logger.error(f"[_dataframes_to_json] PROBLEMA: {empty_dates} produtos sem data!")
        
        return result
    
    def _delete_product_df(self, product_index, products_df, variants_df):
        if product_index < 0 or product_index >= len(products_df):
            raise ValueError('Índice de produto fora dos limites')
        
        # Obter o product_id real antes de remover
        product_id_to_remove = products_df.iloc[product_index]['product_id']
        
        # Remover o produto
        products_df = products_df[products_df['product_id'] != product_id_to_remove].reset_index(drop=True)

        # Criar novo mapeamento de product_id
        old_ids = products_df['product_id'].tolist()  # Estes ainda são os antigos
        products_df['product_id'] = range(len(products_df))  # Novo reindexamento
        new_ids = products_df['product_id'].tolist()

        # Criar dicionário old_id -> new_id
        id_mapping = dict(zip(old_ids, new_ids))
        
        # Remover variantes associadas ao produto excluído
        variants_df = variants_df[variants_df['product_id'] != product_id_to_remove]

        # Atualizar os product_id restantes nas variantes
        variants_df['product_id'] = variants_df['product_id'].map(lambda x: id_mapping.get(x, x))

        return products_df, variants_df

    def _delete_variant_df(self, product_index, variant_index, variants_df):
        """
        Exclui uma variante específica do DataFrame de variantes
        """
        # Validar os índices
        if product_index < 0 or variant_index < 0:
            raise ValueError('Índices inválidos')

        # Obter todas as variantes do produto
        product_variants = variants_df[variants_df['product_id'] == product_index].copy()

        if variant_index >= len(product_variants):
            raise ValueError('Índice de variante fora dos limites')

        # Excluir a variante com base no índice informado
        product_variants = product_variants.drop(product_variants.index[variant_index]).reset_index(drop=True)

        # Reatribuir os variant_id apenas dentro deste produto
        product_variants['variant_id'] = product_variants.index

        # Filtrar variantes dos outros produtos
        other_variants = variants_df[variants_df['product_id'] != product_index]

        # Concatenar os dois DataFrames novamente
        variants_df = pd.concat([other_variants, product_variants], ignore_index=True)

        return variants_df

    def _edit_product_df(self, product_index, product_data, products_df, variants_df):
        # Validar o índice do produto
        if product_index < 0 or product_index >= len(products_df):
            raise ValueError('Índice de produto fora dos limites')
        
        # Obter o product_id real do DataFrame
        product_id = products_df.iloc[product_index]['product_id']
        
        # Se a data não estiver definida no produto editado, manter a data existente
        current_date = products_df.loc[products_df['product_id'] == product_id, 'date'].values[0]
        new_date = product_data.get('date', '')
        
        if not new_date and current_date:
            product_data['date'] = current_date
        
        # Atualizar dados do produto
        products_df.loc[products_df['product_id'] == product_id, 'material_code'] = product_data.get('material_code', '')
        products_df.loc[products_df['product_id'] == product_id, 'name'] = product_data.get('name', '')
        products_df.loc[products_df['product_id'] == product_id, 'composition'] = product_data.get('composition', '')
        products_df.loc[products_df['product_id'] == product_id, 'category'] = product_data.get('category', '')
        products_df.loc[products_df['product_id'] == product_id, 'gender'] = self.normalize_gender(product_data.get('gender', 'Homem'))
        products_df.loc[products_df['product_id'] == product_id, 'brand'] = product_data.get('brand', '')
        products_df.loc[products_df['product_id'] == product_id, 'supplier'] = product_data.get('supplier', '')
        products_df.loc[products_df['product_id'] == product_id, 'date'] = product_data.get('date', current_date)
        products_df.loc[products_df['product_id'] == product_id, 'integrated'] = product_data.get('integrated', '0')
        products_df.loc[products_df['product_id'] == product_id, 'warehouse'] = product_data.get('warehouse', '1')

        variants_df = variants_df[variants_df['product_id'] != product_id]
        
        # Adicionar novas variantes
        new_variants = []
        for idx, detail in enumerate(product_data.get('details', [])):
            # Atualizar descrição com base no nome do produto e códigos
            description = f"{product_data['name']}[{detail.get('color_code', '')}/{detail.get('size', '')}]"
            
            new_variants.append({
                'product_id': product_id,
                'variant_id': idx,
                'reference': detail.get('reference', ''),
                'color_code': detail.get('color_code', ''),
                'color_name': detail.get('color_name', ''),
                'size': detail.get('size', ''),
                'description': description,
                'quantity': detail.get('quantity', 0),
                'unit_price': detail.get('unit_price', 0),
                'sales_price': detail.get('sales_price', 0),
                'barcode': detail.get('barcode', '')
            })
        
        # Adicionar novas variantes ao DataFrame
        new_variants_df = pd.DataFrame(new_variants) if new_variants else pd.DataFrame(columns=variants_df.columns)
        variants_df = pd.concat([variants_df, new_variants_df], ignore_index=True)
        
        return products_df, variants_df

    def _extract_shared_date(self, products_data):
        shared_date = None
        
        if not products_data:
            return None
            
        for product in products_data:
            date_value = product.get('date', '')
            
            if (date_value and 
                str(date_value).strip() and 
                str(date_value).strip().lower() not in ['', 'none', 'null', 'nan']):
                shared_date = str(date_value).strip()
                logger.info(f"[_extract_shared_date] Data encontrada: '{shared_date}'")
                break
        
        return shared_date

    def _apply_shared_date_to_dataframe(self, products_df, shared_date):
        if shared_date and not products_df.empty:
            products_df['date'] = shared_date
            logger.info(f"[_apply_shared_date_to_dataframe] Data '{shared_date}' aplicada a {len(products_df)} produtos")
        
        return products_df

class SyncToMoloniView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            products_data = data.get('products', [])

            if not products_data:
                return JsonResponse({"error": "Nenhum produto fornecido"}, status=400)

            serializer = ProductSerializer(data=products_data, many=True)
            if not serializer.is_valid():
                return JsonResponse({
                    'error': 'Dados de produtos inválidos', 
                    'details': serializer.errors
                }, status=400)
            
            products_data = serializer.validated_data

            company = self._get_moloni_company(request)
            if not company:
                return JsonResponse({
                    "error": "É necessário selecionar uma empresa Moloni primeiro",
                    "code": "company_required"
                }, status=401)

            success, metrics, results = MoloniSyncService.sync_products_to_moloni(
                products_data, company
            )

            message = MoloniSyncService.generate_sync_message(metrics)

            self._clear_session_data(request)

            logger.info(message)
            return JsonResponse({
                "success": success,
                "message": message,
                "metrics": metrics,
                "results": results
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
        except Exception as e:
            return self._handle_sync_error(e, request)

    def _get_moloni_company(self, request) -> Optional[Moloni]:
        company = None
        
        if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
            company = request.user.profile.selected_moloni_company
        else:
            company_id = request.session.get('selected_company_id')
            if company_id:
                try:
                    company = Moloni.objects.get(company_id=company_id)
                except Moloni.DoesNotExist:
                    pass

        if not company:
            logger.warning("Empresa Moloni não disponível")
        
        return company
    
    def _clear_session_data(self, request):
        try:
            if "products_to_moloni" in request.session:
                del request.session['products_to_moloni']
                request.session.modified = True
        except:
            pass
    
    def _handle_sync_error(self, e: Exception, request) -> JsonResponse:
        logger.exception(f"Erro ao sincronizar com Moloni: {str(e)}")
        
        error_msg = str(e).lower()
        
        if any(term in error_msg for term in ['unauthorized', 'token', 'auth', 'permission']):
            return JsonResponse({
                "error": "Erro de autenticação no Moloni. É necessário autenticar novamente.",
                "code": "auth_required"
            }, status=401)
        
        if "invalid_grant" in error_msg or "invalid refresh token" in error_msg:
            logger.warning("Refresh token do Moloni inválido. Marcando necessidade de reautenticação.")
            
            request.session['moloni_token_invalid'] = True
            request.session.modified = True
            
            return JsonResponse({
                "error": "A sua sessão Moloni expirou. Você precisará fazer login novamente.",
                "code": "moloni_reauth_required",
                "action": "reauth"
            }, status=401)
        
        return JsonResponse({
            'error': f'Erro ao sincronizar: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=500)

class SyncToShopifyView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            products_data = data.get('products', [])

            if not products_data:
                return JsonResponse({"error": "Nenhum produto fornecido"}, status=400)

            serializer = ProductSerializer(data=products_data, many=True)
            if not serializer.is_valid():
                return JsonResponse({
                    'error': 'Dados de produtos inválidos', 
                    'details': serializer.errors
                }, status=400)
            
            products_data = serializer.validated_data

            # Verificar se o usuário tem loja Shopify configurada
            try:
                shopify_store = Shopify.objects.filter(users=request.user).first()
                if not shopify_store:
                    return JsonResponse({
                        "error": "Não há lojas Shopify associadas a este usuário. "
                                "Por favor, configure sua loja Shopify primeiro."
                    }, status=400)
                
                shop_domain = shopify_store.shop_domain
                access_token = shopify_store.access_token
                
                if not shop_domain or not access_token:
                    return JsonResponse({
                        "error": "Credenciais da loja Shopify incompletas. "
                                "Verifique sua configuração."
                    }, status=400)
                
            except Exception as e:
                logger.exception(f"Erro ao buscar loja Shopify do usuário: {str(e)}")
                return JsonResponse({
                    "error": f"Erro ao buscar loja Shopify: {str(e)}"
                }, status=500)

            # PASSO 1: CONSOLIDAR PRODUTOS POR COR
            consolidated_products = ShopifySyncService.consolidate_products_by_color(products_data)

            # Obter localizações do Shopify para controle de inventário
            locations = ShopifySyncService.get_locations(access_token, shop_domain)
            if not locations:
                return JsonResponse({
                    "error": "Não foi possível obter as localizações da loja Shopify."
                }, status=400)
            
            default_location_id = locations[0].get("id")

            # Inicializar métricas
            original_products = len(products_data)
            consolidated_count = len(consolidated_products)
            original_variants = sum(len(p.get('details', [])) for p in products_data)
            consolidated_variants = sum(len(p.get('details', [])) for p in consolidated_products)
            
            metrics = {
                "original_products": original_products,
                "consolidated_products": consolidated_count,
                "products_merged": original_products - consolidated_count,
                "original_variants": original_variants,
                "consolidated_variants": consolidated_variants,
                "created": 0,
                "failed": 0
            }
            
            results = []

            # Processar cada produto consolidado
            for product_idx, product in enumerate(consolidated_products, 1):
                try:
                    product_name = product.get('name', f'Produto {product_idx}')
                    logger.info(f"Processando produto consolidado {product_idx}/{len(consolidated_products)}: {product_name}")
                    
                    # Formatar produto para o Shopify
                    shopify_product_data = ShopifySyncService.format_product_for_shopify(product)
                    
                    # Criar produto no Shopify
                    success, shopify_product, message = ShopifySyncService.create_product(
                        access_token, shop_domain, shopify_product_data
                    )
                    
                    if success and shopify_product:
                        product_id = shopify_product.get('id')
                        variants = shopify_product.get('variants', [])
                        
                        logger.info(f"Produto criado com sucesso: ID {product_id}, {len(variants)} variantes")
                        
                        # Atualizar inventário para cada variante
                        for variant in variants:
                            try:
                                inventory_item_id = variant.get('inventory_item_id')
                                variant_sku = variant.get('sku', '')
                                
                                # Encontrar a quantidade correspondente nos dados originais
                                original_quantity = 0
                                for detail in product.get('details', []):
                                    if detail.get('reference') == variant_sku:
                                        original_quantity = int(detail.get('quantity', 0))
                                        break
                                
                                if inventory_item_id and original_quantity > 0:
                                    inventory_success, inventory_message = ShopifySyncService.update_inventory_level(
                                        access_token, shop_domain, inventory_item_id, 
                                        default_location_id, original_quantity
                                    )
                                    
                                    if inventory_success:
                                        logger.debug(f"Inventário atualizado para variante {variant_sku}: {original_quantity}")
                                    else:
                                        logger.warning(f"Erro ao atualizar inventário para variante {variant_sku}: {inventory_message}")
                                        
                            except Exception as e:
                                logger.warning(f"Erro ao atualizar inventário da variante {variant.get('sku', 'desconhecida')}: {str(e)}")
                        
                        metrics["created"] += 1
                        results.append({
                            "id": product_id,
                            "name": product_name,
                            "action": "created",
                            "variants_count": len(variants),
                            "success": True
                        })
                        
                    else:
                        logger.error(f"Falha ao criar produto {product_name}: {message}")
                        metrics["failed"] += 1
                        results.append({
                            "name": product_name,
                            "action": "create_failed",
                            "error": message,
                            "success": False
                        })
                        
                except Exception as e:
                    metrics["failed"] += 1
                    logger.exception(f"Erro ao processar produto {product.get('name', 'desconhecido')}: {str(e)}")
                    results.append({
                        "name": product.get('name', f'Produto {product_idx}'),
                        "action": "exception",
                        "error": str(e),
                        "success": False
                    })
                                
                # Pausa entre produtos para evitar rate limiting
                time.sleep(1)

            # Gerar mensagem de resultado
            message = f"Sincronização com Shopify concluída: {metrics['created']} produtos criados"
            if metrics["products_merged"] > 0:
                message += f" (consolidados {metrics['products_merged']} produtos por cor)"
            if metrics["failed"] > 0:
                message += f", {metrics['failed']} falhas"
            message += f". Total de {metrics['consolidated_variants']} variantes processadas."

            logger.info(message)
            return JsonResponse({
                "success": metrics["created"] > 0,
                "message": message,
                "metrics": metrics,
                "results": results
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.exception(f"Erro ao sincronizar com Shopify: {str(e)}")
            
            return JsonResponse({
                'error': f'Erro ao sincronizar com Shopify: {str(e)}',
                'traceback': error_trace,
                'suggestion': 'Verifique se você está conectado ao Shopify e se a configuração está correta'
            }, status=500)

class SyncToBothView(LoginRequiredMixin, View): 
    """
    View para sincronizar produtos com Moloni e Shopify simultaneamente
    """
    
    def post(self, request, *args, **kwargs):
        """
        Recebe os produtos processados e os envia para ambas as plataformas
        """
        try:
            # Obter dados do corpo da requisição
            data = json.loads(request.body)
            products_data = data.get('products', [])

            if not products_data:
                return JsonResponse({"error": "Nenhum produto fornecido"}, status=400)

            # Validar dados usando o serializer
            serializer = ProductSerializer(data=products_data, many=True)
            if not serializer.is_valid():
                return JsonResponse({'error': 'Dados de produtos inválidos', 'details': serializer.errors}, status=400)
            
            # Manter os dados originais para enviar a ambas as plataformas
            original_data = {'products': products_data}
            
            # ETAPA 1: Enviar para o Moloni
            moloni_response = self._send_to_moloni(request, original_data)
            moloni_success = moloni_response.get('success', False)
            moloni_message = moloni_response.get('message', 'Erro desconhecido')
            moloni_metrics = moloni_response.get('metrics', {})
            
            # ETAPA 2: Enviar para o Shopify
            shopify_response = self._send_to_shopify(request, original_data)
            shopify_success = shopify_response.get('success', False)
            shopify_message = shopify_response.get('message', 'Erro desconhecido')
            shopify_metrics = shopify_response.get('metrics', {})
            
            # Combinar resultados
            combined_success = moloni_success or shopify_success
            combined_message = f"Moloni: {moloni_message} | Shopify: {shopify_message}"
            
            # Combinar métricas
            combined_metrics = {
                "moloni": moloni_metrics,
                "shopify": shopify_metrics
            }
            
            return JsonResponse({
                "success": combined_success,
                "message": combined_message,
                "metrics": combined_metrics
            })
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.exception(f"Erro ao sincronizar com ambas as plataformas: {str(e)}")
            
            return JsonResponse({
                'error': f'Erro ao sincronizar: {str(e)}',
                'traceback': error_trace
            }, status=500)
    
    def _send_to_moloni(self, request, data):
        """
        Envia os produtos para o Moloni através da view existente
        """
        try:
            # Obter a classe para a view do Moloni
            from apps.aitigos.views import SyncToMoloniView
            
            # Simular requisição POST para a view do Moloni
            view = SyncToMoloniView()
            view.setup(request)
            
            # Executar a view com os dados
            response = view.post(request)
            
            # Processar a resposta
            if response.status_code == 200:
                content = json.loads(response.content)
                return content
            else:
                return {
                    "success": False,
                    "message": f"Erro ao sincronizar com Moloni: {response.status_code}",
                    "metrics": {}
                }
                
        except Exception as e:
            logger.exception(f"Erro ao enviar para Moloni: {str(e)}")
            return {
                "success": False,
                "message": f"Exceção: {str(e)}",
                "metrics": {}
            }
    
    def _send_to_shopify(self, request, data):
        """
        Envia os produtos para o Shopify através da view correspondente
        """
        try:
            # Obter a classe para a view do Shopify
            view = SyncToShopifyView()
            view.setup(request)
            
            # Executar a view com os dados
            response = view.post(request)
            
            # Processar a resposta
            if response.status_code == 200:
                content = json.loads(response.content)
                return content
            else:
                return {
                    "success": False,
                    "message": f"Erro ao sincronizar com Shopify: {response.status_code}",
                    "metrics": {}
                }
                
        except Exception as e:
            logger.exception(f"Erro ao enviar para Shopify: {str(e)}")
            return {
                "success": False,
                "message": f"Exceção: {str(e)}",
                "metrics": {}
            }

class ProductEditView(LoginRequiredMixin, TemplateView):
    template_name = "product_edit.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        try:
            company = None
            if hasattr(self.request.user, 'profile') and self.request.user.profile.selected_moloni_company:
                company = self.request.user.profile.selected_moloni_company
                logger.info(f"Empresa selecionada: {company.name} (ID: {company.id}, Company ID: {company.company_id})")
            
            if company: 
                categories = Category.objects.filter(company=company).order_by('name')
                logger.info(f"Categorias encontradas: {categories.count()}")
                context['categories'] = [{"name": category.name, "id": category.category_id} for category in categories]
                
                suppliers = Supplier.objects.filter(company=company).order_by('name')
                logger.info(f"Fornecedores encontrados: {suppliers.count()}")
                context['suppliers'] = [{"name": supplier.name, "code": supplier.code.zfill(2)} for supplier in suppliers]
                
                try:
                    brands = Brand.objects.filter(company=company).order_by('name')
                    context['brands'] = [{"name": brand.name} for brand in brands]
                    logger.info(f"Marcas encontradas: {brands.count()}")
                except Exception as e:
                    logger.error(f"Erro ao buscar marcas: {str(e)}")
                    context['brands'] = []
                
                try:
                    colors = Color.objects.filter(company=company).order_by('name')
                    context['colors'] = [{"name": color.name, "code": color.code.zfill(3)} for color in colors]
                    logger.info(f"Cores encontradas: {colors.count()}")
                except Exception as e:
                    logger.error(f"Erro ao buscar cores: {str(e)}")
                    context['colors'] = []
                
                try:
                    sizes = Size.objects.filter(company=company).order_by('value')
                    context['sizes'] = [{"name": size.value,"value": size.value, "code": size.code.zfill(3)} for size in sizes]
                    logger.info(f"Tamanhos encontrados: {sizes.count()}")
                except Exception as e:
                    logger.error(f"Erro ao buscar tamanhos: {str(e)}")
                    context['sizes'] = []
                    
            else:
                logger.warning("Nenhuma empresa selecionada")
                context['categories'] = []
                context['suppliers'] = []
                context['brands'] = []
                context['colors'] = []
                context['sizes'] = []
                
        except Exception as e:
            logger.exception(f"Erro ao buscar dados para dropdowns: {str(e)}")
            context['categories'] = []
            context['suppliers'] = []
            context['brands'] = []
            context['colors'] = []
            context['sizes'] = []
        
        return context
 
    def _get_color_code_from_name(self, color_name, company):
        """
        Busca o código da cor pelo nome
        """
        try:
            if not color_name:
                return "000"
            
            color = Color.objects.filter(company=company, name=color_name).first()
            if color:
                return color.code.zfill(3)
            else:
                logger.warning(f"Cor não encontrada: {color_name}")
                # Retornar código vazio em vez de "000" para não sobrescrever
                return ""
        except Exception as e:
            logger.error(f"Erro ao buscar código da cor: {str(e)}")
            return ""
    
    def normalize_gender(self, gender_value):
        """
        Normaliza o valor do campo gender para os valores permitidos:
        - Homem, Senhora, Crianças
        """
        if not gender_value or not isinstance(gender_value, str):
            return 'Homem'
        
        normalized_value = gender_value.lower().strip()
        
        # Tratamento para "Homem"
        if normalized_value in ['homem', 'masculino', 'male', 'man', 'men']:
            return 'Homem'
        
        # Tratamento para "Senhora"
        if normalized_value in ['senhora', 'mulher', 'feminino', 'female', 'woman', 'women']:
            return 'Senhora'
        
        # Tratamento para "Crianças"
        if normalized_value in ['crianças', 'criancas', 'criança', 'crianca', 'kids', 'children', 'infantil', 'child']:
            return 'Crianças'
        
        # Se já está no formato correto
        if gender_value in ['Homem', 'Senhora', 'Crianças']:
            return gender_value
        
        return 'Homem'  # Default

    def determine_gender_from_category(self, category):
        """
        Determina o gender baseado na categoria do produto
        """
        if not category or not isinstance(category, str):
            return 'Homem'
        
        category_upper = category.upper()
        
        # Verificar termos femininos
        feminine_terms = ['WOMAN', 'WOMEN', 'SENHORA', 'FEMININO', 'MULHER', 'FEMALE', 'LADY', 'LADIES']
        if any(term in category_upper for term in feminine_terms):
            return 'Senhora'
        
        # Verificar termos infantis
        children_terms = ['KIDS', 'CHILDREN', 'CRIANÇA', 'CRIANÇAS', 'INFANTIL', 'CHILD', 'BABY', 'BEBÊ']
        if any(term in category_upper for term in children_terms):
            return 'Crianças'
        
        return 'Homem'
    
    def _get_size_code_from_value(self, size_value, company):
        try:
            if not size_value:
                return None
            
            size_str = str(size_value).strip()
            
            logger.debug(f"[_get_size_code_from_value] Buscando código para tamanho: '{size_str}'")
            
            size_by_value = Size.objects.filter(company=company, value=size_str).first()
            if size_by_value:
                code = size_by_value.code.zfill(3)
                logger.debug(f"[_get_size_code_from_value] Encontrado por VALUE: {size_str} -> código {code}")
                return code
            
            if size_str.isdigit() and len(size_str) <= 3:
                size_by_code = Size.objects.filter(company=company, code=size_str).first()
                if size_by_code:
                    code = size_by_code.code.zfill(3)
                    logger.debug(f"[_get_size_code_from_value] Encontrado por CODE: {size_str} -> código {code}")
                    return code
                else:
                    code = size_str.zfill(3)
                    logger.debug(f"[_get_size_code_from_value] Usando valor numérico como código: {size_str} -> {code}")
                    return code
            
            padded_code = size_str.zfill(3)
            size_by_padded = Size.objects.filter(company=company, code=padded_code).first()
            if size_by_padded:
                logger.debug(f"[_get_size_code_from_value] Encontrado por código com padding: {size_str} -> {padded_code}")
                return padded_code
            
            logger.warning(f"[_get_size_code_from_value] Tamanho não encontrado: '{size_str}'")
            return None
            
        except Exception as e:
            logger.error(f"[_get_size_code_from_value] Erro ao buscar tamanho: {str(e)}")
            return None
    
    def _generate_barcode_with_season(self, season, supplier_code, sequential_number, color_code, size_code):
        """
        Gera código de barras com season preservada: Season(2) + Supplier(2) + Sequential(3) + Color(3) + Size(3)
        """
        try:
            season_str = str(season).zfill(2)
            supplier = str(supplier_code).zfill(2)
            sequential = str(100 + int(sequential_number)).zfill(3)
            color = str(color_code).zfill(3)
            size = str(size_code).zfill(3)
            
            barcode = f"{season_str}{supplier}{sequential}{color}{size}"
            logger.debug(f"Código de barras gerado: {season_str}-{supplier}-{sequential}-{color}-{size} = {barcode}")
            
            return barcode
        except Exception as e:
            logger.error(f"Erro ao gerar código de barras: {str(e)}")
            return ""
    
    def _extract_sequential_from_reference(self, reference):
        """
        Extrai o número sequencial da referência (formato: XXX.N)
        """
        try:
            if not reference:
                return 1
            
            parts = reference.split('.')
            if len(parts) > 1:
                return int(parts[1])
            else:
                return 1
        except:
            return 1
    
    def _update_variant_codes_and_barcode(self, variant_data, supplier_name, company, original_variant=None):
        try:
            logger.debug(f"[_update_variant_codes_and_barcode] Processando variante: {variant_data.get('reference', 'SEM_REF')}")
            
            supplier_code = "00"
            if supplier_name:
                found_supplier = Supplier.objects.filter(company=company, name=supplier_name).first()
                if found_supplier:
                    supplier_code = found_supplier.code.zfill(2)
                    logger.debug(f"[_update_variant_codes_and_barcode] Fornecedor: {supplier_name} -> {supplier_code}")
                else:
                    if original_variant and original_variant.get('supplier_code'):
                        supplier_code = str(original_variant['supplier_code']).zfill(2)
                    logger.debug(f"[_update_variant_codes_and_barcode] Fornecedor não encontrado, usando: {supplier_code}")
            
            color_code = "000"
            if variant_data.get('color_name'):
                found_color = Color.objects.filter(company=company, name=variant_data['color_name']).first()
                if found_color:
                    color_code = found_color.code.zfill(3)
                    variant_data['color_code'] = color_code
                    logger.debug(f"[_update_variant_codes_and_barcode] Cor: {variant_data['color_name']} -> {color_code}")
                else:
                    # Manter código original se existir
                    if original_variant and original_variant.get('color_code'):
                        color_code = str(original_variant['color_code']).zfill(3)
                        variant_data['color_code'] = color_code
                    logger.debug(f"[_update_variant_codes_and_barcode] Cor não encontrada, usando: {color_code}")
            elif variant_data.get('color_code'):
                color_code = str(variant_data['color_code']).zfill(3)
                variant_data['color_code'] = color_code
            
            size_input = variant_data.get('size', '')
            logger.debug(f"[_update_variant_codes_and_barcode] Tamanho recebido: '{size_input}'")
            
            if size_input:
                # Buscar código do tamanho na BD
                size_code = self._get_size_code_from_value(size_input, company)
                
                if size_code:
                    # ⚠️ IMPORTANTE: NÃO alterar o valor do tamanho, só usar o código para barcode
                    logger.debug(f"[_update_variant_codes_and_barcode] Tamanho: '{size_input}' mantido, código: {size_code}")
                    # variant_data['size'] permanece como está (XL, M, etc)
                    # Só usamos size_code para o código de barras
                else:
                    # Se não encontrou código, manter valor original
                    size_code = "000"
                    logger.debug(f"[_update_variant_codes_and_barcode] Código não encontrado para '{size_input}', usando padrão: {size_code}")
            else:
                size_code = "000"
                logger.debug(f"[_update_variant_codes_and_barcode] Tamanho vazio, usando código padrão: {size_code}")
            
            sequential_number = self._extract_sequential_from_reference(variant_data.get('reference', ''))
            
            # Extrair season do código original
            season = "23"
            if original_variant and original_variant.get('barcode') and len(str(original_variant['barcode'])) >= 2:
                try:
                    season = str(original_variant['barcode'])[:2]
                    logger.debug(f"[_update_variant_codes_and_barcode] Season extraída: {season}")
                except:
                    season = "23"
            
            # Gerar código de barras
            barcode = self._generate_barcode_with_season(season, supplier_code, sequential_number, color_code, size_code)
            variant_data['barcode'] = barcode
            
            logger.debug(f"[_update_variant_codes_and_barcode] Código de barras gerado: {barcode}")
            logger.debug(f"[_update_variant_codes_and_barcode] Variante final - Tamanho: '{variant_data.get('size')}', Código: {size_code}")
            
        except Exception as e:
            logger.error(f"[_update_variant_codes_and_barcode] Erro: {str(e)}")
            # Em caso de erro, manter dados originais
            if original_variant:
                variant_data['color_code'] = original_variant.get('color_code', variant_data.get('color_code', '000'))
                variant_data['size'] = original_variant.get('size', variant_data.get('size', ''))
                variant_data['barcode'] = original_variant.get('barcode', variant_data.get('barcode', ''))

    def put(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            action = data.get('action', '')

            products_data = data.get('products', [])
            
            if products_data:
                serializer = ProductSerializer(data=products_data, many=True)
                if not serializer.is_valid():
                    return JsonResponse({'error': 'Dados de produtos inválidos', 'details': serializer.errors}, status=400)
                products_data = serializer.validated_data
            
            products_df, variants_df, _ = self._json_to_dataframes(products_data)
            
            if action == 'edit_product':
                product_index = data.get('productIndex', -1)
                product_data = data.get('product', {})
                
                logger.info(f"[MODO SIMPLES] Editando produto {product_index}")
                
                if product_index < 0:
                    return JsonResponse({'error': 'Índice de produto inválido'}, status=400)
                
                if not product_data:
                    return JsonResponse({'error': 'Dados do produto não fornecidos'}, status=400)
                
                company = None
                if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
                    company = request.user.profile.selected_moloni_company
                
                if company and 'details' in product_data:
                    supplier_name = product_data.get('supplier', '')
                    
                    for i, variant in enumerate(product_data.get('details', [])):
                        try:
                            self._update_variant_codes_and_barcode(variant, supplier_name, company, None)
                        except Exception as e:
                            logger.warning(f"Erro ao processar variante {i}: {str(e)}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Produto atualizado com sucesso',
                    'product': product_data
                })
                
            elif action == 'delete_variant':
                product_index = data.get('productIndex', -1)
                variant_index = data.get('variantIndex', -1)
                
                logger.info(f"Solicitação para excluir variante {variant_index} do produto {product_index}")
                
                # Usar a nova função com reindexação
                variants_df = self._delete_variant_with_reindexing(
                    product_index, variant_index, variants_df)
                
                message = 'Variante excluída e referências reindexadas com sucesso'
                
            elif action == 'delete_product':
                product_index = data.get('productIndex', -1)
                products_df, variants_df = self._delete_product_df(
                    product_index, products_df, variants_df)
                message = 'Produto excluído com sucesso'
                
            elif action == 'update_barcode_prefix':
                barcode_prefix = data.get('barcodePrefix', '')
                if not barcode_prefix or len(barcode_prefix) != 2 or not barcode_prefix.isdigit():
                    return JsonResponse({'error': 'Prefixo de código de barras inválido'}, status=400)
                    
                products_df, variants_df = self._update_barcode_prefix_df(
                    barcode_prefix, products_df, variants_df)
                count = len(variants_df)
                message = f'Prefixo atualizado com sucesso em {count} códigos de barras'
                
            else:
                return JsonResponse({'error': 'Ação não reconhecida'}, status=400)
            
            processed_products = self._dataframes_to_json(products_df, variants_df)
            
            return JsonResponse({
                'success': True,
                'message': message,
                'products': processed_products
            })
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
        except Exception as e:
            return JsonResponse({
                'error': f'Erro ao processar requisição: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
    
    def _delete_variant_with_reindexing(self, product_index, variant_index, variants_df):
        try:
            if product_index < 0 or variant_index < 0:
                raise ValueError('Índices inválidos')

            product_variants = variants_df[variants_df['product_id'] == product_index].copy()

            if variant_index >= len(product_variants):
                raise ValueError('Índice de variante fora dos limites')
            
            logger.info(f"Excluindo variante {variant_index} do produto {product_index}")
            logger.info(f"Total de variantes antes da exclusão: {len(product_variants)}")

            if len(product_variants) > 0:
                first_reference = product_variants.iloc[0]['reference']
                material_code = first_reference.split('.')[0] if '.' in first_reference else first_reference
            else:
                material_code = ""

            product_variants = product_variants.drop(product_variants.index[variant_index]).reset_index(drop=True)
            
            logger.info(f"Variantes restantes após exclusão: {len(product_variants)}")

            for idx, row_idx in enumerate(product_variants.index):
                new_sequence = idx + 1
                old_reference = product_variants.loc[row_idx, 'reference']
                new_reference = f"{material_code}.{new_sequence}"
                
                product_variants.loc[row_idx, 'reference'] = new_reference
                
                product_variants.loc[row_idx, 'variant_id'] = idx
                
                old_barcode = product_variants.loc[row_idx, 'barcode']
                
                if old_barcode and len(str(old_barcode)) >= 13:
                    try:
                        barcode_str = str(old_barcode).zfill(13)
                        season = barcode_str[:2]           # Primeiros 2: season
                        supplier = barcode_str[2:4]        # Próximos 2: supplier
                        # sequential = barcode_str[4:7]    # Próximos 3: sequential (será recalculado)
                        color = barcode_str[7:10]          # Próximos 3: color
                        size = barcode_str[10:13]          # Últimos 3: size
                        
                        new_sequential = str(100 + new_sequence).zfill(3)
                        
                        # Montar novo código de barras
                        new_barcode = f"{season}{supplier}{new_sequential}{color}{size}"
                        product_variants.loc[row_idx, 'barcode'] = new_barcode
                        
                        logger.debug(f"Referência reindexada: {old_reference} -> {new_reference}")
                        logger.debug(f"Código de barras reindexado: {old_barcode} -> {new_barcode}")
                        
                    except Exception as e:
                        logger.warning(f"Erro ao reindexar código de barras para {new_reference}: {str(e)}")
                        # Se houver erro, manter código de barras original
                        pass

            # Obter variantes dos outros produtos (não afetadas)
            other_variants = variants_df[variants_df['product_id'] != product_index]

            # Concatenar as variantes reindexadas com as outras variantes
            updated_variants_df = pd.concat([other_variants, product_variants], ignore_index=True)
            
            logger.info(f"Reindexação concluída. Variantes finais do produto: {len(product_variants)}")
            
            return updated_variants_df

        except Exception as e:
            logger.error(f"Erro ao excluir e reindexar variante: {str(e)}")
            raise

    def _json_to_dataframes(self, products_data):
        return AitigosView._json_to_dataframes(self, products_data)
    
    def _dataframes_to_json(self, products_df, variants_df):
        return AitigosView._dataframes_to_json(self, products_df, variants_df)
    
    def _edit_product_df(self, product_index, product_data, products_df, variants_df):
        return AitigosView._edit_product_df(self, product_index, product_data, products_df, variants_df)

class ProductComparisonView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            products_data = data.get('products', [])
            platform = data.get('platform', 'moloni')
            
            if not products_data:
                return JsonResponse({"error": "Nenhum produto fornecido"}, status=400)
            
            # Validar dados
            serializer = ProductSerializer(data=products_data, many=True)
            if not serializer.is_valid():
                return JsonResponse({
                    'error': 'Dados de produtos inválidos', 
                    'details': serializer.errors
                }, status=400)
            
            products_data = serializer.validated_data
                        
            if platform == 'moloni':
                # Obter empresa Moloni
                company = self._get_moloni_company(request)
                if not company:
                    return JsonResponse({
                        "error": "É necessário selecionar uma empresa Moloni primeiro"
                    }, status=400)
                
                # Fazer comparação com Moloni
                comparison_result = ProductComparisonService.compare_with_moloni(
                    products_data, company
                )
                
            elif platform == 'shopify':
                # Obter loja Shopify
                try:
                    from apps.shopify.models import Shopify
                    shopify_store = Shopify.objects.filter(users=request.user).first()
                    if not shopify_store:
                        return JsonResponse({
                            "error": "Não há lojas Shopify associadas a este usuário"
                        }, status=400)
                    
                    # Fazer comparação com Shopify
                    comparison_result = ProductComparisonService.compare_with_shopify(
                        products_data, shopify_store
                    )
                    
                except Exception as e:
                    return JsonResponse({
                        "error": f"Erro ao buscar loja Shopify: {str(e)}"
                    }, status=500)
            
            else:
                return JsonResponse({
                    "error": "Plataforma não suportada"
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'platform': platform,
                'comparison': comparison_result
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
        except Exception as e:
            logger.exception(f"Erro na comparação de produtos: {str(e)}")
            return JsonResponse({
                'error': f'Erro na comparação: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
    
    def _get_moloni_company(self, request):
        """Obter empresa Moloni do usuário"""
        if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
            return request.user.profile.selected_moloni_company
        
        company_id = request.session.get('selected_company_id')
        if company_id:
            try:
                from apps.moloni.models import Moloni
                return Moloni.objects.get(company_id=company_id)
            except Moloni.DoesNotExist:
                pass
        
        return None


class FilteredSyncView(LoginRequiredMixin, View):
    """
    View para sincronizar apenas produtos filtrados (sem conflitos)
    """
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            products_data = data.get('products', [])
            platform = data.get('platform', 'moloni')
            safe_indices = data.get('safe_indices', [])
            
            if not products_data:
                return JsonResponse({"error": "Nenhum produto fornecido"}, status=400)
            
            # Validar dados
            serializer = ProductSerializer(data=products_data, many=True)
            if not serializer.is_valid():
                return JsonResponse({
                    'error': 'Dados de produtos inválidos',
                    'details': serializer.errors
                }, status=400)
            
            products_data = serializer.validated_data
            
            filtered_products = ProductComparisonService.filter_products_for_insertion(
                products_data, safe_indices
            )
            
            if not filtered_products:
                return JsonResponse({
                    "error": "Nenhum produto seguro para inserir foi encontrado"
                }, status=400)
            
            if platform == 'moloni':
                view = SyncToMoloniView()
                view.setup(request)
                
                request._body = json.dumps({'products': filtered_products}).encode('utf-8')
                
                return view.post(request)
                
            elif platform == 'shopify':
                view = SyncToShopifyView()
                view.setup(request)
                
                request._body = json.dumps({'products': filtered_products}).encode('utf-8')
                
                return view.post(request)
                
            else:
                return JsonResponse({
                    "error": "Plataforma não suportada"
                }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
        except Exception as e:
            logger.exception(f"Erro na sincronização filtrada: {str(e)}")
            return JsonResponse({
                'error': f'Erro na sincronização: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
