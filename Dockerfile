# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем только нужные файлы и папки
COPY static/ ./static/
COPY templates/ ./templates/
COPY modules/ ./modules/
COPY app.py .

# Устанавливаем права на выполнение (если нужно)
RUN chmod +x /app/modules/botTelegram.py

# Указываем, что приложение слушает 5000 порт (для Flask)
#EXPOSE 5000
