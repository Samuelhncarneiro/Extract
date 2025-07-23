# Plataforma de Gestão Integrada

![](https://img.shields.io/badge/license-MIT-blue.svg)

![](https://img.shields.io/badge/django-5.0.6-green.svg)

![](https://img.shields.io/badge/python-3.8+-blue.svg)

![](https://img.shields.io/badge/docker-ready-blue.svg)

Uma plataforma moderna e inteligente para gestão integrada de produtos e vendas, conectando **Moloni** e **Shopify** com automatização baseada em IA.

## Visão Geral

O **Aitigos** é uma solução completa para empresas que precisam sincronizar e gerir produtos entre diferentes plataformas:

- **Moloni**: Sistema de faturação e gestão empresarial
- **Shopify**: Plataforma de e-commerce
- **Processamento IA**: Automação inteligente de pdfs de notas de encomend

## Tecnologias

### Backend

- **Django 5.0.6**: Framework web principal
- **Django REST Framework**: API RESTful
- **PostgreSQL**: Base de dados principal
- **Redis**: Cache e sessões
- **Celery**: Tarefas assíncronas

### Frontend

- **Bootstrap 5**: Framework CSS
- **JavaScript ES6+**: Interatividade
- **jQuery**: Manipulação DOM
- **Chart.js**: Gráficos e visualizações

## Arquitetura

```
├── apps/                   # Aplicações Django
│   ├── aitigos/            # App principal com IA
│   ├── dashboard/          # Dashboard executivo
│   ├── landing/            # Página inicial
│   ├── moloni/             # Integração Moloni
│   ├── shopify/            # Integração Shopify
│   ├── product_moloni/     # Gestão produtos Moloni
│   ├── product_shopify/    # Gestão produtos Shopify
│   ├── pages/              # Páginas estáticas
│   └── sechic/             # Módulo auxiliar
├── auth/                   # Sistema de autenticação
├── config/                 # Configurações Django
├── templates/              # Templates HTML
├── staticfiles/            # Ficheiros estáticos
├── src/                    # Assets fonte (SCSS, JS)
└── nginx/                  # Configuração Nginx

```

## Instalação

### Pré-requisitos

- Python 3.12
- Node.js 16+ (para assets)
- PostgreSQL 12+
- Redis 6+
- Docker

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
cd src && npm install

```

### 2. Configurar Base de Dados Local

```bash
# Criar base de dados PostgreSQL
python manage.py makemigrations --settings=config.settings_local_django
# Executar migrações
python manage.py migrate --settings=config.settings_local_django
```

### 3. Configurar Redis local

```bash
# Instalar e iniciar Redis
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# Windows
# Download Redis do site oficial ou usar Docker
```

### 4. Configurar Redis local com docker separado

```bash
# Run Docker
docker-compose -f docker-compose-local.yml up --build
docker run -d --name redis-local -p 6379:6379 redis:latest

#Monitorar Estado
docker exec -it redis-local redis-cli monitor
```

### 5. Criar Super Utilizador Local

```bash
python manage.py createsuperuser --settings=config.settings_local_django
```

### 6. Compilar Assets

```bash
cd src
npm run build
```

### 7. Executar Servidor

### Desenvolvimento Local (sem Docker)

```bash
python manage.py runserver --settings=config.settings_local_django

```

### Produção (sem Docker)

```bash
python manage.py runserver

```

## Configuração

### Variáveis de Ambiente

### Desenvolvimento Local (`.env.local.django`)

```
# Django
DJANGO_SETTINGS_MODULE=config.settings.django
DEBUG=True
DJANGO_ENVIRONMENT=local
SECRET_KEY=K5tRjVxP9qCwZ2gH8sN6mT3dF7aK1pW4eX7yV9uL6kG3jB2tR8qE5zA1rC

# Base URL
BASE_URL=http://127.0.0.1:8000
API_BASE_URL=http://localhost:8001

# Base de Dados PostgreSQL (Local)
DB_NAME= [Name]
DB_USER= [User]
DB_PASSWORD= [Password]
DB_HOST= [Host]
DB_PORT= [Port]

# Red
REDIS_URL=redis://localhost:6379/1

# Sessões
SESSION_ENGINE=django.contrib.sessions.backends.db
SESSION_COOKIE_SECURE=False
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_AGE=3600

# Autenticação
LOGIN_URL=/login/
LOGOUT_REDIRECT_URL=/login/

```

### Produção (`.env.prod`)

```
# Django
DEBUG=False
DJANGO_ENVIRONMENT=production
SECRET_KEY=K5tRjVxP9qCwZ2gH8sN6mT3dF7aK1pW4eX7yV9uL6kG3jB2tR8qE5zA1rC

# Base URL
BASE_URL= [URL]
API_BASE_URL= [URL] : [Porta]

# Base de Dados PostgreSQL (Produção)
DB_NAME= [Name]
DB_USER= [User]
DB_PASSWORD= [Password]
DB_HOST= [Host]
DB_PORT= [Port]

```

## Docker

### Desenvolvimento Local

```bash
# Construir e executar (usando .env.local)
docker-compose -f docker-compose-local.yml up --build

# Executar migrações
docker-compose exec web-aitigos-django python manage.py migrate --settings=config.settings_local_django

# Criar super utilizador
docker-compose exec web-aitigos-django python manage.py createsuperuser --settings=config.settings_local_django

# Ver logs
docker-compose logs -f web-aitigos-django

```

### Serviços Incluídos

O projeto Docker inclui:

- **Django App**: Servidor principal (porta 5005)
- **Redis**: Cache e sessões (porta 6379)
- **PostgreSQL**: Base de dados (configuração externa)

---

**Desenvolvido com ❤️ pela equipa ednu.ai**
