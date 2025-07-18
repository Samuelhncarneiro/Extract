from django.core.cache import cache
import logging
import json

logger = logging.getLogger(__name__)

class AitigosCacheManager:    
    # ===== CACHE TIMEOUTS =====
    DROPDOWN_DATA_TIMEOUT = 1800    # 30 minutos
    COMPANY_CONFIG_TIMEOUT = 900    # 15 minutos
    API_RESPONSE_TIMEOUT = 300      # 5 minutos
    PRODUCTS_SESSION_TIMEOUT = 3600 # 1 hora
    
    # ===== CACHE KEYS =====
    @staticmethod
    def get_dropdown_cache_key(company_id, data_type):
        return f"aitigos:dropdown:{data_type}:company:{company_id}"
    
    @staticmethod
    def get_company_config_cache_key(company_id):
        return f"aitigos:company_config:company:{company_id}"
    
    @staticmethod
    def get_products_session_cache_key(user_id, session_id):
        return f"aitigos:products_session:user:{user_id}:session:{session_id}"
    
    # ===== DROPDOWN DATA CACHE =====
    @staticmethod
    def get_cached_categories(company_id):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'categories')
        return cache.get(cache_key)
    
    @staticmethod
    def cache_categories(company_id, categories_data):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'categories')
        cache.set(cache_key, categories_data, AitigosCacheManager.DROPDOWN_DATA_TIMEOUT)
    
    @staticmethod
    def get_cached_suppliers(company_id):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'suppliers')
        return cache.get(cache_key)
    
    @staticmethod
    def cache_suppliers(company_id, suppliers_data):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'suppliers')
        cache.set(cache_key, suppliers_data, AitigosCacheManager.DROPDOWN_DATA_TIMEOUT)
    
    @staticmethod
    def get_cached_brands(company_id):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'brands')
        return cache.get(cache_key)
    
    @staticmethod
    def cache_brands(company_id, brands_data):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'brands')
        cache.set(cache_key, brands_data, AitigosCacheManager.DROPDOWN_DATA_TIMEOUT)
    
    @staticmethod
    def get_cached_colors(company_id):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'colors')
        return cache.get(cache_key)
    
    @staticmethod
    def cache_colors(company_id, colors_data):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'colors')
        cache.set(cache_key, colors_data, AitigosCacheManager.DROPDOWN_DATA_TIMEOUT)
    
    @staticmethod
    def get_cached_sizes(company_id):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'sizes')
        return cache.get(cache_key)
    
    @staticmethod
    def cache_sizes(company_id, sizes_data):
        cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, 'sizes')
        cache.set(cache_key, sizes_data, AitigosCacheManager.DROPDOWN_DATA_TIMEOUT)
    
    # ===== COMPANY CONFIG CACHE =====
    @staticmethod
    def get_cached_company_config(company_id):
        cache_key = AitigosCacheManager.get_company_config_cache_key(company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_company_config(company_id, config_data):
        cache_key = AitigosCacheManager.get_company_config_cache_key(company_id)
        cache.set(cache_key, config_data, AitigosCacheManager.COMPANY_CONFIG_TIMEOUT)
    
    # ===== PRODUCTS SESSION CACHE =====
    @staticmethod
    def get_cached_products_session(user_id, session_id):
        cache_key = AitigosCacheManager.get_products_session_cache_key(user_id, session_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_products_session(user_id, session_id, products_data):
        cache_key = AitigosCacheManager.get_products_session_cache_key(user_id, session_id)
        cache.set(cache_key, products_data, AitigosCacheManager.PRODUCTS_SESSION_TIMEOUT)
    
    # ===== INVALIDAÇÃO =====
    @staticmethod
    def invalidate_dropdown_cache(company_id, data_type=None):
        if data_type:
            cache_key = AitigosCacheManager.get_dropdown_cache_key(company_id, data_type)
            cache.delete(cache_key)
        else:
            data_types = ['categories', 'suppliers', 'brands', 'colors', 'sizes']
            cache_keys = [
                AitigosCacheManager.get_dropdown_cache_key(company_id, dt) 
                for dt in data_types
            ]
            cache.delete_many(cache_keys)
    
    @staticmethod
    def invalidate_company_config(company_id):
        cache_key = AitigosCacheManager.get_company_config_cache_key(company_id)
        cache.delete(cache_key)
    
    @staticmethod
    def invalidate_all_for_company(company_id):
        AitigosCacheManager.invalidate_dropdown_cache(company_id)
        AitigosCacheManager.invalidate_company_config(company_id)
