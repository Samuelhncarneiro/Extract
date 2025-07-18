# apps/moloni/middleware.py

import logging
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import Moloni, MoloniCredentials
from apps.sechic.services import MoloniService

logger = logging.getLogger(__name__)

class MoloniTokenRefreshMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Paths que devem ser ignorados pelo middleware
        self.excluded_paths = [
            '/moloni/login/',
            '/moloni/callback/',
            '/moloni/config/',
            '/admin/',
            '/static/',
            '/media/',
        ]
        
    def __call__(self, request):
        # Verificar se deve processar este request
        if not self._should_process_request(request):
            return self.get_response(request)
        
        if request.user.is_authenticated:
            try:
                # Verificar se o usuário tem uma empresa selecionada
                if hasattr(request.user, 'profile') and request.user.profile.selected_moloni_company:
                    company = request.user.profile.selected_moloni_company
                    
                    # Processar refresh de tokens
                    self._process_token_refresh(request, company)
                    
            except Exception as e:
                logger.error(f"Erro no middleware Moloni para usuário {request.user.username}: {str(e)}")
                
        response = self.get_response(request)
        return response
    
    def _should_process_request(self, request):
        """Determina se deve processar este request"""
        # Não processar se não é usuário autenticado
        if not request.user.is_authenticated:
            return False
            
        # Não processar paths excluídos
        current_path = request.path
        for excluded_path in self.excluded_paths:
            if current_path.startswith(excluded_path):
                return False
                
        # Não processar requests AJAX (opcional)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False
            
        return True
    
    def _process_token_refresh(self, request, company):
        """Processa o refresh de tokens para a empresa"""
        try:
            token_status = company.get_token_status()
            
            # Token expirado ou sem token - redirecionar para login
            if token_status in ['no_token', 'expired']:
                logger.info(f"Token expirado para {company.name}, redirecionamento necessário")
                request.session['moloni_token_invalid'] = True
                request.session.modified = True
                return
            
            # Refresh token expirando - avisar usuário
            elif token_status == 'refresh_expiring':
                days_left = company.days_until_refresh_expires()
                if not request.session.get('moloni_refresh_warning_shown'):
                    request.session['moloni_refresh_warning_shown'] = True
                    request.session.modified = True
                    logger.info(f"Aviso de refresh token expirando para {company.name} ({days_left} dias)")
            
            # Access token expirando - fazer refresh automático
            elif token_status == 'access_expiring':
                self._auto_refresh_access_token(request, company)
            
            # Token válido - sincronizar sessão
            elif token_status == 'valid':
                self._sync_session_token(request, company)
                
        except Exception as e:
            logger.exception(f"Erro ao processar refresh de tokens: {str(e)}")
    
    def _auto_refresh_access_token(self, request, company):
        """Faz refresh automático do access token"""
        try:
            from apps.sechic.services import MoloniService
            
            minutes_left = company.minutes_until_access_expires()
            logger.info(f"🔄 Fazendo refresh automático para {company.name} (expira em {minutes_left} min)")
            
            success, new_token, error = MoloniService.refresh_access_token(company)
            
            if success:
                # Atualizar sessão com novo token
                request.session['access_token'] = new_token
                request.session.modified = True
                logger.info(f"✅ Token renovado automaticamente para {company.name}")
                
                # Limpar avisos anteriores
                if 'moloni_refresh_warning_shown' in request.session:
                    del request.session['moloni_refresh_warning_shown']
                    request.session.modified = True
                    
            else:
                logger.warning(f"❌ Falha no refresh automático para {company.name}: {error}")
                
                # Se refresh token expirou, marcar para redirecionamento
                if "re-autenticação necessária" in error:
                    request.session['moloni_token_invalid'] = True
                    request.session.modified = True
                    
        except Exception as e:
            logger.exception(f"Erro no refresh automático: {str(e)}")
    
    def _sync_session_token(self, request, company):
        """Sincroniza o token da sessão com o da empresa"""
        try:
            session_token = request.session.get('access_token')
            if session_token != company.moloni_access_token:
                request.session['access_token'] = company.moloni_access_token
                request.session.modified = True
                logger.debug(f"Token da sessão sincronizado para {company.name}")
                
        except Exception as e:
            logger.warning(f"Erro ao sincronizar token da sessão: {str(e)}")