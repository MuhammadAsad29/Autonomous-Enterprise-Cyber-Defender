FROM python:3.10-slim

WORKDIR /app

# Install dependencies (CPU PyTorch + requirements)
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Hugging Face Spaces port
ENV PORT=7860
EXPOSE 7860

# Launch Flask application via Gunicorn on Hugging Face port 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--timeout", "120", "app:app"]
