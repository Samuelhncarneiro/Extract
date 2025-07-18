#
# python manage.py runserver --settings=config.settings_local_django

import os
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

from .template import TEMPLATE_CONFIG, THEME_LAYOUT_DIR, THEME_VARIABLES

BASE_DIR = Path(__file__).resolve().parent.parent
# Carregar o arquivo .env.local explicitamente
load_dotenv(BASE_DIR / ".env.local.django")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", default='')           


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", 'True').lower() in ['true', 'yes', '1']


# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = ['http://localhost', 'http://127.0.0.1', 'https://9a9fd065d2b4.ngrok-free.app']
MOLONI_REDIRECT_URI = 'https://9a9fd065d2b4.ngrok-free.app/moloni/callback-moloni/'
     
#Moloni settings
#MOLONI_CLIENT_ID = '24850283'
#MOLONI_CLIENT_SECRET = '21e0b5e4374a815882b82dfcaf264ec3fb5aaba5'

# Current DJANGO_ENVIRONMENT
ENVIRONMENT = os.environ.get("DJANGO_ENVIRONMENT", default="local")

SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY', '')
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_API_SECRET', '')
SHOPIFY_API_VERSION = '2023-10'
SHOPIFY_SCOPE = 'read_products,write_products'

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    "auth.apps.AuthConfig",

    "apps.landing",
    "apps.dashboard",
    "apps.pages",
    "apps.aitigos", 
    "apps.sechic",
    "apps.moloni",
    "apps.product_moloni",
    "apps.product_shopify",
    "apps.shopify",
    
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'apps.shopify.middleware.ShopifyMiddleware',
    'apps.moloni.middleware.MoloniTokenRefreshMiddleware',
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.language_code",
                "config.context_processors.my_setting",
                "config.context_processors.get_cookie",
                "config.context_processors.environment",
            ],
            "libraries": {
                "theme": "web_project.template_tags.theme",
            },
            "builtins": [
                "django.templatetags.static",
                "web_project.template_tags.theme",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME',''),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': '5432',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

# Enable i18n and set the list of supported languages
LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("ar", _("Arabic")),
    ("de", _("German")),
    # Add more languages as needed
]

# Set default language
# ! Make sure you have cleared the browser cache after changing the default language
LANGUAGE_CODE = "en"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# Configuração para arquivos estáticos locais
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Diretórios adicionais para arquivos estáticos (caso existam)
STATICFILES_DIRS = [
    BASE_DIR / "src" / "assets",
]

# Configuração para arquivos de mídia locais
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Definir STORAGES para uso local (Django 4+)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}



# Default URL on which Django application runs for specific environment
BASE_URL = os.environ.get("BASE_URL", default="http://127.0.0.1:8000")


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Template Settings
# ------------------------------------------------------------------------------

THEME_LAYOUT_DIR = THEME_LAYOUT_DIR
TEMPLATE_CONFIG = TEMPLATE_CONFIG
THEME_VARIABLES = THEME_VARIABLES

# Create Folder STATIC_ROOT if not exists
# ------------------------------------------------------------------------------
import os
if not os.path.exists(STATIC_ROOT):
    os.makedirs(STATIC_ROOT)

# Configuração de sessões
SESSION_ENGINE = os.getenv("SESSION_ENGINE", "django.contrib.sessions.backends.db")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() in ["true", "1"]
SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "True").lower() in ["true", "1"]
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "3600"))

LOGIN_URL = os.getenv("LOGIN_URL", "/login/")
LOGOUT_REDIRECT_URL = os.getenv("LOGOUT_REDIRECT_URL", "/login/")
