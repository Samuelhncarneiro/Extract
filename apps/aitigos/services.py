# apps/aitigos/services.py
import logging
import requests
import json
import re
import time
from typing import Dict, Any, List, Tuple, Optional
from django.conf import settings

from apps.product_moloni.models import Product, ProductVariant
from apps.sechic.models import Category, Supplier, Unit, Tax
from apps.moloni.models import Moloni
from apps.sechic.services import MoloniService
from apps.product_moloni.services import ProductMoloniService
from .cache_manager import AitigosCacheManager

from apps.product_moloni.models import Product as MoloniProduct
from apps.product_shopify.models import ShopifyProduct, ShopifyVariant
logger = logging.getLogger(__name__)

class MoloniSyncService:
    @staticmethod
    def sync_products_to_moloni(products_data: List[Dict], company: Moloni) -> Tuple[bool, Dict, List]:
        try:
            config_result = MoloniSyncService._load_company_config(company)
            if not config_result['success']:
                return False, {}, [{"error": config_result['error']}]
            
            categories = config_result['categories']
            suppliers = config_result['suppliers']
            units = config_result['units']
            taxes = config_result['taxes']
            defaults = config_result['defaults']
            
            metrics = {
                "total": len(products_data),
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "failed": 0,
                "total_variants": 0
            }
            
            results = []
            
            for product in products_data:
                metrics["total_variants"] += len(product.get('details', []))
            
            for product_idx, product in enumerate(products_data):
                product_result = MoloniSyncService._process_single_product(
                    product, product_idx, company, categories, suppliers, 
                    units, taxes, defaults, metrics
                )
                
                results.extend(product_result)
                
                time.sleep(0.5)
            
            try:
                success_products, message_products, count_products = ProductMoloniService.fetch_and_store_products(company)
                if success_products:
                    logger.info(f"Lista de produtos atualizada após sincronização: {message_products}")
                else:
                    logger.warning(f"Erro ao atualizar lista de produtos: {message_products}")
            except Exception as e:
                logger.error(f"Erro ao atualizar lista de produtos após sincronização: {str(e)}")
            
            overall_success = metrics["created"] > 0 or metrics["updated"] > 0
            
            return overall_success, metrics, results
            
        except Exception as e:
            logger.exception(f"Erro geral na sincronização com Moloni: {str(e)}")
            return False, {"error": str(e)}, []
    
    @staticmethod
    def _load_company_config(company: Moloni) -> Dict:
        try:                          
            categories = {cat.name.upper(): cat for cat in Category.objects.filter(company=company)}
            suppliers = {sup.name.upper(): sup for sup in Supplier.objects.filter(company=company)}
            units = {u.name.upper(): u for u in Unit.objects.filter(company=company)}
            taxes = {t.name.upper(): t for t in Tax.objects.filter(company=company)}
            
            default_category = Category.objects.filter(company=company).first()
            default_supplier = Supplier.objects.filter(company=company).first()
            default_unit = Unit.objects.filter(company=company).first()
            default_tax = Tax.objects.filter(company=company).first()
            
            if not all([default_category, default_supplier, default_unit, default_tax]):
                error_config = {
                    'success': False,
                    'error': "Configuração de categorias, fornecedores, unidades ou impostos não encontrada para esta empresa."
                }
                return error_config
            
            # Preparar dados para cache (apenas IDs e nomes, não objetos ORM)
            config_data = {
                'success': True,
                'categories': {name: {'id': cat.category_id, 'name': cat.name} for name, cat in categories.items()},
                'suppliers': {name: {'id': sup.supplier_id, 'name': sup.name, 'code': sup.code} for name, sup in suppliers.items()},
                'units': {name: {'id': u.unit_id, 'name': u.name, 'short_name': u.short_name} for name, u in units.items()},
                'taxes': {name: {'id': t.tax_id, 'name': t.name, 'value': t.value} for name, t in taxes.items()},
                'defaults': {
                    'category': {'id': default_category.category_id, 'name': default_category.name},
                    'supplier': {'id': default_supplier.supplier_id, 'name': default_supplier.name, 'code': default_supplier.code},
                    'unit': {'id': default_unit.unit_id, 'name': default_unit.name, 'short_name': default_unit.short_name},
                    'tax': {'id': default_tax.tax_id, 'name': default_tax.name, 'value': default_tax.value}
                }
            }
            
            AitigosCacheManager.cache_company_config(company.id, config_data)
            
            result = {
                'success': True,
                'categories': categories,
                'suppliers': suppliers,
                'units': units,
                'taxes': taxes,
                'defaults': {
                    'category': default_category,
                    'supplier': default_supplier,
                    'unit': default_unit,
                    'tax': default_tax
                }
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Erro ao carregar configurações da empresa: {str(e)}")
            return {
                'success': False,
                'error': f"Erro ao carregar configurações: {str(e)}"
            }
    
    @staticmethod
    def _process_single_product(product: Dict, product_idx: int, company: Moloni, 
                               categories: Dict, suppliers: Dict, units: Dict, 
                               taxes: Dict, defaults: Dict, metrics: Dict) -> List[Dict]:

        product_name = product.get('name', '')
        variants = product.get('details', [])
        results = []
        
        if not variants:
            logger.warning(f"Produto sem variantes, ignorando: {product_name}")
            metrics["skipped"] += 1
            return results
        
        category = MoloniSyncService._resolve_category(product.get('category', ''), categories, defaults['category'])
        supplier = MoloniSyncService._resolve_supplier(product.get('supplier', ''), suppliers, defaults['supplier'])
        unit = MoloniSyncService._resolve_unit('UNIDADE', units, defaults['unit'])
        tax = MoloniSyncService._resolve_tax('IVA 23%', taxes, defaults['tax'])
        
        for variant_idx, variant in enumerate(variants):
            try:
                variant_result = MoloniSyncService._process_single_variant(
                    product, variant, variant_idx, len(variants), company, 
                    category, supplier, unit, tax
                )
                
                if variant_result['success']:
                    metrics["created"] += 1
                else:
                    metrics["failed"] += 1
                
                results.append(variant_result)
                
            except Exception as e:
                metrics["failed"] += 1
                logger.exception(f"Erro ao processar variante {variant.get('reference')}: {str(e)}")
                results.append({
                    "reference": variant.get('reference'),
                    "action": "exception",
                    "error": str(e),
                    "success": False
                })
        
        return results
    
    @staticmethod
    def _process_single_variant(product: Dict, variant: Dict, variant_idx: int, 
                               total_variants: int, company: Moloni,
                               category, supplier, unit, tax) -> Dict:

        product_name = product.get('name', '')
        variant_desc = f"{product_name} - {variant.get('color_name', '')} {variant.get('size', '')}"
        
        logger.info(f"Processando variante {variant_idx+1}/{total_variants}: {variant_desc}")
        
        try:
            unit_price = float(variant.get('unit_price', 0) or 0)
            quantity = float(variant.get('quantity', 0) or 0)
            has_stock = 1 if quantity > 0 else 0

            markup = supplier.current_markup
            sales_price = unit_price * markup
            
            try:
                if isinstance(tax, dict):
                    tax_value = float(str(tax.get('value', 23)).replace('%', ''))
                    tax_id = tax.get('id', 1)
                else:
                    if str(tax.value).replace('.', '').replace('%', '').isdigit():
                        tax_value = float(str(tax.value).replace('%', ''))
                    else:
                        tax_value = 23.0
                    tax_id = tax.tax_id
            except (ValueError, TypeError, AttributeError):
                tax_value = 23.0
                tax_id = 1
                logger.warning(f"Usando valor de imposto padrão: {tax_value}%")
            
            form_data = {
                'company_id': int(company.company_id),
                'category_id': int(category.category_id),
                'type': 1,
                'name': variant.get('description') or variant_desc,
                'summary': '',
                'reference': variant.get('reference', ''),
                'ean': variant.get('barcode', ''),
                'price': float(sales_price/1.23),
                'unit_id': int(unit.unit_id),
                'has_stock': 0,
                'stock': 0.0,
                'exemption_reason': 'M01',
                'pos_favorite': 0,
                'suppliers[0][supplier_id]': int(supplier.supplier_id),
                'suppliers[0][cost_price]': float(unit_price),
                'taxes[0][tax_id]': int(tax.tax_id),
                'taxes[0][value]': tax_value,
                'taxes[0][order]': 0,
                'taxes[0][cumulative]': 0,
            }
            
            if has_stock == 1:
                form_data['at_product_category'] = "M"
            
            # Adicionar propriedades
            properties = MoloniSyncService._build_product_properties(product, variant)
            if properties:
                for i, prop in enumerate(properties):
                    form_data[f'properties[{i}][property_id]'] = prop['property_id']
                    form_data[f'properties[{i}][value]'] = prop['value']
            
            url = f'https://api.moloni.pt/v1/products/insert/'
            success, response_data, error = MoloniService._make_authenticated_request_encode(
                url, company, method='POST', form_data=form_data
            )
            
            if success and response_data and response_data.get('valid') == 1:
                product_id = response_data.get('product_id')
                logger.info(f"Produto criado: {variant.get('reference')} com ID {product_id}")
                
                return {
                    "id": product_id,
                    "reference": variant.get('reference'),
                    "action": "created",
                    "name": form_data["name"],
                    "success": True
                }
            else:
                error_msg = str(response_data) if response_data else error
                logger.error(f"Falha ao criar: {variant.get('reference')} - {error_msg}")
                
                return {
                    "reference": variant.get('reference'),
                    "action": "create_failed",
                    "error": error_msg,
                    "success": False
                }
                
        except Exception as e:
            logger.exception(f"Erro ao processar variante {variant.get('reference')}: {str(e)}")
            return {
                "reference": variant.get('reference'),
                "action": "exception",
                "error": str(e),
                "success": False
            }

    @staticmethod
    def _resolve_category(category_name: str, categories: Dict, default_category) -> Any:
        """Resolve a categoria do produto"""
        if category_name:
            return categories.get(category_name.upper(), default_category)
        return default_category
    
    @staticmethod
    def _resolve_supplier(supplier_name: str, suppliers: Dict, default_supplier) -> Any:
        """Resolve o fornecedor do produto"""
        if supplier_name:
            return suppliers.get(supplier_name.upper(), default_supplier)
        return default_supplier
    
    @staticmethod
    def _resolve_unit(unit_name: str, units: Dict, default_unit) -> Any:
        """Resolve a unidade do produto"""
        return units.get(unit_name.upper(), default_unit)
    
    @staticmethod
    def _resolve_tax(tax_name: str, taxes: Dict, default_tax) -> Any:
        """Resolve o imposto do produto"""
        return taxes.get(tax_name.upper(), default_tax)
    
    @staticmethod
    def _build_product_properties(product: Dict, variant: Dict) -> List[Dict]:
        """Constrói as propriedades do produto"""
        properties = []
        
        if product.get('composition'):
            properties.append({"property_id": 1, "value": product.get('composition', '')})
        if variant.get('color_name'):
            properties.append({"property_id": 2, "value": variant.get('color_name', '')})
        if variant.get('size'):
            properties.append({"property_id": 3, "value": variant.get('size', '')})
        if product.get('gender'):
            properties.append({"property_id": 4, "value": product.get('gender', '')})
        
        return properties

    @staticmethod
    def generate_sync_message(metrics: Dict) -> str:
        message = f"Sincronização concluída: {metrics['created']} criados, {metrics['updated']} atualizados"
        
        if metrics["failed"]:
            message += f", {metrics['failed']} falhas"
        if metrics["skipped"]:
            message += f", {metrics['skipped']} ignorados"
        if metrics["total_variants"]:
            message += f". Total de {metrics['total_variants']} variantes processadas."
        
        return message
            
class ShopifySyncService:
    @staticmethod
    def create_product(access_token: str, shop_domain: str, product_data: Dict[str, Any]) -> Tuple[bool, Dict, str]:
        try:
            url = f"https://{shop_domain}/admin/api/2023-07/products.json"
            
            # Configurar headers
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            }
            
            # Log detalhado dos dados enviados
            logger.info("="*50)
            logger.info("CRIANDO PRODUTO NO SHOPIFY")
            logger.info("="*50)
            logger.info(f"URL: {url}")
            logger.info(f"Produto: {product_data.get('title', '')}")
            
            # Garantir valores padrão para campos obrigatórios
            if not product_data.get('product_type'):
                product_data['product_type'] = "Geral"
                
            if not product_data.get('vendor'):
                product_data['vendor'] = "Loja" 
                
            # Garantir status ativo
            if 'status' not in product_data:
                product_data['status'] = "active"
            
            # Verificar se existem opções e são válidas
            if 'options' in product_data:
                for option in product_data['options']:
                    if not option.get('values') or len(option['values']) == 0:
                        option['values'] = ["Padrão"]
            
            # PREVENÇÃO DE VARIANTES DUPLICADAS
            # Verificar se há variantes definidas e deduplica-las 
            if 'variants' in product_data and product_data['variants']:
                logger.info(f"Verificando {len(product_data['variants'])} variantes para possíveis duplicatas")
                
                # Mapear variantes por combinação de opções
                unique_variants = {}
                
                for variant in product_data['variants']:
                    # Criar uma chave única baseada nas opções (cor/tamanho)
                    option_key = ""
                    for i in range(1, 4): 
                        option_name = f"option{i}"
                        if option_name in variant:
                            option_key += f"{variant[option_name]}/"
                        
                        # Gerar nova chave
                        option_key = ""
                        for i in range(1, 4):
                            option_name = f"option{i}"
                            if option_name in variant:
                                option_key += f"{variant[option_name]}/"
                    
                    # Armazenar a variante com chave única
                    unique_variants[option_key] = variant
                
                # Substituir lista original por lista deduplicitada
                product_data['variants'] = list(unique_variants.values())
                logger.info(f"Após deduplicação: {len(product_data['variants'])} variantes restantes")
                
                # Log das variantes
                for i, variant in enumerate(product_data['variants']):
                    logger.info(f"Variante {i+1}:")
                    for key, value in variant.items():
                        logger.info(f"  {key}: {value}")
            
            # Payload completo
            payload = {"product": product_data}
            logger.info(f"Payload completo: {json.dumps(payload, indent=2)}")
            
            # Fazer requisição para criar produto
            response = requests.post(url, headers=headers, json=payload)
            
            # Log da resposta
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Resposta completa: {response.text[:1000]}")  # Limitar para não logar respostas enormes
            
            # Verificar resposta
            if response.status_code in (200, 201):
                result = response.json()
                logger.info(f"Produto criado com sucesso. ID: {result.get('product', {}).get('id')}")
                return True, result.get("product", {}), "Produto criado com sucesso"
            else:
                logger.error(f"Erro ao criar produto no Shopify: {response.status_code} - {response.text}")
                # Tentar extrair mensagem de erro mais clara
                error_message = "Erro ao criar produto"
                try:
                    error_json = response.json()
                    if 'errors' in error_json:
                        error_message = f"{error_message}: {json.dumps(error_json['errors'])}"
                except:
                    error_message = f"{error_message}: {response.text}"
                
                return False, {}, error_message
                
        except Exception as e:
            logger.exception(f"Exceção ao criar produto no Shopify: {str(e)}")
            return False, {}, f"Exceção: {str(e)}"

    @staticmethod
    def get_locations(access_token: str, shop_domain: str) -> List[Dict]:
        """
        Obtém as localizações disponíveis da loja Shopify para controle de inventário
        
        Args:
            access_token: Token de acesso da API Shopify
            shop_domain: Domínio da loja Shopify
            
        Returns:
            List[Dict]: Lista de localizações
        """
        try:
            url = f"https://{shop_domain}/admin/api/2023-07/locations.json"
            
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            }
            
            logger.info(f"Obtendo localizações do Shopify: {url}")
            
            response = requests.get(url, headers=headers)
            
            logger.info(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                locations = result.get("locations", [])
                logger.info(f"Localizações encontradas: {len(locations)}")
                return locations
            else:
                logger.error(f"Erro ao obter localizações: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.exception(f"Exceção ao obter localizações: {str(e)}")
            return []

    @staticmethod
    def update_inventory_level(access_token: str, shop_domain: str, inventory_item_id: int, location_id: int, quantity: int) -> Tuple[bool, str]:
        """
        Atualiza o nível de inventário de uma variante
        
        Args:
            access_token: Token de acesso da API Shopify
            shop_domain: Domínio da loja Shopify
            inventory_item_id: ID do item de inventário
            location_id: ID da localização
            quantity: Quantidade disponível
            
        Returns:
            Tuple[bool, str]: Sucesso e mensagem
        """
        try:
            # Montar URL da API
            url = f"https://{shop_domain}/admin/api/2023-07/inventory_levels/set.json"
            
            # Configurar headers
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            }
            
            # Dados para atualizar inventário
            data = {
                "inventory_item_id": inventory_item_id,
                "location_id": location_id,
                "available": quantity
            }
            
            # Log para depuração
            logger.info(f"Atualizando inventário: Item ID: {inventory_item_id}, Location ID: {location_id}, Quantidade: {quantity}")
            
            # Fazer requisição para atualizar inventário
            response = requests.post(url, headers=headers, json=data)
            
            # Log da resposta
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Resposta: {response.text}")
            
            # Verificar resposta
            if response.status_code == 200:
                return True, "Inventário atualizado com sucesso"
            else:
                logger.error(f"Erro ao atualizar inventário: {response.status_code} - {response.text}")
                return False, f"Erro ao atualizar inventário: {response.text}"
                
        except Exception as e:
            logger.exception(f"Exceção ao atualizar inventário: {str(e)}")
            return False, f"Exceção: {str(e)}"

    @staticmethod
    def consolidate_products_by_color(products_data: List[Dict]) -> List[Dict]:
        logger.info("="*60)
        logger.info("CONSOLIDANDO PRODUTOS POR COR (CORRIGIDO)")
        logger.info("="*60)
        
        color_consolidation = {}
        
        for product in products_data:
            product_name = product.get('name') or 'Produto'
            material_code = product.get('material_code') or ''
            
            for detail in product.get('details', []):
                # Proteção contra None
                color_name = detail.get('color_name') or ''
                if color_name:
                    color_name = str(color_name).strip()
                
                if not color_name:
                    color_name = "Sem Cor"
                
                unique_key = f"{material_code}_{color_name}"
                
                if unique_key not in color_consolidation:
                    if color_name and color_name != "Sem Cor":
                        display_name = f"{product_name}"
                    else:
                        display_name = product_name
                    
                    color_consolidation[unique_key] = {
                        'name': display_name,
                        'original_name': product_name,
                        'material_code': material_code,
                        'composition': product.get('composition') or '',
                        'category': product.get('category') or '',
                        'gender': product.get('gender') or '',
                        'brand': product.get('brand') or '',
                        'supplier': product.get('supplier') or '',
                        'date': product.get('date') or '',
                        'warehouse': product.get('warehouse') or '1',
                        'integrated': product.get('integrated') or '0',
                        'details': []
                    }
                    logger.info(f"Criada consolidação para: {display_name} ({material_code})")
                
                color_consolidation[unique_key]['details'].append(detail)
        
        consolidated_products = list(color_consolidation.values())
        
        total_original_variants = sum(len(p.get('details', [])) for p in products_data)
        total_consolidated_variants = sum(len(p.get('details', [])) for p in consolidated_products)
        
        logger.info(f"Consolidação concluída:")
        logger.info(f"  Produtos originais: {len(products_data)}")
        logger.info(f"  Produtos consolidados: {len(consolidated_products)}")
        logger.info(f"  Variantes originais: {total_original_variants}")
        logger.info(f"  Variantes consolidadas: {total_consolidated_variants}")
        
        for product in consolidated_products:
            variant_count = len(product['details'])
            logger.info(f"  {product['name']}: {variant_count} variantes")
        
        return consolidated_products

    @staticmethod
    def format_product_for_shopify(product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formata dados do produto consolidado para o Shopify
        """
        material_code = product_data.get('material_code', '')
        product_name = product_data.get('name', '')
        variants = product_data.get('details', [])
        
        logger.info(f"Formatando produto consolidado: {product_name} com {len(variants)} variantes")
        
        all_sizes = set()
        
        for variant in variants:
            size = variant.get('size', '').strip()
            if size:
                all_sizes.add(size)
        
        logger.info(f"Tamanhos encontrados: {sorted(all_sizes)}")
        
        if all_sizes:
            options = [{"name": "Size", "values": sorted(list(all_sizes))}]
        else:
            options = [{"name": "Title", "values": ["Default"]}]
        
        shopify_product = {
            "title": product_name,
            "body_html": product_data.get('composition', ''),
            "vendor": product_data.get('supplier', '') or "Loja",
            "product_type": product_data.get('category', '') or "Geral",
            "status": "active",
            "published_scope": "web",
            "tags": ", ".join(filter(None, [
                product_data.get('category', ''),
                product_data.get('gender', ''),
                product_data.get('brand', ''),
                f"ref:{material_code}"
            ])),
            "options": options
        }
        
        # Formatar variantes
        formatted_variants = []
        
        for variant in variants:
            variant_sku = variant.get('reference', '')
            variant_size = variant.get('size', '')
            
            # Validar preços
            try:
                sales_price = float(variant.get('sales_price', 0))
                price_str = f"{sales_price:.2f}"
            except:
                price_str = "0.00"
                
            try:
                unit_price = float(variant.get('unit_price', 0))
                cost_str = f"{unit_price:.2f}"
            except:
                cost_str = "0.00"
                
            try:
                quantity = int(variant.get('quantity', 0))
            except:
                quantity = 0
            
            variant_data = {
                "sku": variant_sku,
                "barcode": variant.get('barcode', ''),
                "price": price_str,
                "cost": cost_str,
                "inventory_management": "shopify",
                "inventory_policy": "deny",
                "inventory_quantity": quantity,
                "weight": 0,
                "weight_unit": "kg",
                "requires_shipping": True,
                "taxable": True
            }
            
            # Adicionar opção de tamanho
            if variant_size and len(options) > 0 and options[0]["name"] == "Size":
                variant_data["option1"] = variant_size
            else:
                variant_data["option1"] = "Default"
            
            formatted_variants.append(variant_data)
            logger.debug(f"Variante adicionada: Size={variant_size}, SKU={variant_sku}")
        
        shopify_product["variants"] = formatted_variants
        
        logger.info(f"Produto formatado: {len(formatted_variants)} variantes consolidadas")
        
        return shopify_product

class ProductComparisonService:
    @staticmethod
    def compare_with_moloni(products_data: List[Dict], company) -> Dict:
        try:
            logger.info(f"Comparando {len(products_data)} produtos com base de dados Moloni")
            
            existing_products = MoloniProduct.objects.filter(company=company)
            
            existing_by_reference = {}
            existing_by_ean = {}
            existing_by_name = {}
            
            for product in existing_products:
                if product.reference:
                    existing_by_reference[product.reference.upper()] = product
                if product.ean:
                    existing_by_ean[product.ean] = product
                if product.name:
                    existing_by_name[product.name.upper()] = product
            
            comparison_results = {
                'total_new': len(products_data),
                'conflicts': [],
                'safe_to_insert': [],
                'total_variants_new': 0,
                'total_variants_conflicts': 0
            }
            
            for product_idx, product in enumerate(products_data):
                variants = product.get('details', [])
                comparison_results['total_variants_new'] += len(variants)
                
                product_conflicts = []
                variant_conflicts = []
                
                for variant in variants:
                    reference = variant.get('reference', '').strip()
                    barcode = variant.get('barcode', '').strip()
                    name = variant.get('description', '').strip()
                    
                    conflicts = []
                    
                    if reference and reference.upper() in existing_by_reference:
                        existing = existing_by_reference[reference.upper()]
                        conflicts.append({
                            'type': 'reference',
                            'field': 'Referência',
                            'value': reference,
                            'existing_product': {
                                'id': existing.product_id,
                                'name': existing.name,
                                'reference': existing.reference,
                                'ean': existing.ean,
                                'price': float(existing.price)
                            }
                        })
                    
                    if barcode and barcode in existing_by_ean:
                        existing = existing_by_ean[barcode]
                        conflicts.append({
                            'type': 'barcode',
                            'field': 'Código de Barras',
                            'value': barcode,
                            'existing_product': {
                                'id': existing.product_id,
                                'name': existing.name,
                                'reference': existing.reference,
                                'ean': existing.ean,
                                'price': float(existing.price)
                            }
                        })
                    
                    if name and name.upper() in existing_by_name:
                        existing = existing_by_name[name.upper()]
                        conflicts.append({
                            'type': 'name',
                            'field': 'Nome',
                            'value': name,
                            'existing_product': {
                                'id': existing.product_id,
                                'name': existing.name,
                                'reference': existing.reference,
                                'ean': existing.ean,
                                'price': float(existing.price)
                            }
                        })
                    
                    if conflicts:
                        variant_conflicts.append({
                            'variant': variant,
                            'conflicts': conflicts
                        })
                        comparison_results['total_variants_conflicts'] += 1
                
                if variant_conflicts:
                    comparison_results['conflicts'].append({
                        'product_index': product_idx,
                        'product': product,
                        'variant_conflicts': variant_conflicts
                    })
                else:
                    comparison_results['safe_to_insert'].append({
                        'product_index': product_idx,
                        'product': product
                    })
            
            comparison_results['has_conflicts'] = len(comparison_results['conflicts']) > 0
            comparison_results['safe_variants'] = (
                comparison_results['total_variants_new'] - 
                comparison_results['total_variants_conflicts']
            )
            
            logger.info(f"Comparação Moloni concluída: {len(comparison_results['conflicts'])} produtos com conflitos, "
                       f"{len(comparison_results['safe_to_insert'])} seguros para inserir")
            
            return comparison_results
            
        except Exception as e:
            logger.exception(f"Erro na comparação com Moloni: {str(e)}")
            return {
                'error': str(e),
                'has_conflicts': False,
                'conflicts': [],
                'safe_to_insert': products_data,
                'total_new': len(products_data)
            }
    
    @staticmethod
    def compare_with_shopify(products_data: List[Dict], shopify_store) -> Dict:
        try:
            logger.info(f"Comparando {len(products_data)} produtos com base de dados Shopify")
            
            from apps.aitigos.services import ShopifySyncService
            consolidated_products = ShopifySyncService.consolidate_products_by_color(products_data)
            
            # Obter produtos existentes do Shopify
            existing_products = ShopifyProduct.objects.filter(store=shopify_store)
            existing_variants = ShopifyVariant.objects.filter(product__store=shopify_store)
            
            # Criar mapas de produtos existentes
            existing_by_title = {}
            existing_variants_by_sku = {}
            existing_variants_by_barcode = {}
            
            for product in existing_products:
                if product.title:
                    existing_by_title[product.title.upper()] = product
            
            for variant in existing_variants:
                if variant.sku:
                    existing_variants_by_sku[variant.sku.upper()] = variant
                if variant.barcode:
                    existing_variants_by_barcode[variant.barcode] = variant
            
            comparison_results = {
                'total_new': len(consolidated_products),
                'conflicts': [],
                'safe_to_insert': [],
                'total_variants_new': 0,
                'total_variants_conflicts': 0,
                'consolidation_info': {
                    'original_products': len(products_data),
                    'consolidated_products': len(consolidated_products)
                }
            }
            
            for product_idx, product in enumerate(consolidated_products):
                variants = product.get('details', [])
                comparison_results['total_variants_new'] += len(variants)
                
                variant_conflicts = []
                
                # Verificar conflito por título do produto
                product_title = product.get('name', '').strip()
                title_conflict = None
                
                if product_title and product_title.upper() in existing_by_title:
                    existing = existing_by_title[product_title.upper()]
                    title_conflict = {
                        'type': 'title',
                        'field': 'Título',
                        'value': product_title,
                        'existing_product': {
                            'id': existing.shopify_id,
                            'title': existing.title,
                            'vendor': existing.vendor,
                            'product_type': existing.product_type,
                            'status': existing.status
                        }
                    }
                
                # Verificar cada variante
                for variant in variants:
                    reference = variant.get('reference', '').strip()
                    barcode = variant.get('barcode', '').strip()
                    
                    conflicts = []
                    
                    # Verificar conflito por SKU (referência)
                    if reference and reference.upper() in existing_variants_by_sku:
                        existing_variant = existing_variants_by_sku[reference.upper()]
                        conflicts.append({
                            'type': 'sku',
                            'field': 'SKU/Referência',
                            'value': reference,
                            'existing_variant': {
                                'id': existing_variant.variant_id,
                                'sku': existing_variant.sku,
                                'title': existing_variant.title,
                                'price': float(existing_variant.price),
                                'product_title': existing_variant.product.title
                            }
                        })
                    
                    # Verificar conflito por código de barras
                    if barcode and barcode in existing_variants_by_barcode:
                        existing_variant = existing_variants_by_barcode[barcode]
                        conflicts.append({
                            'type': 'barcode',
                            'field': 'Código de Barras',
                            'value': barcode,
                            'existing_variant': {
                                'id': existing_variant.variant_id,
                                'sku': existing_variant.sku,
                                'barcode': existing_variant.barcode,
                                'title': existing_variant.title,
                                'price': float(existing_variant.price),
                                'product_title': existing_variant.product.title
                            }
                        })
                    
                    if conflicts:
                        variant_conflicts.append({
                            'variant': variant,
                            'conflicts': conflicts
                        })
                        comparison_results['total_variants_conflicts'] += 1
                
                # Se há conflitos (título ou variantes), adicionar à lista
                if title_conflict or variant_conflicts:
                    conflict_info = {
                        'product_index': product_idx,
                        'product': product,
                        'variant_conflicts': variant_conflicts
                    }
                    if title_conflict:
                        conflict_info['title_conflict'] = title_conflict
                    
                    comparison_results['conflicts'].append(conflict_info)
                else:
                    comparison_results['safe_to_insert'].append({
                        'product_index': product_idx,
                        'product': product
                    })
            
            comparison_results['has_conflicts'] = len(comparison_results['conflicts']) > 0
            comparison_results['safe_variants'] = (
                comparison_results['total_variants_new'] - 
                comparison_results['total_variants_conflicts']
            )
            
            logger.info(f"Comparação Shopify concluída: {len(comparison_results['conflicts'])} produtos com conflitos, "
                       f"{len(comparison_results['safe_to_insert'])} seguros para inserir")
            
            return comparison_results
            
        except Exception as e:
            logger.exception(f"Erro na comparação com Shopify: {str(e)}")
            return {
                'error': str(e),
                'has_conflicts': False,
                'conflicts': [],
                'safe_to_insert': consolidated_products if 'consolidated_products' in locals() else products_data,
                'total_new': len(products_data)
            }
    
    @staticmethod
    def filter_products_for_insertion(products_data: List[Dict], safe_indices: List[int]) -> List[Dict]:
        try:
            filtered_products = []
            
            for idx in safe_indices:
                if 0 <= idx < len(products_data):
                    filtered_products.append(products_data[idx])
            
            logger.info(f"Filtrados {len(filtered_products)} produtos de {len(products_data)} originais")
            
            return filtered_products
            
        except Exception as e:
            logger.exception(f"Erro ao filtrar produtos: {str(e)}")
            return []