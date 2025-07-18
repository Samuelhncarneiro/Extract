# apps/aitigos/urls.py
from django.urls import path
from .views import AitigosView, SyncToMoloniView, SyncToShopifyView, SyncToBothView, ProductEditView, ProductComparisonView, FilteredSyncView


urlpatterns = [
    path(
        "aitigos/",
        AitigosView.as_view(template_name="aitigos.html"),
        name="aitigos",
    ),
    path('api/sync-products/', SyncToMoloniView.as_view(), name='sync_to_moloni'),
    path('api/sync-shopify/', SyncToShopifyView.as_view(), name='sync_shopify'),
    path('api/sync-both/', SyncToBothView.as_view(), name='sync_both'),
    path('edit/', ProductEditView.as_view(), name='product_edit'),

    path('api/compare-products/', ProductComparisonView.as_view(), name='compare_products'),
    path('api/sync-filtered/', FilteredSyncView.as_view(), name='sync_filtered'),
]