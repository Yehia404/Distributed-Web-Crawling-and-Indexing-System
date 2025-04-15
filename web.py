#!/usr/bin/env python3
import threading
import time
import subprocess
from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from master_node import MasterNode
from indexer_node import IndexerNode
import logging




app = Flask("web crawler")

command = [
    "celery", "-A", "tasks","worker","-l","info"
]
master = MasterNode()


def master_loop():
    while True:
        master.distribute_tasks()
        master.monitor_workers()
        master.monitor_finished_tasks()
        time.sleep(1) # Poll every second

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
        # (Optional:) You can store/use depth and domain information in the MasterNode.
        master.add_seed_urls(url_list)
        master.set_crawl_options(depth,domains)
        # Redirect back to home page (or to a "status" page) once seed URLs are submitted.
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
    master.update_workers_from_redis()
    progress = {
        'active crawlers': list(master.active_crawlers),
        'active indexers': list(master.active_indexers),
        'urls in queue': list(master.url_queue),
        'urls crawled': list(master.crawled_urls)
    }
    return jsonify(progress)

if __name__ == '__main__':
    # Start the background thread for the master loop (so tasks are distributed and monitored)
    t = threading.Thread(target=master_loop, daemon=True)
    t.start()
    
    # Run the Flask app on port 5000. Adjust host or debug mode as needed.
    app.run(host="0.0.0.0", port=5000, debug=True)
