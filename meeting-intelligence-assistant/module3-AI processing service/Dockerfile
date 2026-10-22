FROM python:3.13-slim

WORKDIR /app

# Install Python dependencies first so Docker can cache this layer
# whenever only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code.
COPY app ./app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]