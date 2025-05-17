# Distributed-Web-Crawling-and-Indexing-System

## Introduction

This project is a **proof-of-concept distributed web-crawler** that:

- Accepts seed URLs from a web UI or REST call  
- Crawls pages in parallel (respecting `robots.txt`)  
- Stores HTML + extracted text in **S3**  
- Tokenizes the text and indexes it into **Amazon OpenSearch**  
- Allows near-real-time search of indexed pages  

It is built entirely with **open-source Python components** and **AWS managed services**, and can run either:

- On a single laptop, or  
- Fully distributed on AWS (managed stores)

---

## Architecture Overview

### Core Services

- **Flask UI** (port `5000`) – Thin Bootstrap interface  
- **Master API** (port `6000`) – Task scheduler & cluster monitor  
- **Celery workers** – Two queues:
  - `crawler`: downloads pages  
  - `indexer`: builds search index  
- **Redis (ElastiCache)** – Heartbeats, pending/finished sets  
- **Amazon SQS** – Durable task queues (`crawler`, `indexer`)  
- **Amazon S3** – Object store for HTML and text files  
- **Amazon OpenSearch** – Search index (web-crawl index)  

---

## Terminology

- **Seed URL** – First URL(s) you provide  
- **Depth** – "Number of clicks" from the seed  
- **Worker** – A Celery process running inside a Docker container  
- **Heartbeat** – Periodic Redis ZSET update (`active_crawlers`, `active_indexers`)  
- **Task ID** – Celery task UUID  

---

## Web Interface

### Home (`/`)

- Displays three cards: **Crawl**, **Search**, and **Monitor**

---

### Crawl (`/crawl`)

- **URLs**: Comma-separated list of HTTP/S URLs  
- **Depth**: Integer between 1–10  
- **Restrict domains** *(optional)*: e.g., `wikipedia.org`, `bbc.com`  
- Press **Launch Crawl**. The form `POST`s to the master  

---

### Search (`/search`)

- Plain keyword box  
- Results show a clickable list of matched URLs  

---

### Monitor (`/monitor`)

- Real-time counts:
  - Active crawlers  
  - Active indexers  
  - Queue length  
  - Crawled URLs  
- Two scrolling lists:
  - Next 20 queued  
  - Last 20 crawled  

---

## Master API

### General Info

- **Base URL**: `http://<MASTER_HOST>:6000`  
- All requests and successful responses are **UTF-8 JSON**, except `/health` (plain text)  
- Default request header: `Content-Type: application/json`  
- **No authentication** – should be deployed inside private VPC or isolated cluster  

---

### `POST /seed` – Submit Seed URLs

**Purpose**: Queue one or more start URLs and (optionally) set crawl limits.

#### Request JSON Fields

```json
{
  "urls":   ["https://example.com", "https://example.org"],
  "depth":  2,
  "domains": "example.com,example.org"
}
```

- `urls` *(array, required)* – Absolute `http(s)` URLs to crawl  
- `depth` *(integer, optional, default 1)* – Maximum link depth to follow  
- `domains` *(string, optional, default empty)* – Comma-separated allow-list  

#### Successful Response

```json
HTTP/1.1 202 Accepted
{
  "queued": 2
}
```

- `queued` is the number of URLs accepted (duplicates/disallowed are ignored)

#### Error Responses

- `HTTP 400` – Malformed JSON or missing `urls`  
- `HTTP 500` – Unexpected server-side error (check master logs)  

---

### `GET /state` – Retrieve Live Cluster Status

**Purpose**: Return current operational state (via Redis + master's in-memory frontier)

#### Example Response

```json
HTTP/1.1 200 OK
{
  "active_crawlers": ["crawler_bf23c", "crawler_a921d"],
  "active_indexers": ["indexer_0f18e"],
  "urls_in_queue":   ["https://example.com/alpha", "https://example.org/beta"],
  "urls_crawled":    ["https://example.com", "https://example.org"]
}
```

#### Field Explanations

- `active_crawlers`: Task IDs of crawlers with recent heartbeats  
- `active_indexers`: Same, but for indexers  
- `urls_in_queue`: URLs waiting for assignment  
- `urls_crawled`: URLs already dispatched  

#### Status Codes

- `HTTP 200` on success  
- `HTTP 500` if Redis or other critical service fails  

---

### `GET /health` – Liveness Probe

**Purpose**: Allow orchestrators or load balancers to check service availability

#### Request

```http
GET /health
```

#### Successful Response

```http
HTTP/1.1 200 OK
Content-Type: text/plain
```

---

## Example `cURL` Commands

### Seed a Crawl

```bash
curl -X POST http://master:6000/seed      -H "Content-Type: application/json"      -d '{"urls":["https://example.com"],"depth":2,"domains":""}'
```

---

### Poll Cluster State

```bash
curl http://master:6000/state
```

---

### Health Check

```bash
curl -f http://master:6000/health
```