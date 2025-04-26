FROM python:3.10-slim                           
ENV PYTHONUNBUFFERED=1
WORKDIR /app


ENV PYTHONUNBUFFERED=1  

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m nltk.downloader punkt stopwords wordnet  # bundle NLTK :contentReference[oaicite:1]{index=1}

COPY . .
ENV PORT=8080
CMD ["gunicorn","--bind","0.0.0.0:$PORT","web:app"]




