from django.views.generic import TemplateView
from web_project import TemplateLayout
from web_project.template_helpers.theme import TemplateHelper
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Profile

"""
This file is a view controller for multiple pages as a module.
Here you can override the page view layout.
Refer to auth/urls.py file for more pages.
"""


class AuthView(TemplateView):
    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))

        context.update(
            {
                "layout_path": TemplateHelper.set_layout("layout_blank.html", context),
            }
        )

        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "profile.html"

    def get_context_data(self, **kwargs):
        context = TemplateLayout.init(self, super().get_context_data(**kwargs))
        
        profile = self.request.user.profile
        
        context.update({
            'user': self.request.user,
            'profile': profile,
        })
        
        return context

@login_required
def profile_view_function(request):
    profile = request.user.profile
    
    class MockView:
        def __init__(self, request):
            self.request = request
    
    mock_view = MockView(request)
    context = TemplateLayout.init(mock_view, {})
    
    context.update({
        'user': request.user,
        'profile': profile,
    })
    
    return render(request, 'profile.html', context)