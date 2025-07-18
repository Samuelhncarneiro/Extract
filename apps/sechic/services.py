# apps/sechic/services.py
import requests
import logging
from django.db import transaction
from dotenv import load_dotenv
import os
import json
import time

from django.utils import timezone
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
from django.core.cache import cache

from .models import Category, Supplier, Tax, Unit, SupplierMarkup
from apps.sechic.extra_data.supplier_cost import suppliers_data
from apps.moloni.models import Moloni, MoloniCredentials
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env.local.django")

class MoloniService:
    @staticmethod
    def get_sync_cache_key(company_id, operation='categories'):
        """Chave para controlar cooldown de sincronização"""
        return f"moloni:sync:{operation}:company:{company_id}"
    
    @staticmethod
    def get_api_cache_key(company_id, endpoint):
        """Chave para cache de responses da API"""
        return f"moloni:api:{endpoint}:company:{company_id}"
    
    @staticmethod
    def should_sync(company_id, operation='categories', cooldown_minutes=10):
        """Verifica se deve sincronizar baseado no cooldown"""
        cache_key = MoloniService.get_sync_cache_key(company_id, operation)
        last_sync = cache.get(cache_key)
        
        if last_sync is None:
            logger.info(f"🔄 Primeira sincronização de {operation} para empresa {company_id}")
            return True
        
        logger.debug(f"⏰ Sincronização de {operation} em cooldown para empresa {company_id}")
        return False
    
    @staticmethod
    def mark_sync_completed(company_id, operation='categories', cooldown_minutes=10):
        """Marca sincronização como concluída"""
        cache_key = MoloniService.get_sync_cache_key(company_id, operation)
        cache.set(cache_key, timezone.now().isoformat(), cooldown_minutes * 60)
        logger.info(f"✅ Sincronização de {operation} marcada como concluída para empresa {company_id}")
    
    @staticmethod
    def refresh_access_token(company):
        try:
            def _get_user_credentials(company):
                if company.users.exists():
                    user = company.users.first()
                    try:
                        credentials = MoloniCredentials.objects.get(user=user)
                        return credentials.client_id, credentials.client_secret
                    except MoloniCredentials.DoesNotExist:
                        pass
                
                from django.conf import settings
                return (
                    getattr(settings, 'MOLONI_CLIENT_ID', None),
                    getattr(settings, 'MOLONI_CLIENT_SECRET', None)
                )
            
            client_id, client_secret = _get_user_credentials(company)
            
            if not client_id or not client_secret or not company.moloni_refresh_token:
                logger.error(f"Credenciais insuficientes para refresh - Company: {company.name}")
                return False, None, "Credenciais ou refresh token não disponíveis"
            
            refresh_url = "https://api.moloni.pt/v1/grant/"
            params = {
                'grant_type': 'refresh_token',
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': company.moloni_refresh_token
            }
            
            logger.info(f"🔄 Fazendo refresh do token para empresa {company.name}")
            response = requests.get(refresh_url, params=params)
            
            if response.status_code != 200:
                error_msg = f"Erro no refresh: {response.status_code} - {response.text}"
                logger.error(error_msg)
                
                if "invalid_grant" in response.text.lower():
                    logger.warning(f"Refresh token expirado para empresa {company.name}")
                    company.moloni_access_token = None
                    company.moloni_refresh_token = None
                    company.token_expires_at = None
                    company.token_last_refreshed = None
                    company.save()
                    return False, None, "Refresh token expirado - re-autenticação necessária"
                
                return False, None, error_msg
            
            token_data = response.json()
            new_access_token = token_data.get('access_token')
            new_refresh_token = token_data.get('refresh_token', company.moloni_refresh_token)
            expires_in = token_data.get('expires_in', 3600)
            
            if not new_access_token:
                logger.error("Novo access token não recebido na resposta")
                return False, None, "Novo access token não recebido"
            
            company.moloni_access_token = new_access_token
            company.moloni_refresh_token = new_refresh_token
            company.token_last_refreshed = timezone.now()
            company.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
            company.save()
            
            logger.info(f"Token renovado com sucesso para empresa {company.name} - Expira em {expires_in/60:.0f} min")
            return True, new_access_token, "Token renovado com sucesso"
            
        except Exception as e:
            error_msg = f"Erro ao renovar token: {str(e)}"
            logger.exception(error_msg)
            return False, None, error_msg

    @staticmethod
    def ensure_valid_token(company):
        try:
            if not company.moloni_access_token:
                return False, None, "Sem token - autenticação necessária"
            
            if not company.needs_access_token_refresh():
                return True, company.moloni_access_token, "Token válido"
            
            if company.needs_reauth():
                return False, None, "Refresh token expirado - re-autenticação necessária"
            
            success, new_token, error = MoloniService.refresh_access_token(company)
            
            if success:
                return True, new_token, "Token renovado"
            else:
                return False, None, error
            
        except Exception as e:
            error_msg = f"Erro ao verificar token: {str(e)}"
            logger.exception(error_msg)
            return False, None, error_msg

    @staticmethod
    def _make_authenticated_request(url, company, method='GET', data=None, max_retries=1):        
        for attempt in range(max_retries + 1):
            try:
                success, current_token, error = MoloniService.ensure_valid_token(company)
                
                if not success:
                    logger.error(f"Token inválido para {company.name}: {error}")
                    return False, None, error
                
                if method.upper() == 'GET':
                    separator = '&' if '?' in url else '?'
                    params_str = f"company_id={company.company_id}&access_token={current_token}"
                    full_url = f"{url}{separator}{params_str}"
                    
                    logger.debug(f"GET URL: {full_url.replace(current_token, '***TOKEN***')}")
                    response = requests.get(full_url)
                
                else:
                    if data is None:
                        data = {}
                    
                    data['company_id'] = company.company_id
                    
                    separator = '&' if '?' in url else '?'
                    full_url = f"{url}{separator}access_token={current_token}"
                    
                    logger.debug(f"POST URL: {full_url.replace(current_token, '***TOKEN***')}")
                    logger.debug(f"POST Data: {data}")
                    
                    response = requests.post(full_url, data=data)
                    
                    if response.status_code != 200:
                        logger.debug("Tentando POST com JSON...")
                        response = requests.post(full_url, json=data)
                
                logger.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 401 and attempt < max_retries:
                    logger.info(f"Token expirado (tentativa {attempt + 1}), forçando refresh...")
                    
                    company.token_expires_at = timezone.now() - timedelta(minutes=1)
                    company.save()
                    
                    continue
                
                if response.status_code == 200:
                    try:
                        return True, response.json(), None
                    except json.JSONDecodeError:
                        return False, None, "Resposta inválida da API"
                else:
                    error_msg = f"Erro da API: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, None, error_msg
                    
            except Exception as e:
                error_msg = f"Erro na requisição: {str(e)}"
                logger.exception(error_msg)
                
                if attempt >= max_retries:
                    return False, None, error_msg
                
                time.sleep(1)
        
        return False, None, "Máximo de tentativas excedido"

    @staticmethod
    def _make_authenticated_request_encode(url, company, method='POST', form_data=None, max_retries=1):
        for attempt in range(max_retries + 1):
            try:
                success, current_token, error = MoloniService.ensure_valid_token(company)
                
                if not success:
                    logger.error(f"Token inválido para {company.name}: {error}")
                    return False, None, error
                
                if form_data is None:
                    form_data = {}
                
                form_data['company_id'] = company.company_id
                
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                separator = '&' if '?' in url else '?'
                full_url = f"{url}{separator}access_token={current_token}"
                
                data_string = urlencode(form_data)
                
                logger.debug(f"FORM POST URL: {full_url.replace(current_token, '***TOKEN***')}")
                logger.debug(f"FORM Data keys: {list(form_data.keys())}")
                
                if method.upper() == 'POST':
                    response = requests.post(full_url, data=data_string, headers=headers)
                else:
                    raise ValueError(f"Método {method} não suportado para form-urlencoded")
                
                logger.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 401 and attempt < max_retries:
                    logger.info(f"Token expirado (tentativa {attempt + 1}), forçando refresh...")
                    
                    company.token_expires_at = timezone.now() - timedelta(minutes=1)
                    company.save()
                    
                    continue
                
                if response.status_code == 200:
                    try:
                        return True, response.json(), None
                    except json.JSONDecodeError:
                        return False, None, "Resposta inválida da API"
                else:
                    error_msg = f"Erro da API: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return False, None, error_msg
                    
            except Exception as e:
                error_msg = f"Erro na requisição form-urlencoded: {str(e)}"
                logger.exception(error_msg)
                
                if attempt >= max_retries:
                    return False, None, error_msg
                
                time.sleep(1)
        
        return False, None, "Máximo de tentativas excedido"

    @staticmethod
    def fetch_and_store_categories(company):
        try:
            logger.info(f"Buscando categorias para empresa: {company.name}")
            
            url = "https://api.moloni.pt/v1/productCategories/getAll/"
            data = {"parent_id": 0}
            
            success, response_data, error = MoloniService._make_authenticated_request(
                url, company, method='POST', data=data
            )
            
            if not success:
                return False, f"Erro ao buscar categorias: {error}", 0
            
            if not isinstance(response_data, list):
                return False, "Formato de resposta inesperado", 0
            
            logger.info(f"Encontradas {len(response_data)} categorias")
            
            with transaction.atomic():
                count = 0
                
                for category_data in response_data:
                    category_id = category_data.get("category_id")
                    name = category_data.get("name", "")
                    
                    if category_id and name:
                        Category.objects.update_or_create(
                            category_id=category_id,
                            company=company,
                            defaults={
                                'name': name,
                                'parent_id': 0,
                                'num_categories': category_data.get("num_categories", 0),
                                'num_products': category_data.get("num_products", 0),
                            }
                        )
                        count += 1
                
                logger.info(f"Categorias processadas: {count}")
            
            return True, f"Importadas {count} categorias", count
            
        except Exception as e:
            logger.exception(f"Erro ao processar categorias: {str(e)}")
            return False, f"Erro: {str(e)}", 0

    @staticmethod
    def sync_categories_with_moloni(company, force_sync=False):
        try:
            if not force_sync and not MoloniService.should_sync(company.id, 'categories', 10):
                current_count = Category.objects.filter(company=company).count()
                return True, f"Sincronização em cooldown - {current_count} categorias existentes", 0
            
            logger.info(f"🚀 Iniciando sincronização de categorias para empresa: {company.name}")
            
            url = "https://api.moloni.pt/v1/productCategories/getAll/"
            data = {"parent_id": 0}
            
            api_cache_key = MoloniService.get_api_cache_key(company.id, 'categories_sync')
            cached_response = cache.get(api_cache_key)
            
            if cached_response:
                logger.debug(f"📦 Response da API do cache para empresa {company.name}")
                response_data = cached_response
                success = True
                error = None
            else:
                success, response_data, error = MoloniService._make_authenticated_request(
                    url, company, method='POST', data=data
                )
                
                if success:
                    cache.set(api_cache_key, response_data, 600)
                    logger.debug(f"💾 Response da API cached para empresa {company.name}")
            
            if not success:
                return False, f"Erro ao buscar categorias: {error}", 0
            
            if not isinstance(response_data, list):
                return False, "Formato de resposta inesperado", 0
            
            moloni_category_ids = set()
            for category_data in response_data:
                category_id = category_data.get("category_id")
                if category_id:
                    moloni_category_ids.add(category_id)
            
            with transaction.atomic():
                success, message, count = MoloniService.fetch_and_store_categories(company)
                
                if not success:
                    return False, message, 0
                
                removed_count = 0
                if moloni_category_ids:
                    categories_to_remove = Category.objects.filter(
                        company=company
                    ).exclude(category_id__in=moloni_category_ids)
                    
                    removed_count = categories_to_remove.count()
                    if removed_count > 0:
                        logger.info(f"🗑️ Removendo {removed_count} categorias que não existem no Moloni")
                        categories_to_remove.delete()
                
                total_operations = count + removed_count
                final_message = f"Sincronização concluída - Processadas: {count}, Removidas: {removed_count}"
                
                MoloniService.mark_sync_completed(company.id, 'categories', 10)
                
                logger.info(f"✅ {final_message}")
                return True, final_message, total_operations
                
        except Exception as e:
            logger.exception(f"❌ Erro na sincronização de categorias: {str(e)}")
            return False, f"Erro: {str(e)}", 0

    @staticmethod
    def fetch_and_store_suppliers(company):
        try:
            logger.info(f"Buscando fornecedores para empresa: {company.name}")
            
            supplier_markups = {name.upper(): markup for code, name, markup in suppliers_data}
            supplier_markups_by_code = {code: markup for code, name, markup in suppliers_data}
            
            url = "https://api.moloni.pt/v1/suppliers/getAll/"
            
            success, response_data, error = MoloniService._make_authenticated_request(
                url, company, method='POST', data={}
            )
            
            if not success:
                return False, f"Erro ao buscar fornecedores: {error}", 0
            
            if not isinstance(response_data, list):
                return False, "Formato de resposta inesperado", 0
            
            logger.info(f"Encontrados {len(response_data)} fornecedores")
            
            with transaction.atomic():
                count = 0
                
                for supplier_data in response_data:
                    supplier_id = supplier_data.get("supplier_id")
                    number = supplier_data.get("number", "")
                    name = supplier_data.get("name", "")
                    
                    if supplier_id and name:
                        markup = None
                        
                        if name.upper() in supplier_markups:
                            markup = supplier_markups[name.upper()]
                        else:
                            for supplier_name, markup_value in supplier_markups.items():
                                if supplier_name in name.upper() or name.upper() in supplier_name:
                                    markup = markup_value
                                    break
                        
                        if markup is None and number in supplier_markups_by_code:
                            markup = supplier_markups_by_code[number]
                        
                        if markup is None:
                            markup = 2.5
                        
                        code = number[:2] if number else str(supplier_id)[-2:]
                        
                        supplier, created = Supplier.objects.update_or_create(
                            supplier_id=supplier_id,
                            defaults={
                                'code': code,
                                'name': name,
                                'company': company,
                            }
                        )
                        
                        if created or not supplier.markups.filter(is_active=True).exists():
                            existing_markup = supplier.markups.filter(markup=markup).first()
                            
                            if existing_markup:
                                supplier.markups.update(is_active=False)
                                existing_markup.is_active = True
                                existing_markup.save()
                            else:
                                from django.contrib.auth.models import User
                                system_user = User.objects.filter(is_superuser=True).first()
                                if not system_user:
                                    system_user, _ = User.objects.get_or_create(
                                        username='system',
                                        defaults={
                                            'email': 'system@moloni-sync.com',
                                            'first_name': 'Sistema',
                                            'last_name': 'Moloni Sync'
                                        }
                                    )
                                
                                supplier.markups.update(is_active=False)
                                
                                SupplierMarkup.objects.create(
                                    supplier=supplier,
                                    markup=markup,
                                    created_by=system_user,
                                    is_active=True
                                )
                        
                        count += 1
                
                logger.info(f"Fornecedores processados: {count}")
            
            return True, f"Importados {count} fornecedores", count
            
        except Exception as e:
            logger.exception(f"Erro ao processar fornecedores: {str(e)}")
            return False, f"Erro: {str(e)}", 0

    @staticmethod
    def fetch_and_store_taxes(company):
        try:
            logger.info(f"Buscando impostos para empresa: {company.name}")
            
            url = "https://api.moloni.pt/v1/taxes/getAll/"
            
            success, response_data, error = MoloniService._make_authenticated_request(
                url, company, method='POST', data={}
            )
            
            if not success:
                return False, f"Erro ao buscar impostos: {error}", 0
            
            if not isinstance(response_data, list):
                return False, "Formato de resposta inesperado", 0
            
            logger.info(f"Encontrados {len(response_data)} impostos")
            
            with transaction.atomic():
                count = 0
                
                for tax_data in response_data:
                    tax_id = tax_data.get("tax_id")
                    name = tax_data.get("name", "")
                    value = tax_data.get("value", "")
                    
                    if tax_id and name and value:
                        Tax.objects.update_or_create(
                            tax_id=tax_id,
                            company=company,
                            defaults={
                                'name': name,
                                'value': value,
                            }
                        )
                        count += 1
                
                logger.info(f"Impostos processados: {count}")
            
            return True, f"Importados {count} impostos", count
            
        except Exception as e:
            logger.exception(f"Erro ao processar impostos: {str(e)}")
            return False, f"Erro: {str(e)}", 0

    @staticmethod
    def fetch_and_store_measurement_units(company):
        """✅ NOVA ASSINATURA: apenas (company)"""
        try:
            logger.info(f"Buscando unidades de medida para empresa: {company.name}")
            
            url = "https://api.moloni.pt/v1/measurementUnits/getAll/"
            
            success, response_data, error = MoloniService._make_authenticated_request(
                url, company, method='POST', data={}
            )
            
            if not success:
                return False, f"Erro ao buscar unidades: {error}", 0
            
            if not isinstance(response_data, list):
                return False, "Formato de resposta inesperado", 0
            
            logger.info(f"Encontradas {len(response_data)} unidades de medida")
            
            with transaction.atomic():
                count = 0
                
                for unit_data in response_data:
                    unit_id = unit_data.get("unit_id")
                    name = unit_data.get("name", "")
                    short_name = unit_data.get("short_name", "")
                    
                    if unit_id and name and short_name:
                        Unit.objects.update_or_create(
                            unit_id=unit_id,
                            company=company,
                            defaults={
                                'name': name,
                                'short_name': short_name,
                            }
                        )
                        count += 1
                
                logger.info(f"Unidades processadas: {count}")
            
            return True, f"Importadas {count} unidades", count
            
        except Exception as e:
            logger.exception(f"Erro ao processar unidades: {str(e)}")
            return False, f"Erro: {str(e)}", 0

    @staticmethod
    def check_moloni_session(access_token, company_id=None):
        """Verifica se a sessão do Moloni está ativa"""
        try:
            response = requests.get(
                f"https://api.moloni.pt/v1/companies/getAll/?access_token={access_token}"
            )
            
            if response.status_code != 200:
                return {
                    "valid": False,
                    "message": "Erro de conexão com o Moloni"
                }
            
            companies = response.json()
            
            if not companies or not isinstance(companies, list):
                return {
                    "valid": False,
                    "message": "Nenhuma empresa disponível no Moloni"
                }
            
            if company_id:
                company_found = False
                for company in companies:
                    if company.get('company_id') == company_id:
                        company_found = True
                        company_info = company
                        break
                        
                if not company_found:
                    return {
                        "valid": False,
                        "message": f"Empresa {company_id} não encontrada no Moloni"
                    }
                    
                return {
                    "valid": True,
                    "message": "Sessão válida",
                    "company": company_info
                }
            
            return {
                "valid": True,
                "message": "Sessão válida",
                "companies": companies
            }
            
        except Exception as e:
            logger.exception(f"Erro ao verificar sessão do Moloni: {str(e)}")
            
            return {
                "valid": False,
                "message": f"Erro ao verificar sessão: {str(e)}"
            }