# apps/dashboard/urls.py
from django.urls import path
from .views import DashboardView


urlpatterns = [
    path(
        "",
        DashboardView.as_view(template_name="dashboard.html"),
        name="index",
    ),

]
