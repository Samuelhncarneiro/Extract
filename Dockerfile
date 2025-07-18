# Base da imagem
FROM python:3.12-slim

# Variáveis de ambiente para o Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instala dependências do sistema e ferramentas necessárias
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    gnupg \
    nodejs \
    npm && \
    apt-get clean

# Instala Yarn globalmente
RUN npm install -g yarn

# Define diretório base da aplicação
WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto
COPY . .

# Compila assets front-end com Yarn
WORKDIR /app/src
RUN yarn && yarn build

# Volta para o root do projeto Django e coleta staticfiles
WORKDIR /app
RUN python manage.py collectstatic --noinput

# Comando para iniciar o servidor Gunicorn
CMD ["gunicorn", "--config", "gunicorn-cfg.py", "config.wsgi"]
