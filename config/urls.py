# apps/config/urls.py
from django.contrib import admin
from django.urls import include, path
from web_project.views import SystemView
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # redirect to the landing page
    path("", RedirectView.as_view(url='/landing/', permanent=True)),

    # dashboard urls
    path("dashboard/", include("apps.dashboard.urls")),
    
    # pages urls
    path("pages/", include("apps.pages.urls")),

    # landing urls
    path("landing/", include("apps.landing.urls")),

    # aitigos urls
    path("aitigos/", include("apps.aitigos.urls")),

    # sechic urls
    path("sechic/", include("apps.sechic.urls")),

    # auth urls
    path("", include("auth.urls")),
    
    path('moloni/', include('apps.moloni.urls')),

    path('product-moloni/', include('apps.product_moloni.urls')),

    path('product-shopify/', include('apps.product_shopify.urls')),

    path('shopify/', include('apps.shopify.urls', namespace='shopify')),
]

handler404 = SystemView.as_view(template_name="pages_misc_error.html", status=404)
handler403 = SystemView.as_view(template_name="pages_misc_not_authorized.html", status=403)
handler400 = SystemView.as_view(template_name="pages_misc_error.html", status=400)
handler500 = SystemView.as_view(template_name="pages_misc_error.html", status=500)

# Adiciona URLs para servir arquivos de mídia em modo de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
