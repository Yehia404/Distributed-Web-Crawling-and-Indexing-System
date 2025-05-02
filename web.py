#!/usr/bin/env python3
import threading
import time
import requests
from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from master_node import MasterNode
from indexer_node import IndexerNode
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


app = Flask("web crawler")
MASTER_URL = os.getenv("MASTER_URL", "http://master:6000")

@app.route('/')
def home():
    home_html = """
    <html>
      <head>
        <title>Distributed Web Crawler</title>
      </head>
      <body>
        <h1>Distributed Web Crawler</h1>
        <ul>
          <li><a href="/crawl">Start a Crawl</a></li>
          <li><a href="/search">Search the Index</a></li>
          <li><a href="/monitor">Monitor Progress</a></li>
        </ul>
      </body>
    </html>
    """
    return render_template_string(home_html)


@app.route('/crawl',methods=["GET","POST"])
def crawl():
    if request.method == "POST":
        # Retrieve comma-separated URLs, crawl depth, and allowed domains from the form.
        urls = request.form.get("urls", "")
        depth = int(request.form.get("depth", "1"))
        domains = request.form.get("domains", "")
        # For simplicity, we only use the URLs for now
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        try:
            resp = requests.post(
                f"{MASTER_URL}/seed",
                json={"urls": url_list, "depth": depth, "domains": domains},
                timeout=5
            )
            resp.raise_for_status()
            msg = f"Queued {len(url_list)} URLs"
            logger.info("Sent %s URLs to master (%s)", len(url_list), resp.status_code)
        except Exception as exc:
            msg = f"Error contacting master: {exc}"
            logger.error(msg)
        return redirect(url_for("home"))
    crawl_html= """
    <html>
      <head>
        <title>Start a Web Crawl</title>
      </head>
      <body>
        <h2>Start a Web Crawl</h2>
        <form method="post">
          <label>URLs (comma-separated):</label><br>
          <input type="text" name="urls" size="80"><br><br>
          <label>Crawl Depth (limit how deep to follow links):</label><br>
          <input type="number" name="depth" value="1"><br><br>
          <label>Limit to Domains (optional, comma-separated):</label><br>
          <input type="text" name="domains" size="50"><br><br>
          <input type="submit" value="Start Crawl">
        </form>
      </body>
    </html>
    """
    return render_template_string(crawl_html)

# Search page: query the index
@app.route('/search', methods=["GET", "POST"])
def search():
    indexer = IndexerNode()
    results = []
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "")
        results = indexer.search(query)
    search_html = """
    <html>
      <head>
        <title>Search the Index</title>
      </head>
      <body>
        <h2>Search the Index</h2>
        <form method="post">
          <label>Search Keywords:</label><br>
          <input type="text" name="query" size="50" value="{{query}}"><br><br>
          <input type="submit" value="Search">
        </form>
        <h3>Results:</h3>
        {% if results %}
          <ul>
          {% for url in results %}
            <li>{{url}}</li>
          {% endfor %}
          </ul>
        {% else %}
          <p>No results</p>
        {% endif %}
      </body>
    </html>
    """
    return render_template_string(search_html, results=results, query=query)

# Monitor page: show current status from the MasterNode
@app.route('/monitor')
def monitor():
    data = requests.get(f"{MASTER_URL}/state").json()
    return jsonify(data)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
