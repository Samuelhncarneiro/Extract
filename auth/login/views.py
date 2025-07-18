from django.shortcuts import redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib import messages
from auth.views import AuthView
from django.contrib.messages import get_messages

class LoginView(AuthView):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("index")

        storage = get_messages(request)
        filtered_messages = []
        for message in storage:
            if 'Shopify' not in str(message) and 'loja' not in str(message):
                messages.add_message(request, message.level, message.message, message.tags)

        return super().get(request)

    def post(self, request):
        if request.method == "POST":
            username = request.POST.get("email-username")
            password = request.POST.get("password")

            if not (username and password):
                messages.error(request, "Please enter your username and password.")
                return redirect("login")

            if "@" in username:
                user_email = User.objects.filter(email=username).first()
                if user_email is None:
                    messages.error(request, "Please enter a valid email.")
                    return redirect("login")
                username = user_email.username

            user_email = User.objects.filter(username=username).first()
            if user_email is None:
                messages.error(request, "Please enter a valid username.")
                return redirect("login")

            authenticated_user = authenticate(request, username=username, password=password)
            if authenticated_user is not None:
                # Login the user if authentication is successful
                login(request, authenticated_user)

                # Redirect to the page the user was trying to access before logging in
                if "next" in request.POST:
                    return redirect(request.POST["next"])
                else: # Redirect to the home page or another appropriate page
                    return redirect("index")
            else:
                messages.error(request, "Please enter a valid username.")
                return redirect("login")
