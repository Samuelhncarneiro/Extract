# apps/moloni/views.py

import requests
import urllib.parse
import logging

from django.shortcuts import redirect, render
from django.views.generic import ListView, TemplateView, View
from web_project import TemplateLayout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.contrib.auth.models import User

from auth.models import Profile
from apps.sechic.services import MoloniService
from apps.product_moloni.services import ProductMoloniService
from .models import MoloniCredentials, Moloni

logger = logging.getLogger(__name__)

IMAGE_BASE_URL = "https://www.moloni.pt/_imagens/?macro=imgAC_iconeEmpresa_s4&img="


@login_required
def select_company(request, company_id):
    company = get_object_or_404(Moloni, id=company_id, users=request.user)
    
    request.session['selected_company_id'] = company.company_id
    request.session['selected_company_name'] = company.name
    request.session['selected_company_email'] = company.email
    request.session['selected_company_vat'] = company.vat
    request.session['selected_company_url_image'] = company.url_image
    request.session['access_token'] = company.moloni_access_token
    
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        profile.selected_moloni_company = company
        profile.save()
        logger.info(f"Empresa ID {company.company_id} associada ao perfil do usuário {request.user.username}")
    else:
        try:
            profile = Profile.objects.create(
                user=request.user,
                email=request.user.email,
                selected_moloni_company=company
            )
            logger.info(f"Perfil criado para o usuário {request.user.username}")
        except Exception as e:
            logger.error(f"Erro ao criar perfil para o usuário {request.user.username}: {str(e)}")

    logger.info(f"Selected Company ID: {company.company_id}")
    
    # Buscar dados do Moloni
    messages_list = []
    
    # Categorias
    success, message, count = MoloniService.fetch_and_store_categories(company)
    if success:
        messages_list.append(f"Categorias: {message}")
    else:
        messages_list.append(f"Erro nas categorias: {message}")
    
    # Fornecedores
    success, message, count = MoloniService.fetch_and_store_suppliers(company)
    if success:
        messages_list.append(f"Fornecedores: {message}")
    else:
        messages_list.append(f"Erro nos fornecedores: {message}")
    
    # Impostos
    success, message, count = MoloniService.fetch_and_store_taxes(company)
    if success:
        messages_list.append(f"Impostos: {message}")
    else:
        messages_list.append(f"Erro nos impostos: {message}")
    
    # Unidades de medida
    success, message, count = MoloniService.fetch_and_store_measurement_units(company)
    if success:
        messages_list.append(f"Unidades: {message}")
    else:
        messages_list.append(f"Erro nas unidades: {message}")
    
    # Produtos
    try:
        success_products, message_products, count_products = ProductMoloniService.fetch_and_store_products(company)
        if success_products:
            messages_list.append(f"Produtos: {message_products}")
        else:
            messages_list.append(f"Erro nos produtos: {message_products}")
    except Exception as e:
        logger.error(f"Erro ao buscar produtos: {str(e)}")
        messages_list.append(f"Erro nos produtos: {str(e)}")
    
    company.refresh_from_db()
    request.session['access_token'] = company.moloni_access_token
    
    if any("Erro" in msg for msg in messages_list):
        messages.warning(request, ". ".join(messages_list))
    else:
        messages.success(request, ". ".join(messages_list))
    
    return redirect('index')

@method_decorator(login_required, name='dispatch')
class SelectCompanyView(ListView):
    template_name = 'select_company.html'
    context_object_name = 'companies'
    model = Moloni
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        return context

    def get_queryset(self):        
        return Moloni.objects.filter(users=self.request.user)

@login_required
def moloni_login(request):
    if 'HTTP_REFERER' in request.META:
        request.session['return_after_moloni_auth'] = request.META['HTTP_REFERER']
    request.session.modified = True
    
    try:
        try:
            credentials = MoloniCredentials.objects.get(user=request.user)
            client_id = credentials.client_id
            client_secret = credentials.client_secret
            redirect_uri = credentials.redirect_uri
        except MoloniCredentials.DoesNotExist:
            from django.conf import settings
            client_id = settings.MOLONI_CLIENT_ID
            client_secret = settings.MOLONI_CLIENT_SECRET
            redirect_uri = settings.MOLONI_REDIRECT_URI
            
            MoloniCredentials.objects.create(
                user=request.user,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri
            )
            logger.info(f"Credenciais Moloni criadas para usuário {request.user.username}")
        
        base_url = "https://api.moloni.pt/v1/authorize/"
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
        }
        
        logger.info(f"Iniciando login Moloni com redirect_uri: {redirect_uri}")
        
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        return redirect(url)
        
    except Exception as e:
        logger.exception(f"Erro ao iniciar login Moloni: {str(e)}")
        messages.error(request, f"Erro ao iniciar autenticação: {str(e)}")
        return redirect('dashboard')

@login_required
def moloni_user_callback(request):
    logger.info("Callback recebido do Moloni")
    
    code = request.GET.get('code')
    if not code:
        logger.info("Código de autorização não fornecido")
        messages.error(request, "Código de autorização não fornecido")
        return redirect('dashboard')

    try:
        # Obter credenciais
        try:
            credentials = MoloniCredentials.objects.get(user=request.user)
            client_id = credentials.client_id
            client_secret = credentials.client_secret
            redirect_uri = credentials.redirect_uri
        except MoloniCredentials.DoesNotExist:
            messages.error(request, "Credenciais do Moloni não encontradas")
            return redirect('moloni:config')

        # Trocar código por token
        base_token_url = "https://api.moloni.pt/v1/grant/"
        params = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
        }

        token_url_with_params = f"{base_token_url}?{urllib.parse.urlencode(params)}"
        response = requests.get(token_url_with_params)
        
        if response.status_code != 200:
            messages.error(request, f"Falha ao obter token de acesso: {response.text}")
            return redirect('moloni:config')

        token_data = response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')

        if not access_token:
            messages.error(request, "Token de acesso não encontrado na resposta")
            return redirect('moloni:config')

        # Obter dados do usuário
        user_info_url = f"https://api.moloni.pt/v1/users/getMe/?access_token={access_token}"
        user_info_response = requests.get(user_info_url)
        user_info = user_info_response.json()

        if 'user_id' not in user_info:
            messages.error(request, "Falha ao obter informações do usuário do Moloni")
            return redirect('moloni:config')

        # Obter empresas
        companies_url = f"https://api.moloni.pt/v1/companies/getAll/?access_token={access_token}"
        companies_response = requests.get(companies_url)
        companies_data = companies_response.json()
        
        if not companies_data or not isinstance(companies_data, list):
            messages.error(request, "Falha ao obter lista de empresas do Moloni")
            return redirect('moloni:config')
        
        token_expires_at = timezone.now() + timedelta(hours=1) 

        # Atualizar tokens para todas as empresas
        for company_data in companies_data:
            image = company_data.get('image')
            full_image_url = IMAGE_BASE_URL + image if image is not None else ''

            company, created = Moloni.objects.update_or_create(
                company_id=company_data['company_id'],
                defaults={
                    'name': company_data.get('name', ''),
                    'email': company_data.get('email', ''),
                    'vat': company_data.get('vat', ''),
                    'url_image': full_image_url,
                    'moloni_access_token': access_token,
                    'moloni_refresh_token': refresh_token,
                    'token_last_refreshed': timezone.now(),
                    'token_expires_at': token_expires_at
                }
            )
            company.users.add(request.user)
        
        # Verificar se o usuário já tem uma empresa selecionada
        if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
            selected_company = request.user.profile.selected_moloni_company
            
            # Atualizar tokens
            selected_company.moloni_access_token = access_token
            selected_company.moloni_refresh_token = refresh_token
            selected_company.token_last_refreshed = timezone.now()
            selected_company.token_expires_at = token_expires_at
            selected_company.save()
            
            # Atualizar sessão
            request.session['access_token'] = access_token
            request.session['selected_company_id'] = selected_company.company_id
            request.session['selected_company_name'] = selected_company.name
            request.session['selected_company_email'] = selected_company.email
            request.session['selected_company_vat'] = selected_company.vat
            request.session['selected_company_url_image'] = selected_company.url_image
            
            return_path = request.session.get('return_after_moloni_auth')
            if return_path:
                del request.session['return_after_moloni_auth']
                request.session.modified = True
                
                messages.success(request, "Autenticação renovada com sucesso")
                
                if return_path.startswith('/'):
                    return redirect(return_path)
            
            messages.success(request, f"Conectado à empresa {selected_company.name}")
            return redirect('index')
        
        request.session['companies'] = companies_data
        
        return redirect('moloni:select-company')
        
    except Exception as e:
        logger.exception(f"Erro no callback do Moloni: {str(e)}")
        messages.error(request, f"Erro ao processar autenticação: {str(e)}")
        return redirect('dashboard')

@method_decorator(login_required, name='dispatch')
class ConfigMoloniView(TemplateView):
    template_name = "moloni_config.html"
    
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        try:
            credentials = MoloniCredentials.objects.get(user=self.request.user)
            client_id = credentials.client_id
            client_secret = "********" 
            redirect_uri = credentials.redirect_uri
        except MoloniCredentials.DoesNotExist:
            client_id = ""
            client_secret = ""
            redirect_uri = settings.MOLONI_REDIRECT_URI if hasattr(settings, 'MOLONI_REDIRECT_URI') else self.request.build_absolute_uri(reverse('moloni:moloni-user-callback'))
        context['client_secret'] = client_secret
        context['redirect_uri'] = redirect_uri
        
        return context

@login_required
def save_credentials(request):
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        client_secret = request.POST.get('client_secret')
        redirect_uri = settings.MOLONI_REDIRECT_URI
        
        if not client_id or not client_secret or not redirect_uri:
            messages.error(request, "Todos os campos são obrigatórios")
            return redirect('moloni:config')
        
        MoloniCredentials.objects.update_or_create(
            user=request.user,
            defaults={
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri
            }
        )
        
        messages.success(request, "Credenciais do Moloni salvas com sucesso!")
        return redirect('moloni:moloni-login')
    
    return redirect('moloni:config')