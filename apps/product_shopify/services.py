# apps/product_shopify/services.py
import logging
import requests
import json
import time
import re
from typing import Dict, List, Any, Tuple, Optional
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from apps.product_shopify.models import ShopifyProduct, ShopifyVariant, ShopifyImage
from apps.shopify.models import Shopify

logger = logging.getLogger(__name__)

class ShopifyService:
    @staticmethod
    def get_shop_url(shop_name: str) -> str:
        """
        Retorna a URL da loja Shopify
        """
        return f"https://{shop_name}.myshopify.com"
    
    @staticmethod
    def get_api_url(shop_name: str, version: str = "2023-10") -> str:
        """
        Retorna a URL base da API do Shopify
        """
        return f"https://{shop_name}.myshopify.com/admin/api/{version}"
    
    @staticmethod
    def get_headers(access_token: str) -> Dict[str, str]:
        """
        Retorna os cabeçalhos para a API do Shopify
        """
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }
    
    @staticmethod
    def fetch_and_store_products(
        shop_name: str, 
        access_token: str,
        limit: int = 250,
        force_update: bool = False,
        store_obj = None
    ) -> Tuple[bool, str, int]:

        logger.info(f"Iniciando sincronização de produtos do Shopify - Loja: {shop_name}")
        start_time = time.time()
        
        store = store_obj
        if not store:
            try:
                from apps.shopify.models import Shopify
                store = Shopify.objects.filter(
                    shop_domain__icontains=shop_name,
                    access_token=access_token
                ).first()
            except Exception as e:
                logger.warning(f"Não foi possível encontrar o objeto da loja: {str(e)}")

        try:
            api_url = ShopifyService.get_api_url(shop_name)
            headers = ShopifyService.get_headers(access_token)
            
            total_products_count = 0
            total_saved_count = 0
            total_variants_count = 0
            total_images_count = 0
            total_deleted_count = 0
            page_index = 0
            
            all_synced_product_ids = set()
            all_synced_product_refs = set()
            
            url = f"{api_url}/products.json?limit={limit}&fields=id,title,handle,body_html,vendor,product_type,status,published_at,tags,variants,images"
            
            def get_products_page(page_url):
                nonlocal total_products_count, total_saved_count, total_variants_count, total_images_count, page_index
                
                page_index += 1
                logger.info(f"Buscando página {page_index} de produtos: {page_url}")
                
                time.sleep(0.5)
                
                try:
                    response = requests.get(page_url, headers=headers, timeout=10)
                    
                    if response.status_code != 200:
                        logger.error(f"Erro ao buscar produtos: HTTP {response.status_code} - {response.text}")
                        return False
                    
                    data = response.json()
                    products_data = data.get("products", [])
                    
                    current_batch_size = len(products_data)
                    total_products_count += current_batch_size
                    
                    logger.info(f"Processando lote de {current_batch_size} produtos")
                    
                    for product_data in products_data:
                        try:
                            shopify_id = product_data.get("id")
                            
                            if shopify_id:
                                all_synced_product_ids.add(shopify_id)
                            
                            variants_data = product_data.get("variants", [])
                            for variant in variants_data:
                                if variant.get("sku"):
                                    all_synced_product_refs.add(variant.get("sku"))
                            
                            try:
                                product = ShopifyProduct.objects.get(shopify_id=shopify_id)
    
                                product.title = product_data.get("title", "")
                                product.handle = product_data.get("handle", "")
                                product.body_html = product_data.get("body_html", "")
                                product.vendor = product_data.get("vendor", "")
                                product.product_type = product_data.get("product_type", "")
                                product.status = product_data.get("status", "active")
                                product.published_at = product_data.get("published_at")
                                product.tags = product_data.get("tags", "")
                                
                                if store:
                                    try:
                                        current_store = product.store
                                        if not current_store:
                                            product.store = store
                                    except ShopifyProduct.store.RelatedObjectDoesNotExist:
                                        product.store = store
                                
                                product.save()
                                
                                if not force_update:
                                    logger.debug(f"Produto atualizado: {product.title} (ID: {shopify_id})")
                                    total_saved_count += 1
                                    continue
                                    
                            except ShopifyProduct.DoesNotExist:
                                product = ShopifyProduct(
                                    shopify_id=shopify_id,
                                    title=product_data.get("title", ""),
                                    handle=product_data.get("handle", ""),
                                    body_html=product_data.get("body_html", ""),
                                    vendor=product_data.get("vendor", ""),
                                    product_type=product_data.get("product_type", ""),
                                    status=product_data.get("status", "active"),
                                    published_at=product_data.get("published_at"),
                                    tags=product_data.get("tags", ""),
                                    store=store
                                )
                                
                                product.save()
                                logger.debug(f"Produto criado: {product.title} (ID: {shopify_id})")
                            
                            variants_data = product_data.get("variants", [])
                            
                            if force_update:
                                product.variants.all().delete()
                            
                            for variant_data in variants_data:
                                variant_id = variant_data.get("id")
                                
                                if variant_id:
                                    try:
                                        variant = ShopifyVariant.objects.get(variant_id=variant_id)
                                        
                                        variant.title = variant_data.get("title", "")
                                        variant.price = variant_data.get("price", 0)
                                        variant.sku = variant_data.get("sku", "")
                                        variant.barcode = variant_data.get("barcode", "")
                                        variant.compare_at_price = variant_data.get("compare_at_price")
                                        variant.position = variant_data.get("position", 1)
                                        variant.option1 = variant_data.get("option1", "")
                                        variant.option2 = variant_data.get("option2", "")
                                        variant.option3 = variant_data.get("option3", "")
                                        variant.inventory_quantity = variant_data.get("inventory_quantity", 0)
                                        
                                        variant.save()
                                        
                                    except ShopifyVariant.DoesNotExist:
                                        # Verificar se a variante existe por SKU
                                        sku = variant_data.get("sku")
                                        existing_variant = None
                                        
                                        if sku:
                                            try:
                                                existing_variant = ShopifyVariant.objects.get(sku=sku)
                                                # Se encontrou variante por SKU mas com ID diferente, atualizar o ID
                                                existing_variant.variant_id = variant_id
                                                existing_variant.title = variant_data.get("title", "")
                                                existing_variant.price = variant_data.get("price", 0)
                                                existing_variant.barcode = variant_data.get("barcode", "")
                                                existing_variant.compare_at_price = variant_data.get("compare_at_price")
                                                existing_variant.position = variant_data.get("position", 1)
                                                existing_variant.option1 = variant_data.get("option1", "")
                                                existing_variant.option2 = variant_data.get("option2", "")
                                                existing_variant.option3 = variant_data.get("option3", "")
                                                existing_variant.inventory_quantity = variant_data.get("inventory_quantity", 0)
                                                existing_variant.product = product  # Associar ao produto correto
                                                
                                                existing_variant.save()
                                                logger.debug(f"Variante encontrada por SKU e atualizada: {sku}")
                                            except ShopifyVariant.DoesNotExist:
                                                existing_variant = None
                                        
                                        # Se não encontrou variante por SKU, criar nova
                                        if not existing_variant:
                                            # Criar nova variante
                                            variant = ShopifyVariant(
                                                variant_id=variant_id,
                                                product=product,
                                                title=variant_data.get("title", ""),
                                                price=variant_data.get("price", 0),
                                                sku=variant_data.get("sku", ""),
                                                barcode=variant_data.get("barcode", ""),
                                                compare_at_price=variant_data.get("compare_at_price"),
                                                position=variant_data.get("position", 1),
                                                option1=variant_data.get("option1", ""),
                                                option2=variant_data.get("option2", ""),
                                                option3=variant_data.get("option3", ""),
                                                inventory_quantity=variant_data.get("inventory_quantity", 0)
                                            )
                                            
                                            variant.save()
                                            total_variants_count += 1
                            
                            # Processar imagens
                            if force_update:
                                product.images.all().delete()
                                
                            images_data = product_data.get("images", [])
                            for image_data in images_data:
                                image_id = image_data.get("id")
                                
                                if image_id:
                                    try:
                                        # Verificar se a imagem já existe
                                        image = ShopifyImage.objects.get(image_id=image_id)
                                        
                                        # Atualizar imagem
                                        image.position = image_data.get("position", 1)
                                        image.src = image_data.get("src", "")
                                        image.alt = image_data.get("alt", "")
                                        image.width = image_data.get("width")
                                        image.height = image_data.get("height")
                                        
                                        image.save()
                                        
                                    except ShopifyImage.DoesNotExist:
                                        # Criar nova imagem
                                        image = ShopifyImage(
                                            image_id=image_id,
                                            product=product,
                                            position=image_data.get("position", 1),
                                            src=image_data.get("src", ""),
                                            alt=image_data.get("alt", ""),
                                            width=image_data.get("width"),
                                            height=image_data.get("height")
                                        )
                                        
                                        image.save()
                                        total_images_count += 1
                            
                            total_saved_count += 1
                            
                        except Exception as e:
                            logger.exception(f"Erro ao salvar produto ID {product_data.get('id')}: {str(e)}")
                    
                    next_page_url = None
                    link_header = response.headers.get('Link')
                    
                    if link_header and "rel=\"next\"" in link_header:
                        urls = ShopifyService._find_urls_in_string(link_header)
                        for url_text in urls:
                            if "rel=\"next\"" in link_header.split(url_text)[1]:
                                next_page_url = url_text
                                break
                    
                    if next_page_url:
                        get_products_page(next_page_url)
                    
                    return True
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout ao buscar página {page_index}. Tentando novamente...")
                    time.sleep(2)
                    return get_products_page(page_url)
                    
                except Exception as e:
                    logger.exception(f"Erro ao processar página {page_index}: {str(e)}")
                    return False
            
            success = get_products_page(url)
            
            if not success:
                return (False, "Erro ao buscar produtos do Shopify", 0)
            
            if total_products_count == 0:
                logger.info("Nenhum produto encontrado no Shopify. Verificando se devemos excluir todos os produtos locais.")
                
                local_products_count = ShopifyProduct.objects.count()
                
                if local_products_count > 0:
                    logger.info(f"Removendo {local_products_count} produtos locais, pois não existem produtos no Shopify.")
                    ShopifyProduct.objects.all().delete()
                    total_deleted_count = local_products_count
                    
                    logger.info(f"Excluídos {total_deleted_count} produtos que não existem mais no Shopify")
                else:
                    logger.info("Nenhum produto local para excluir.")
            elif all_synced_product_ids:
                products_to_delete = ShopifyProduct.objects.exclude(shopify_id__in=all_synced_product_ids)
                deleted_count = products_to_delete.count()
                
                if deleted_count > 0:
                    logger.info(f"Excluindo {deleted_count} produtos que foram removidos do Shopify")
                    
                    deleted_ids = list(products_to_delete.values_list('shopify_id', flat=True))
                    logger.debug(f"IDs dos produtos excluídos: {deleted_ids}")
                    
                    products_to_delete.delete()
                    total_deleted_count = deleted_count
            
            if all_synced_product_refs:
                orphan_variants = ShopifyVariant.objects.filter(
                    Q(sku='') & ~Q(sku__isnull=True) & ~Q(sku__in=all_synced_product_refs)
                )
                
                orphan_count = orphan_variants.count()
                if orphan_count > 0:
                    logger.info(f"Excluindo {orphan_count} variantes órfãs que não existem mais no Shopify")
                    orphan_variants.delete()
                    total_deleted_count += orphan_count
            
            elapsed_time = time.time() - start_time
            logger.info(f"Sincronização concluída em {elapsed_time:.2f}s")
            logger.info(f"Total de produtos no Shopify: {total_products_count}")
            logger.info(f"Total de produtos salvos/atualizados: {total_saved_count}")
            logger.info(f"Total de variantes: {total_variants_count}")
            logger.info(f"Total de imagens: {total_images_count}")
            logger.info(f"Total de produtos/variantes excluídos: {total_deleted_count}")
            
            message = f"Produtos sincronizados com sucesso: {total_saved_count} atualizados"
            if total_deleted_count > 0:
                message += f", {total_deleted_count} excluídos"
            
            # Limpar cache
            try:
                cache.delete('shopify_products_count')
            except:
                pass
            
            return (True, message, total_saved_count)
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.exception(f"Erro na sincronização de produtos após {elapsed_time:.2f}s: {str(e)}")
            return (False, f"Erro na sincronização: {str(e)}", 0)

    @staticmethod
    def _find_urls_in_string(string):
        """Helper para extrair URLs de uma string (usado para paginação)"""
        regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»""'']))"
        url = re.findall(regex, string)
        return [x[0] for x in url]
    
    @staticmethod
    def create_or_update_product(
        shop_name: str,
        access_token: str,
        product_data: Dict[str, Any],
        shopify_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[int]]:

        api_url = ShopifyService.get_api_url(shop_name)
        headers = ShopifyService.get_headers(access_token)
        
        # Se tiver um ID, é atualização; caso contrário, é criação
        if shopify_id:
            url = f"{api_url}/products/{shopify_id}.json"
            method = requests.put
            log_message = f"Atualizando produto ID {shopify_id} no Shopify"
        else:
            url = f"{api_url}/products.json"
            method = requests.post
            log_message = "Criando novo produto no Shopify"
        
        logger.info(log_message)
        
        payload = {"product": product_data}
        
        try:
            response = method(url, headers=headers, json=payload)
            
            if response.status_code not in [200, 201]:
                logger.error(f"Erro na API do Shopify: HTTP {response.status_code} - {response.text}")
                return (False, f"Erro na API do Shopify: {response.status_code}", None)
            
            response_data = response.json()
            new_product = response_data.get("product", {})
            new_product_id = new_product.get("id")
            
            # Salvar no banco de dados local
            if new_product_id:
                try:
                    # Verificar se já existe
                    try:
                        product = ShopifyProduct.objects.get(shopify_id=new_product_id)
                        
                        # Atualizar campos
                        product.title = new_product.get("title", "")
                        product.handle = new_product.get("handle", "")
                        product.body_html = new_product.get("body_html", "")
                        product.vendor = new_product.get("vendor", "")
                        product.product_type = new_product.get("product_type", "")
                        product.status = new_product.get("status", "active")
                        product.published_at = new_product.get("published_at")
                        product.tags = new_product.get("tags", "")
                        
                        product.save()
                        
                    except ShopifyProduct.DoesNotExist:
                        try:
                            if not store:
                                store = Shopify.objects.filter(
                                    shop_domain__icontains=shop_name,
                                    access_token=access_token
                                ).first()
                        except Exception as e:
                            logger.warning(f"Não foi possível encontrar o objeto da loja: {str(e)}")
                       
                        product.store = store

                        product = ShopifyProduct(
                            shopify_id=new_product_id,
                            store=store,
                            title=new_product.get("title", ""),
                            handle=new_product.get("handle", ""),
                            body_html=new_product.get("body_html", ""),
                            vendor=new_product.get("vendor", ""),
                            product_type=new_product.get("product_type", ""),
                            status=new_product.get("status", "active"),
                            published_at=new_product.get("published_at"),
                            tags=new_product.get("tags", "")
                        )
                        
                        product.save()
                    
                    # Processar variantes
                    variants_data = new_product.get("variants", [])
                    for variant_data in variants_data:
                        variant_id = variant_data.get("id")
                        
                        if variant_id:
                            try:
                                # Verificar se a variante já existe
                                variant = ShopifyVariant.objects.get(variant_id=variant_id)
                                
                                # Atualizar variante
                                variant.title = variant_data.get("title", "")
                                variant.price = variant_data.get("price", 0)
                                variant.sku = variant_data.get("sku", "")
                                variant.barcode = variant_data.get("barcode", "")
                                variant.compare_at_price = variant_data.get("compare_at_price")
                                variant.position = variant_data.get("position", 1)
                                variant.option1 = variant_data.get("option1", "")
                                variant.option2 = variant_data.get("option2", "")
                                variant.option3 = variant_data.get("option3", "")
                                variant.inventory_quantity = variant_data.get("inventory_quantity", 0)
                                
                                variant.save()
                                
                            except ShopifyVariant.DoesNotExist:
                                # Criar nova variante
                                variant = ShopifyVariant(
                                    variant_id=variant_id,
                                    product=product,
                                    title=variant_data.get("title", ""),
                                    price=variant_data.get("price", 0),
                                    sku=variant_data.get("sku", ""),
                                    barcode=variant_data.get("barcode", ""),
                                    compare_at_price=variant_data.get("compare_at_price"),
                                    position=variant_data.get("position", 1),
                                    option1=variant_data.get("option1", ""),
                                    option2=variant_data.get("option2", ""),
                                    option3=variant_data.get("option3", ""),
                                    inventory_quantity=variant_data.get("inventory_quantity", 0)
                                )
                                
                                variant.save()
                    
                    # Processar imagens
                    images_data = new_product.get("images", [])
                    for image_data in images_data:
                        image_id = image_data.get("id")
                        
                        if image_id:
                            try:
                                # Verificar se a imagem já existe
                                image = ShopifyImage.objects.get(image_id=image_id)
                                
                                # Atualizar imagem
                                image.position = image_data.get("position", 1)
                                image.src = image_data.get("src", "")
                                image.alt = image_data.get("alt", "")
                                image.width = image_data.get("width")
                                image.height = image_data.get("height")
                                
                                image.save()
                                
                            except ShopifyImage.DoesNotExist:
                                # Criar nova imagem
                                image = ShopifyImage(
                                    image_id=image_id,
                                    product=product,
                                    position=image_data.get("position", 1),
                                    src=image_data.get("src", ""),
                                    alt=image_data.get("alt", ""),
                                    width=image_data.get("width"),
                                    height=image_data.get("height")
                                )
                                
                                image.save()
                    
                    return (True, f"Produto {'atualizado' if shopify_id else 'criado'} com sucesso", new_product_id)
                    
                except Exception as e:
                    logger.exception(f"Erro ao salvar produto na base local: {str(e)}")
                    return (True, f"Produto {'atualizado' if shopify_id else 'criado'} no Shopify, mas erro ao salvar localmente: {str(e)}", new_product_id)
            
            return (False, "Resposta da API não contém ID do produto", None)
            
        except Exception as e:
            logger.exception(f"Erro ao {'atualizar' if shopify_id else 'criar'} produto: {str(e)}")
            return (False, f"Erro ao {'atualizar' if shopify_id else 'criar'} produto: {str(e)}", None)