FROM python:3.14.5-slim

# Force stdin/stdout to be completely unbuffered (critical for real-time streaming LLM logs)
ENV PYTHONUNBUFFERED=1

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies if needed later (e.g., curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
