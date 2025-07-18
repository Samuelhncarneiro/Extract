# apps/product_moloni/services.py
import logging
import requests
import json
import time
import threading

from django.db import transaction, connection
from django.utils import timezone
from django.core.cache import cache

from typing import Dict, List, Any, Tuple, Optional
from django.conf import settings
from apps.sechic.models import Category, Supplier
from apps.product_moloni.models import Product, ProductVariant
from apps.sechic.services import MoloniService
from apps.moloni.models import Moloni   

logger = logging.getLogger(__name__)

class ProductMoloniService:
    @staticmethod
    def _safe_moloni_request(url, company, method='POST', data=None):
        try:
            if data is None:
                data = {}
            
            return MoloniService._make_authenticated_request_encode(
                url, company, method=method, form_data=data
            )
            
        except Exception as e:
            logger.exception(f"Erro na requisição segura: {str(e)}")
            return False, None, f"Erro inesperado: {str(e)}"

    @staticmethod
    def get_product_details(company, product_id):
        try:
            url = "https://api.moloni.pt/v1/products/getOne/"
            data = {"product_id": product_id}
            
            success, product_data, error = MoloniService._make_authenticated_request_encode(
                url, company, 'POST', data
            )
            
            if success and product_data:
                return product_data
            else:
                logger.warning(f"Erro ao obter detalhes do produto {product_id}: {error}")
                return None
                
        except Exception as e:
            logger.exception(f"Erro ao obter detalhes do produto {product_id}: {str(e)}")
            return None

    @staticmethod
    def _get_category_products_list(company, category_id):
        try:
            count_url = "https://api.moloni.pt/v1/products/count/"
            count_data = {"category_id": category_id}
            
            count_success, count_response, count_error = MoloniService._make_authenticated_request_encode(
                count_url, company, 'POST', count_data
            )
            
            if not count_success:
                logger.warning(f"Erro ao obter contagem da categoria {category_id}: {count_error}")
                return []
            
            total_products = int(count_response.get("count", 0))
            
            if total_products == 0:
                return []
            
            all_products = []
            batch_size = 50 
            offset = 0
            
            while offset < total_products:
                params = {
                    "category_id": category_id,
                    "offset": offset,
                    "qty": batch_size,
                    "with_invisible": 1  
                }
                
                url = "https://api.moloni.pt/v1/products/getAll/"
                success, products_data, error = MoloniService._make_authenticated_request_encode(
                    url, company, 'POST', params
                )
                
                if not success or not products_data:
                    logger.warning(f"Erro ao buscar produtos da categoria {category_id}, offset {offset}: {error}")
                    break
                
                all_products.extend(products_data)
                offset += len(products_data)
                
                if len(products_data) < batch_size:
                    break
                
                time.sleep(0.2)
            
            logger.info(f"Categoria {category_id}: obtidos {len(all_products)} produtos")
            return all_products
            
        except Exception as e:
            logger.exception(f"Erro ao obter lista de produtos da categoria {category_id}: {str(e)}")
            return []

    @staticmethod
    def fetch_and_store_products(company, force_delete: bool = False) -> Tuple[bool, str, Dict[str, int]]:
        logger.info(f"Iniciando sincronização DETALHADA de produtos do Moloni - Empresa: {company.name}")
        start_time = time.time()
        
        moloni_product_ids = set()
        stats = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "total": 0,
            "errors": 0
        }
        
        try:
            categories = Category.objects.filter(company=company)
            category_ids = [category.category_id for category in categories]
            
            if not category_ids:
                logger.warning("Nenhuma categoria encontrada.")
                category_ids = [0]
            
            found_any_products = False
            
            for category_id in category_ids:
                try:
                    logger.info(f"Processando categoria ID {category_id}")
                    
                    # Primeiro, obter lista de produtos
                    products_list = ProductMoloniService._get_category_products_list(company, category_id)
                    
                    if not products_list:
                        continue
                    
                    found_any_products = True
                    stats["total"] += len(products_list)
                    
                    # Processar cada produto individualmente para obter detalhes completos
                    for basic_product in products_list:
                        try:
                            product_id = basic_product.get("product_id")
                            if not product_id:
                                continue
                            
                            moloni_product_ids.add(product_id)
                            
                            # Obter detalhes completos do produto
                            detailed_product = ProductMoloniService.get_product_details(company, product_id)
                            
                            if detailed_product:
                                # Usar dados detalhados que incluem supplier
                                product, created = ProductMoloniService.create_or_update_product(
                                    detailed_product, company
                                )
                                
                                if product:
                                    if created:
                                        stats["added"] += 1
                                    else:
                                        stats["updated"] += 1
                                else:
                                    stats["errors"] += 1
                            else:
                                # Fallback: usar dados básicos se não conseguir obter detalhes
                                product, created = ProductMoloniService.create_or_update_product(
                                    basic_product, company
                                )
                                
                                if product:
                                    if created:
                                        stats["added"] += 1
                                    else:
                                        stats["updated"] += 1
                                else:
                                    stats["errors"] += 1
                            
                            # Pausa pequena para não sobrecarregar a API
                            time.sleep(0.1)
                            
                        except Exception as e:
                            logger.exception(f"Erro ao processar produto {product_id}: {str(e)}")
                            stats["errors"] += 1
                    
                except Exception as e:
                    logger.exception(f"Erro ao processar categoria {category_id}: {str(e)}")
                    stats["errors"] += 1
            
            # Limpeza de produtos obsoletos
            if not found_any_products or stats["total"] == 0:
                logger.info("NENHUM produto encontrado no Moloni.")
                local_products = Product.objects.filter(company=company)
                local_count = local_products.count()
                
                if local_count > 0 and force_delete:
                    logger.info(f"REMOVENDO TODOS os {local_count} produtos locais")
                    local_products.delete()
                    stats["deleted"] = local_count
                    message = f"Moloni vazio: removidos {local_count} produtos locais"
                else:
                    message = f"Moloni vazio: {local_count} produtos locais mantidos"
            
            elif force_delete and moloni_product_ids:
                products_to_delete = Product.objects.filter(company=company).exclude(
                    product_id__in=moloni_product_ids
                )
                deleted_count = products_to_delete.count()
                
                if deleted_count > 0:
                    logger.info(f"Excluindo {deleted_count} produtos obsoletos")
                    products_to_delete.delete()
                    stats["deleted"] = deleted_count
            
            # Limpar cache
            cache.delete('products_count')
            cache.delete(f'products_count_{company.id}')
            
            # Mensagem final
            if not 'message' in locals():
                message = "Produtos sincronizados com sucesso"
                if stats["added"] > 0:
                    message += f": {stats['added']} adicionados"
                if stats["updated"] > 0:
                    message += f", {stats['updated']} atualizados"
                if stats["deleted"] > 0:
                    message += f", {stats['deleted']} excluídos"
                if stats["errors"] > 0:
                    message += f", {stats['errors']} erros"
            
            elapsed_time = time.time() - start_time
            logger.info(f"Sincronização detalhada concluída em {elapsed_time:.2f} segundos")
            logger.info(f"Stats finais: {stats}")
            
            return (True, message, stats)
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.exception(f"Erro na sincronização detalhada após {elapsed_time:.2f}s: {str(e)}")
            return (False, f"Erro na sincronização: {str(e)}", stats)

    @staticmethod
    def clean_field_data(value, max_length=None, field_name="campo"):
        if value is None:
            return ""
        
        value = str(value).strip()
        
        if max_length is None:
            return value
        
        if len(value) > max_length:
            logger.warning(f"{field_name} truncado de {len(value)} para {max_length} caracteres. Valor original: {value[:50]}...")
            return value[:max_length]
        
        return value
    
    @staticmethod
    def safe_decimal_conversion(value, default=0):
        """Converte valor para decimal de forma segura"""
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Erro ao converter valor para decimal: {value}. Usando {default}")
            return default
    
    @staticmethod
    def safe_int_conversion(value, default=None):
        """Converte valor para inteiro de forma segura"""
        try:
            if value is None or value == "":
                return default
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Erro ao converter valor para inteiro: {value}. Usando {default}")
            return default

    @staticmethod
    def extract_ean_from_product_data(product_data):
        """Extrai EAN/código de barras dos dados do produto"""
        # Primeiro, verificar se existe campo EAN direto
        ean = product_data.get("ean", "")
        
        if ean:
            return ProductMoloniService.clean_field_data(ean, max_length=50, field_name="EAN")
        
        # Se não, verificar nas propriedades
        properties = product_data.get("properties", [])
        if properties and isinstance(properties, list):
            for prop in properties:
                if isinstance(prop, dict):
                    prop_name = prop.get("name", "").lower()
                    if prop_name in ["ean", "ean13", "ean8", "código de barras", "codigo de barras", "barcode"]:
                        ean_value = prop.get("value", "")
                        if ean_value:
                            return ProductMoloniService.clean_field_data(ean_value, max_length=50, field_name="EAN")
        
        return ""

    @staticmethod
    def create_or_update_product(product_data, company):
        try:
            product_id = ProductMoloniService.safe_int_conversion(product_data.get("product_id"))
            
            if not product_id:
                logger.warning(f"Product ID inválido: {product_data.get('product_id')}")
                return None, False
            
            # Limpar e validar dados básicos
            reference = ProductMoloniService.clean_field_data(
                product_data.get("reference", ""), max_length=100, field_name="Reference"
            )
            
            name = ProductMoloniService.clean_field_data(
                product_data.get("name", ""), max_length=255, field_name="Name"
            )
            
            summary = ProductMoloniService.clean_field_data(
                product_data.get("summary", ""), field_name="Summary"
            )
            
            ean = ProductMoloniService.extract_ean_from_product_data(product_data)
            
            price = ProductMoloniService.safe_decimal_conversion(product_data.get("price", 0))
            stock = ProductMoloniService.safe_decimal_conversion(product_data.get("stock", 0))
            
            type_value = ProductMoloniService.safe_int_conversion(product_data.get("type", 1), default=1)
            unit_id = ProductMoloniService.safe_int_conversion(product_data.get("unit_id"))
            
            has_stock = bool(product_data.get("has_stock", False))
            
            # Tentar obter produto existente
            try:
                product = Product.objects.get(product_id=product_id)
                created = False
            except Product.DoesNotExist:
                product = Product(product_id=product_id, company=company)
                created = True
            
            product.reference = reference
            product.name = name
            product.summary = summary
            product.ean = ean
            product.price = price
            product.stock = stock
            product.type = type_value
            product.unit_id = unit_id
            product.has_stock = has_stock
            product.company = company
            
            product.save()
            
            ProductMoloniService.associate_category(product, product_data, company)
            
            ProductMoloniService.associate_supplier(product, product_data, company)
            
            return product, created
            
        except Exception as e:
            logger.exception(f"Erro ao criar/atualizar produto {product_data.get('product_id')}: {str(e)}")
            return None, False
    
    @staticmethod
    def associate_category(product, product_data, company):
        try:
            if "category" in product_data and product_data["category"]:
                category_data = product_data["category"]
                category_id = ProductMoloniService.safe_int_conversion(category_data.get("category_id"))
                
                if category_id:
                    category_name = ProductMoloniService.clean_field_data(
                        category_data.get("name", ""), max_length=255, field_name="Category Name"
                    )
                    
                    category, _ = Category.objects.get_or_create(
                        category_id=category_id,
                        company=company,
                        defaults={"name": category_name}
                    )
                    product.category = category
                    product.save(update_fields=['category'])
                    
        except Exception as e:
            logger.warning(f"Erro ao associar categoria ao produto {product.product_id}: {str(e)}")
    
    @staticmethod
    def associate_supplier(product, product_data, company):
        try:
            logger.debug(f"Tentando associar supplier ao produto {product.product_id}")
            
            supplier_data = None
            
            if "suppliers" in product_data and product_data["suppliers"]:
                suppliers_array = product_data["suppliers"]
                if isinstance(suppliers_array, list) and len(suppliers_array) > 0:
                    first_supplier = suppliers_array[0]
                    supplier_id = first_supplier.get("supplier_id")
                    
                    if supplier_id:
                        logger.debug(f"Supplier encontrado no array: supplier_id={supplier_id}")
                        
                        supplier_name = ProductMoloniService.get_supplier_name_by_id(company, supplier_id)
                        
                        supplier_data = {
                            "supplier_id": supplier_id,
                            "name": supplier_name or f"Fornecedor {supplier_id}"
                        }
                    else:
                        logger.debug(f"Supplier_id inválido no array: {first_supplier}")
                else:
                    logger.debug("Array 'suppliers' vazio ou inválido")
            
            elif "supplier" in product_data and product_data["supplier"]:
                supplier_data = product_data["supplier"]
                logger.debug(f"Supplier encontrado como objeto: {supplier_data}")
            
            elif "supplier_id" in product_data and product_data.get("supplier_id"):
                supplier_id = product_data["supplier_id"]
                supplier_name = ProductMoloniService.get_supplier_name_by_id(company, supplier_id)
                supplier_data = {
                    "supplier_id": supplier_id,
                    "name": supplier_name or f"Fornecedor {supplier_id}"
                }
                logger.debug(f"Supplier_id encontrado diretamente: {supplier_id}")
            
            else:
                logger.debug(f"Nenhum supplier encontrado para produto {product.product_id}")
                return
            
            if supplier_data:
                supplier_id = ProductMoloniService.safe_int_conversion(supplier_data.get("supplier_id"))
                
                if supplier_id:
                    supplier_name = ProductMoloniService.clean_field_data(
                        supplier_data.get("name", f"Fornecedor {supplier_id}"), 
                        max_length=255, 
                        field_name="Supplier Name"
                    )
                    
                    supplier, created = Supplier.objects.get_or_create(
                        supplier_id=supplier_id,
                        company=company,
                        defaults={"name": supplier_name}
                    )
                    
                    if not created and supplier.name != supplier_name:
                        supplier.name = supplier_name
                        supplier.save()
                    
                    product.supplier = supplier
                    product.save(update_fields=['supplier'])
                    
                    logger.info(f"Supplier associado ao produto {product.product_id}: {supplier_name} (ID: {supplier_id})")
                else:
                    logger.debug(f"Supplier ID inválido: {supplier_data}")
            
        except Exception as e:
            logger.warning(f"Erro ao associar fornecedor ao produto {product.product_id}: {str(e)}")

    @staticmethod
    def get_supplier_name_by_id(company, supplier_id):
        try:
            try:
                from apps.sechic.models import Supplier
                local_supplier = Supplier.objects.get(supplier_id=supplier_id, company=company)
                return local_supplier.name
            except Supplier.DoesNotExist:
                pass
            
            url = "https://api.moloni.pt/v1/suppliers/getOne/"
            data = {"supplier_id": supplier_id}
            
            success, supplier_response, error = MoloniService._make_authenticated_request_encode(
                url, company, 'POST', data
            )
            
            if success and supplier_response:
                supplier_name = supplier_response.get("name", f"Fornecedor {supplier_id}")
                logger.debug(f"Nome do supplier {supplier_id} obtido da API: {supplier_name}")
                return supplier_name
            else:
                logger.warning(f"Erro ao obter nome do supplier {supplier_id}: {error}")
                return None
                
        except Exception as e:
            logger.warning(f"Erro ao obter nome do supplier {supplier_id}: {str(e)}")
            return None

class BackgroundSyncService:
    @staticmethod
    def start_sync(company, force_delete: bool = False, user_id: Optional[int] = None) -> tuple[bool, str]:
        sync_key = f'sync_progress_{company.id}'
        
        current_sync = cache.get(sync_key)
        if current_sync and current_sync.get('status') in ['started', 'processing']:
            return False, "Sincronização já em andamento"
        
        progress_data = {
            'status': 'started',
            'progress': 0,
            'total_categories': 0,
            'current_category': None,
            'current_batch': 0,
            'total_batches': 0,
            'stats': {
                'added': 0,
                'updated': 0,
                'deleted': 0,
                'errors': 0,
                'total_moloni': 0
            },
            'start_time': timezone.now().isoformat(),
            'user_id': user_id,
            'force_delete': force_delete,
            'messages': []
        }
        
        cache.set(sync_key, progress_data, timeout=7200)
        
        thread = threading.Thread(
            target=BackgroundSyncService._sync_products_background,
            args=(company, force_delete, sync_key),
            daemon=True
        )
        thread.start()
        
        return True, "Sincronização iniciada em background"
    
    @staticmethod
    def _sync_products_background(company, force_delete: bool, sync_key: str):
        """Executa a sincronização em background"""
        try:
            logger.info(f"Iniciando sincronização em background - Empresa: {company.name}")
            
            # Atualizar status
            BackgroundSyncService._update_progress(sync_key, {
                'status': 'processing',
                'message': 'Obtendo categorias...'
            })
            
            # Obter categorias
            categories = list(Category.objects.filter(company=company))
            if not categories:
                categories = [{'category_id': 0, 'name': 'Default'}]
                logger.warning("Nenhuma categoria encontrada, usando categoria padrão")
            
            total_categories = len(categories)
            moloni_product_ids = set()
            
            BackgroundSyncService._update_progress(sync_key, {
                'total_categories': total_categories,
                'message': f'Processando {total_categories} categorias...'
            })
            
            # Processar cada categoria
            for category_index, category in enumerate(categories):
                try:
                    category_id = category.category_id if hasattr(category, 'category_id') else category['category_id']
                    category_name = category.name if hasattr(category, 'name') else category['name']
                    
                    # Verificar se deve continuar
                    if not BackgroundSyncService._should_continue(sync_key):
                        logger.info("Sincronização cancelada pelo usuário")
                        return
                    
                    BackgroundSyncService._update_progress(sync_key, {
                        'current_category': {
                            'id': category_id,
                            'name': category_name,
                            'index': category_index + 1,
                            'total': total_categories
                        },
                        'progress': int((category_index / total_categories) * 90),  # Deixar 10% para cleanup
                        'message': f'Processando categoria: {category_name}'
                    })
                    
                    # Processar categoria
                    category_stats = BackgroundSyncService._process_category(
                        company, category_id, category_name, sync_key, moloni_product_ids
                    )
                    
                    # Atualizar stats globais
                    BackgroundSyncService._update_stats(sync_key, category_stats)
                    
                except Exception as e:
                    logger.exception(f"Erro ao processar categoria {category_id}: {str(e)}")
                    BackgroundSyncService._add_message(sync_key, f"Erro na categoria {category_id}: {str(e)}", 'error')
            
            # Cleanup de produtos obsoletos
            if force_delete:
                BackgroundSyncService._update_progress(sync_key, {
                    'progress': 90,
                    'message': 'Verificando produtos obsoletos...'
                })
                
                # Se não há produtos no Moloni, remover todos os produtos locais
                if not moloni_product_ids:
                    local_products_count = Product.objects.filter(company=company).count()
                    if local_products_count > 0:
                        logger.info(f"Nenhum produto no Moloni. Removendo {local_products_count} produtos locais.")
                        BackgroundSyncService._add_message(sync_key, f"Removendo todos os produtos locais ({local_products_count})", 'info')
                        Product.objects.filter(company=company).delete()
                        deleted_count = local_products_count
                    else:
                        deleted_count = 0
                else:
                    # Se há produtos no Moloni, remover apenas os que não existem mais
                    deleted_count = BackgroundSyncService._cleanup_obsolete_products(company, moloni_product_ids, sync_key)
                
                BackgroundSyncService._update_stats(sync_key, {'deleted': deleted_count})
            
            BackgroundSyncService._finalize_sync(sync_key)
            
        except Exception as e:
            logger.exception(f"Erro na sincronização em background: {str(e)}")
            BackgroundSyncService._update_progress(sync_key, {
                'status': 'error',
                'message': f'Erro na sincronização: {str(e)}',
                'progress': 0
            })

    @staticmethod
    def _process_category(company, category_id: int, category_name: str, sync_key: str, moloni_product_ids: set) -> Dict[str, int]:
        """Processa uma categoria específica"""
        category_stats = {'added': 0, 'updated': 0, 'errors': 0, 'total_moloni': 0}
        
        try:
            # Obter contagem de produtos
            count_url = "https://api.moloni.pt/v1/products/count/"
            count_data = {"category_id": category_id}
            
            count_success, count_response, count_error = MoloniService._make_authenticated_request_encode(
                count_url, company, 'POST', count_data
            )
            
            if not count_success:
                logger.warning(f"Erro ao obter contagem da categoria {category_id}: {count_error}")
                BackgroundSyncService._add_message(sync_key, f"Erro ao obter contagem da categoria {category_name}: {count_error}", 'warning')
                return category_stats
            
            total_products = int(count_response.get("count", 0))
            category_stats['total_moloni'] = total_products
            
            if total_products == 0:
                BackgroundSyncService._add_message(sync_key, f"Categoria {category_name}: 0 produtos", 'info')
                return category_stats
            
            logger.info(f"Categoria {category_name}: {total_products} produtos para processar")
            
            # Processar em lotes
            batch_size = 20  # Lotes pequenos para evitar timeout
            total_batches = (total_products + batch_size - 1) // batch_size
            offset = 0
            
            BackgroundSyncService._update_progress(sync_key, {
                'total_batches': total_batches,
                'current_batch': 0
            })
            
            for batch_num in range(total_batches):
                try:
                    # Verificar se deve continuar
                    if not BackgroundSyncService._should_continue(sync_key):
                        break
                    
                    BackgroundSyncService._update_progress(sync_key, {
                        'current_batch': batch_num + 1,
                        'message': f'Categoria {category_name}: lote {batch_num + 1}/{total_batches}'
                    })
                    
                    # Buscar produtos do lote
                    params = {
                        "category_id": category_id,
                        "offset": offset,
                        "qty": batch_size
                    }
                    
                    url = "https://api.moloni.pt/v1/products/getAll/"
                    success, products_data, error = MoloniService._make_authenticated_request_encode(
                        url, company, 'POST', params
                    )
                    
                    if not success or not products_data:
                        logger.warning(f"Erro ao buscar lote {batch_num + 1}: {error}")
                        break
                    
                    # Processar produtos do lote
                    batch_stats = BackgroundSyncService._process_product_batch(
                        products_data, company, moloni_product_ids
                    )
                    
                    category_stats['added'] += batch_stats['added']
                    category_stats['updated'] += batch_stats['updated']
                    category_stats['errors'] += batch_stats['errors']
                    
                    offset += len(products_data)
                    
                    # Pausa entre lotes
                    time.sleep(0.1)
                    
                    # Se o lote retornou menos produtos que o esperado, terminar
                    if len(products_data) < batch_size:
                        break
                        
                except Exception as e:
                    logger.exception(f"Erro no lote {batch_num + 1} da categoria {category_id}: {str(e)}")
                    category_stats['errors'] += 1
            
            BackgroundSyncService._add_message(
                sync_key, 
                f"Categoria {category_name}: {category_stats['added']} adicionados, {category_stats['updated']} atualizados, {category_stats['errors']} erros",
                'success'
            )
            
        except Exception as e:
            logger.exception(f"Erro ao processar categoria {category_id}: {str(e)}")
            category_stats['errors'] += 1
        
        return category_stats
    
    @staticmethod
    def _process_product_batch(products_data: list, company, moloni_product_ids: set) -> Dict[str, int]:
        """Processa um lote de produtos"""
        batch_stats = {'added': 0, 'updated': 0, 'errors': 0}
        
        try:
            with transaction.atomic():
                for product_data in products_data:
                    try:
                        product, created = ProductMoloniService.create_or_update_product(
                            product_data, company
                        )
                        
                        if product:
                            moloni_product_ids.add(product.product_id)
                            if created:
                                batch_stats['added'] += 1
                            else:
                                batch_stats['updated'] += 1
                        else:
                            batch_stats['errors'] += 1
                            
                    except Exception as e:
                        logger.exception(f"Erro ao processar produto {product_data.get('product_id')}: {str(e)}")
                        batch_stats['errors'] += 1
                        
        except Exception as e:
            logger.exception(f"Erro no lote de produtos: {str(e)}")
            batch_stats['errors'] += len(products_data)
        
        return batch_stats
    
    @staticmethod
    def _cleanup_obsolete_products(company, moloni_product_ids: set, sync_key: str) -> int:
        """Remove produtos que não estão mais no Moloni"""
        try:
            products_to_delete = Product.objects.filter(company=company).exclude(
                product_id__in=moloni_product_ids
            )
            deleted_count = products_to_delete.count()
            
            if deleted_count > 0:
                logger.info(f"Removendo {deleted_count} produtos obsoletos")
                BackgroundSyncService._add_message(sync_key, f"Removendo {deleted_count} produtos obsoletos", 'info')
                
                # Deletar em lotes para evitar problemas de memória
                batch_size = 100
                total_deleted = 0
                
                while products_to_delete.exists():
                    batch_ids = list(products_to_delete.values_list('product_id', flat=True)[:batch_size])
                    Product.objects.filter(product_id__in=batch_ids).delete()
                    total_deleted += len(batch_ids)
                    
                    if total_deleted % 500 == 0:  # Log a cada 500 deletados
                        BackgroundSyncService._add_message(sync_key, f"Removidos {total_deleted}/{deleted_count} produtos obsoletos", 'info')
                
                return deleted_count
            
        except Exception as e:
            logger.exception(f"Erro ao remover produtos obsoletos: {str(e)}")
            BackgroundSyncService._add_message(sync_key, f"Erro ao remover produtos obsoletos: {str(e)}", 'error')
        
        return 0
    
    @staticmethod
    def _update_progress(sync_key: str, updates: Dict[str, Any]):
        """Atualiza o progresso da sincronização"""
        try:
            progress = cache.get(sync_key, {})
            progress.update(updates)
            progress['last_update'] = timezone.now().isoformat()
            cache.set(sync_key, progress, timeout=7200)
        except Exception as e:
            logger.exception(f"Erro ao atualizar progresso: {str(e)}")
    
    @staticmethod
    def _update_stats(sync_key: str, new_stats: Dict[str, int]):
        """Atualiza as estatísticas da sincronização"""
        try:
            progress = cache.get(sync_key, {})
            current_stats = progress.get('stats', {})
            
            for key, value in new_stats.items():
                current_stats[key] = current_stats.get(key, 0) + value
            
            progress['stats'] = current_stats
            cache.set(sync_key, progress, timeout=7200)
        except Exception as e:
            logger.exception(f"Erro ao atualizar stats: {str(e)}")
    
    @staticmethod
    def _add_message(sync_key: str, message: str, level: str = 'info'):
        """Adiciona mensagem ao log da sincronização"""
        try:
            progress = cache.get(sync_key, {})
            messages = progress.get('messages', [])
            
            messages.append({
                'timestamp': timezone.now().isoformat(),
                'message': message,
                'level': level
            })
            
            # Manter apenas as últimas 50 mensagens
            if len(messages) > 50:
                messages = messages[-50:]
            
            progress['messages'] = messages
            cache.set(sync_key, progress, timeout=7200)
        except Exception as e:
            logger.exception(f"Erro ao adicionar mensagem: {str(e)}")
    
    @staticmethod
    def _should_continue(sync_key: str) -> bool:
        """Verifica se a sincronização deve continuar"""
        try:
            progress = cache.get(sync_key)
            return progress and progress.get('status') not in ['cancelled', 'error']
        except Exception:
            return False
    
    @staticmethod
    def _finalize_sync(sync_key: str):
        """Finaliza a sincronização"""
        try:
            progress = cache.get(sync_key, {})
            stats = progress.get('stats', {})
            
            # Limpar cache de contagem
            cache.delete('products_count')
            
            # Fechar conexões do banco para liberar recursos
            connection.close()
            
            # Atualizar status final
            progress.update({
                'status': 'completed',
                'progress': 100,
                'message': f"Sincronização concluída: {stats.get('added', 0)} adicionados, {stats.get('updated', 0)} atualizados, {stats.get('deleted', 0)} removidos",
                'end_time': timezone.now().isoformat()
            })
            
            cache.set(sync_key, progress, timeout=300)  # Manter por 5 minutos
            
            logger.info(f"Sincronização finalizada: {stats}")
            
        except Exception as e:
            logger.exception(f"Erro ao finalizar sincronização: {str(e)}")
    
    @staticmethod
    def get_sync_progress(company_id: int) -> Optional[Dict[str, Any]]:
        """Obtém o progresso atual da sincronização"""
        sync_key = f'sync_progress_{company_id}'
        return cache.get(sync_key)
    
    @staticmethod
    def cancel_sync(company_id: int) -> bool:
        """Cancela a sincronização em andamento"""
        sync_key = f'sync_progress_{company_id}'
        progress = cache.get(sync_key)
        
        if progress and progress.get('status') in ['started', 'processing']:
            progress['status'] = 'cancelled'
            progress['message'] = 'Sincronização cancelada pelo usuário'
            cache.set(sync_key, progress, timeout=300)
            return True
        
        return False
    
    @staticmethod
    def cleanup_old_syncs():
        """Remove sincronizações antigas do cache (chamar periodicamente)"""
        try:
            # Esta função pode ser chamada por um comando de management
            # para limpar sincronizações antigas do cache
            pass
        except Exception as e:
            logger.exception(f"Erro ao limpar sincronizações antigas: {str(e)}")
