# apps/shopify/views.py
import shopify
import os
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import FormView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from web_project import TemplateLayout
from django.views import View
from django.conf import settings

from django.contrib.auth.models import User
from auth.models import Profile

from .forms import ShopifyCredentialsForm
from .models import Shopify

SCOPES = [
    'read_products',      
    'write_products',   
    'read_inventory',    
    'write_inventory',  
    'read_locations',
]

@method_decorator(login_required, name='dispatch')
class ShopifyConnectionView(FormView):
    template_name = 'shop_form.html'
    form_class = ShopifyCredentialsForm
    success_url = reverse_lazy('index')
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context
    
    def form_valid(self, form):
        shopify_store = form.save(commit=False)
        
        try:
            shop_url = shopify_store.shop_domain
            token = shopify_store.access_token
            
            # Verifique se a URL da loja tem o formato correto
            if not shop_url.startswith('https://'):
                if not shop_url.endswith('myshopify.com'):
                    shop_url = f"{shop_url}.myshopify.com"
                shop_url = f"https://{shop_url}"
            
            # Criar sessão com a versão mais recente da API
            api_session = shopify.Session(shop_url, '2023-10', token)
            shopify.ShopifyResource.activate_session(api_session)
            
            # Verificar se o token tem acesso aos escopos necessários
            try:
                shop = shopify.Shop.current()
                shopify_store.save()

                shopify_store.users.add(self.request.user)

                if not shopify_store.email:
                    shopify_store.email = shop.email
                                    
                profile = self.request.user.profile
                profile.selected_shopify_store = shopify_store
                profile.save()

                self.request.session['selected_shopify_domain'] = shop_url
                self.request.session['selected_shopify_email'] = shopify_store.email
                
                messages.success(self.request, f"Loja {shopify_store.shop_domain} conectada com sucesso!")
                
            except Exception as e:
                error_message = str(e)
                if "requires merchant approval for" in error_message:
                    return redirect('shopify:authenticate', shop_domain=shopify_store.shop_domain)
                else:
                    messages.error(self.request, f"Erro ao acessar a loja: {error_message}")
                    return self.form_invalid(form)
            finally:
                # Limpar a sessão
                shopify.ShopifyResource.clear_session()
            
        except Exception as e:
            messages.error(self.request, f"Erro ao conectar com a loja: {str(e)}")
            return self.form_invalid(form)
            
        return super().form_valid(form)

@method_decorator(login_required, name='dispatch')
class ShopifyAuthenticateView(View):
    """
    View para lidar com o processo de autenticação OAuth do Shopify
    """
    def get(self, request, *args, **kwargs):
        shop_domain = kwargs.get('shop_domain')
        api_key = os.environ.get('SHOPIFY_API_KEY', '')
        api_secret = os.environ.get('SHOPIFY_API_SECRET', '')
        redirect_uri = request.build_absolute_uri(reverse_lazy('shopify:callback'))
        
        if not all([api_key, api_secret, shop_domain]):
            messages.error(request, "Configuração incompleta. Verifique API Key e Secret.")
            return redirect('shopify:connect')
        
        # Normalizar domínio da loja
        if not shop_domain.endswith('myshopify.com'):
            shop_domain = f"{shop_domain}.myshopify.com"
        
        # Configurar a autenticação
        shopify.Session.setup(api_key=api_key, secret=api_secret)
        
        # Criar URL de autorização com os escopos necessários
        scopes = ','.join(SCOPES)
        
        # Criar nova sessão para obter URL de autorização
        shop_session = shopify.Session(shop_domain, '2023-10')
        auth_url = shop_session.create_permission_url(scopes, redirect_uri)
        
        # Salvar dados da sessão para uso posterior
        request.session['shopify_shop_domain'] = shop_domain
        
        # Redirecionar para o Shopify para autorização
        return HttpResponseRedirect(auth_url)

@method_decorator(login_required, name='dispatch')
class ShopifyCallbackView(View):
    def get(self, request, *args, **kwargs):
        # Configurar variáveis de API
        api_key = os.environ.get('SHOPIFY_API_KEY', '')
        api_secret = os.environ.get('SHOPIFY_API_SECRET', '')
        
        # Recuperar dados da sessão
        shop_domain = request.session.get('shopify_shop_domain', '')
        
        if not all([api_key, api_secret, shop_domain]):
            messages.error(request, "Dados da sessão perdidos. Tente novamente.")
            return redirect('shopify:connect')
        
        # Configurar a autenticação
        shopify.Session.setup(api_key=api_key, secret=api_secret)
        
        # Criar sessão e obter token permanente
        shop_session = shopify.Session(shop_domain, '2023-10')
        
        try:
            # Validar e obter token permanente
            token = shop_session.request_token(request.GET)
            
            # Ativar sessão com o token para testar e recuperar dados da loja
            shopify.ShopifyResource.activate_session(shop_session)
            
            shop = shopify.Shop.current()
            
            # Salvar ou atualizar loja no banco de dados
            shopify_store, created = Shopify.objects.update_or_create(
                shop_domain=shop_domain,
                defaults={
                    'access_token': token,
                    'email': shop.email,
                    'is_active': True
                }
            )
            shopify_store.save()
            shopify_store.users.add(request.user)

            profile = request.user.profile
            profile.selected_shopify_store = shopify_store
            profile.save()

            # Salvar dados na sessão
            request.session['selected_shopify_domain'] = shop_domain
            request.session['selected_shopify_name'] = shop.name
            request.session['selected_shopify_email'] = shop.email
            
            messages.success(request, f"Loja {shop.name} conectada com sucesso com as permissões necessárias!")
            
            try:
                if '.myshopify.com' in shop_domain:
                    shop_name = shop_domain.split('.myshopify.com')[0]
                else:
                    shop_name = shop_domain.split('.')[0]
                
                from apps.product_shopify.services import ShopifyService
                
                ShopifyService.fetch_and_store_products(
                    shop_name=shop_name,
                    access_token=token,
                    force_update=False  
                )
                
                messages.info(request, "Sincronização inicial de produtos iniciada. Isso pode levar alguns minutos.")
                
            except Exception as sync_error:
                logger.exception(f"Erro ao sincronizar produtos após conexão: {str(sync_error)}")
                messages.warning(request, 
                    "Loja conectada com sucesso, mas houve um erro na sincronização inicial de produtos. "
                    "Você pode sincronizar manualmente na página de produtos."
                )
            
        except Exception as e:
            messages.error(request, f"Erro no processo de autenticação: {str(e)}")
        finally:
            # Sempre limpar a sessão 
            shopify.ShopifyResource.clear_session()
        
        return redirect('index')