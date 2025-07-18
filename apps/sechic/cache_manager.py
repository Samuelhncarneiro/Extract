from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class SechicCacheManager:    
    # ===== CACHE TIMEOUTS =====
    COUNTS_TIMEOUT = 300      
    COLORS_TIMEOUT = 600      
    SIZES_TIMEOUT = 600      
    BRANDS_TIMEOUT = 600   
    CATEGORIES_TIMEOUT = 300  
    SUPPLIERS_TIMEOUT = 900
    
    # ===== CACHE KEYS =====
    @staticmethod
    def get_view_cache_key(data_type, company_id):
        return f"sechic:view:{data_type}:company:{company_id}"
    
    @staticmethod
    def get_counts_cache_key(company_id):
        return f"sechic:counts:company:{company_id}"
    
    # ===== COUNTS CACHE =====
    @staticmethod
    def get_cached_counts(company_id):
        cache_key = SechicCacheManager.get_counts_cache_key(company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_counts(company_id, counts_data):
        cache_key = SechicCacheManager.get_counts_cache_key(company_id)
        cache.set(cache_key, counts_data, SechicCacheManager.COUNTS_TIMEOUT)
    
    # ===== COLORS CACHE =====
    @staticmethod
    def get_cached_colors(company_id):
        cache_key = SechicCacheManager.get_view_cache_key('colors', company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_colors(company_id, colors_data):
        cache_key = SechicCacheManager.get_view_cache_key('colors', company_id)
        cache.set(cache_key, colors_data, SechicCacheManager.COLORS_TIMEOUT)
    
    # ===== SIZES CACHE =====
    @staticmethod
    def get_cached_sizes(company_id):
        cache_key = SechicCacheManager.get_view_cache_key('sizes', company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_sizes(company_id, sizes_data):
        cache_key = SechicCacheManager.get_view_cache_key('sizes', company_id)
        cache.set(cache_key, sizes_data, SechicCacheManager.SIZES_TIMEOUT)
    
    # ===== BRANDS CACHE =====
    @staticmethod
    def get_cached_brands(company_id):
        cache_key = SechicCacheManager.get_view_cache_key('brands', company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_brands(company_id, brands_data):
        cache_key = SechicCacheManager.get_view_cache_key('brands', company_id)
        cache.set(cache_key, brands_data, SechicCacheManager.BRANDS_TIMEOUT)
    
    # ===== CATEGORIES CACHE =====
    @staticmethod
    def get_cached_categories(company_id):
        cache_key = SechicCacheManager.get_view_cache_key('categories', company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_categories(company_id, categories_data):
        cache_key = SechicCacheManager.get_view_cache_key('categories', company_id)
        cache.set(cache_key, categories_data, SechicCacheManager.CATEGORIES_TIMEOUT)
    
    # ===== SUPPLIERS CACHE =====
    @staticmethod
    def get_cached_suppliers(company_id):
        cache_key = SechicCacheManager.get_view_cache_key('suppliers', company_id)
        return cache.get(cache_key)
    
    @staticmethod
    def cache_suppliers(company_id, suppliers_data):
        cache_key = SechicCacheManager.get_view_cache_key('suppliers', company_id)
        cache.set(cache_key, suppliers_data, SechicCacheManager.SUPPLIERS_TIMEOUT)
    
    # ===== INVALIDAÇÃO =====
    @staticmethod
    def invalidate_view_cache(company_id, data_type=None):
        if data_type:
            cache_key = SechicCacheManager.get_view_cache_key(data_type, company_id)
            cache.delete(cache_key)
            logger.info(f"🗑️ Cache {data_type} invalidado para empresa {company_id}")
        else:
            data_types = ['colors', 'sizes', 'categories', 'brands', 'suppliers']
            cache_keys = [
                SechicCacheManager.get_view_cache_key(dt, company_id) 
                for dt in data_types
            ]
            cache_keys.append(SechicCacheManager.get_counts_cache_key(company_id))
            cache.delete_many(cache_keys)
    
    @staticmethod
    def invalidate_after_data_change(company_id, data_type):
        """Invalidação após mudança de dados"""
        SechicCacheManager.invalidate_view_cache(company_id, data_type)
        cache.delete(SechicCacheManager.get_counts_cache_key(company_id))
