FROM python:3.11-slim

WORKDIR /app

# Copiar apenas o requirements.txt primeiro (para fazer cache)
COPY backend/requirements.txt .

# Instalar as dependências (isto só corre quando fizermos "build")
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código do backend
COPY backend/ /app/

# Comando para iniciar a aplicação
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]