# app/sechic/urls.py
from django.urls import path
from django.views.generic.base import RedirectView
from . import views

urlpatterns = [
    # Redireciona /sechic/sechic/ para /sechic/
    path('sechic/', RedirectView.as_view(url='/sechic/', permanent=True)),

    # URL para renderizar a página principal
    path('', views.SechicView.as_view(), name='sechic'),

    # URLs para listar todos os itens
    path('api/colors/', views.get_colors, name='get_colors'),
    path('api/sizes/', views.get_sizes, name='get_sizes'),
    path('api/categories/', views.get_categories, name='get_categories'),
    path('api/brands/', views.get_brands, name='get_brands'),
    path('api/suppliers/', views.get_suppliers, name='get_suppliers'),

    # URLs CRUD para Color
    path('api/colors/create/', views.ColorCreateView.as_view(), name='color_create'),
    path('api/colors/<str:code>/', views.ColorDetailView.as_view(), name='color_detail'),
    path('api/colors/<str:code>/update/', views.ColorUpdateView.as_view(), name='color_update'),
    path('api/colors/<str:code>/delete/', views.ColorDeleteView.as_view(), name='color_delete'),

    # URLs CRUD para Size
    path('api/sizes/create/', views.SizeCreateView.as_view(), name='size_create'),
    path('api/sizes/<str:code>/', views.SizeDetailView.as_view(), name='size_detail'),
    path('api/sizes/<str:code>/update/', views.SizeUpdateView.as_view(), name='size_update'),
    path('api/sizes/<str:code>/delete/', views.SizeDeleteView.as_view(), name='size_delete'),

    # URLs CRUD para Brand
    path('api/brands/create/', views.BrandCreateView.as_view(), name='brand_create'),
    path('api/brands/<str:name>/', views.BrandDetailView.as_view(), name='brand_detail'),
    path('api/brands/<str:name>/update/', views.BrandUpdateView.as_view(), name='brand_update'),
    path('api/brands/<str:name>/delete/', views.BrandDeleteView.as_view(), name='brand_delete'),

    # URLs CRUD para Category
    path('categories/<str:name>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('categories/<str:name>/update/', views.CategoryUpdateView.as_view(), name='category_update'),

    # URLs CRUD para Supplier
    path('suppliers/<str:code>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<str:code>/add-markup/', views.SupplierAddMarkupView.as_view(), name='supplier_add_markup'),
    path('suppliers/<str:code>/set-active-markup/', views.SupplierSetActiveMarkupView.as_view(), name='supplier_set_active_markup'),
]