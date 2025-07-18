# apps/dashboard/views.py
from django.views.generic import TemplateView
from web_project import TemplateLayout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils import translation
from django.contrib import messages
from django.urls import reverse

from apps.shopify.models import Shopify
from apps.moloni.models import Moloni

import logging
logger = logging.getLogger(__name__)

class DashboardView(LoginRequiredMixin, TemplateView):

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        if hasattr(self.request.user, 'profile') and self.request.user.profile.selected_moloni_company:
            company = self.request.user.profile.selected_moloni_company
            
            # Atualizar dados da sessão
            self.request.session.update({
                'selected_company_id': company.company_id,
                'selected_company_name': company.name,
                'selected_company_email': company.email,
                'selected_company_vat': company.vat,
                'selected_company_url_image': company.url_image,
                'access_token': company.moloni_access_token
            })
            
            try:
                token_status = company.get_token_status()
                
                if token_status == 'access_expiring':
                    from apps.sechic.services import MoloniService
                    
                    logger.info(f"Token expirando para {company.name}, fazendo refresh proativo...")
                    success, new_token, error = MoloniService.refresh_access_token(company)
                    
                    if success:
                        self.request.session['access_token'] = new_token
                        self.request.session.modified = True
                        logger.info(f"✅ Token renovado com sucesso no dashboard para {company.name}")
                    else:
                        logger.warning(f"❌ Falha no refresh proativo: {error}")
                
                context.update({
                    'token_status': token_status,
                    'minutes_until_access_expires': company.minutes_until_access_expires(),
                    'days_until_refresh_expires': company.days_until_refresh_expires(),
                })
                
                if token_status == 'refresh_expiring':
                    days_left = company.days_until_refresh_expires()
                    if not self.request.session.get('moloni_refresh_warning_shown'):
                        messages.warning(
                            self.request, 
                            f"Autenticação Moloni expira em {days_left} dias. "
                            f"<a href='{reverse('moloni:moloni-login')}' class='alert-link'>Renovar agora</a>"
                        )
                        self.request.session['moloni_refresh_warning_shown'] = True
                        self.request.session.modified = True
                        
            except Exception as e:
                logger.exception(f"Erro ao verificar/renovar token Moloni: {str(e)}")
                messages.warning(
                    self.request,
                    "Problema na verificação da conexão Moloni. "
                    "Se persistir, reconecte sua conta."
                )

        if 'selected_company_id' in self.request.session:
            context.update({
                'selected_company_name': self.request.session.get('selected_company_name', ''),
                'selected_company_vat': self.request.session.get('selected_company_vat', ''),
                'selected_company_email': self.request.session.get('selected_company_email', ''),
                'selected_company_url_image': self.request.session.get('selected_company_url_image', ''),
            })
        
        context.update({
            'has_shopify': Shopify.objects.filter(users=self.request.user, is_active=True).exists(),
            'has_moloni_credentials': hasattr(self.request.user, 'moloni_credentials'),
            'has_moloni_company': hasattr(self.request.user, 'profile') and 
                                 self.request.user.profile.selected_moloni_company is not None,
        })

        return context

@csrf_exempt
def set_dev_settings(request):
    """Função para desenvolvimento - definir configurações manualmente"""
    if request.method == 'POST' and getattr(settings, 'DEBUG', False):        
        company_id = request.POST.get('company_id')
        access_token = request.POST.get('access_token')

        if company_id and access_token:
            request.session['selected_company_id'] = company_id
            request.session['access_token'] = access_token
            request.session.modified = True
            
            logger.info(f"Configurações de desenvolvimento definidas: company_id={company_id}")

        return HttpResponseRedirect('/')
    
    return HttpResponseRedirect('/')