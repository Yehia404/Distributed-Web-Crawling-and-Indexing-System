#!/usr/bin/env python3
import os, logging, requests
from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from master_node import MasterNode
from indexer_node import IndexerNode
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask("web crawler")
MASTER_URL = os.getenv("MASTER_URL", "http://master:6000")


def render_page(title: str, body_html: str, **ctx):
    """
    Return a full HTML page wrapped in Bootstrap 5.
    Usage: return render_page('My Title', '<h1>Hello</h1>', foo=bar)
    """
    page = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{{{{ title }}}}</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body   {{ padding-top: 4.5rem; }}
        footer {{ margin-top: 4rem; font-size: .9rem; color: #777; }}
      </style>
    </head>
    <body>
      <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
        <div class="container-fluid">
          <a class="navbar-brand fw-bold" href="/">Web Crawler</a>
          <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navBar">
            <span class="navbar-toggler-icon"></span>
          </button>
          <div id="navBar" class="collapse navbar-collapse">
            <ul class="navbar-nav ms-auto">
              <li class="nav-item"><a class="nav-link" href="/crawl">Crawl</a></li>
              <li class="nav-item"><a class="nav-link" href="/search">Search</a></li>
              <li class="nav-item"><a class="nav-link" href="/monitor">Monitor</a></li>
            </ul>
          </div>
        </div>
      </nav>

      <main class="container">
        {body_html}
      </main>

      <footer class="text-center">
        <hr>
        <p>&copy; {{{{ year }}}} Distributed Crawler – Built with Flask &amp; Bootstrap 5</p>
      </footer>

      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    ctx.setdefault("year", datetime.utcnow().year)
    return render_template_string(page, title=title, **ctx)



@app.route("/")
def home():
    body = """
      <div class="row text-center">
        <div class="col-md-4 mb-4">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <h5 class="card-title">Start a Crawl</h5>
              <p class="card-text">Seed new URLs and let worker nodes explore the web.</p>
              <a href="/crawl" class="btn btn-primary">Crawl</a>
            </div>
          </div>
        </div>
        <div class="col-md-4 mb-4">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <h5 class="card-title">Search the Index</h5>
              <p class="card-text">Query pages the cluster has already discovered.</p>
              <a href="/search" class="btn btn-success">Search</a>
            </div>
          </div>
        </div>
        <div class="col-md-4 mb-4">
          <div class="card shadow-sm h-100">
            <div class="card-body">
              <h5 class="card-title">Monitor Progress</h5>
              <p class="card-text">Inspect live statistics from the master node.</p>
              <a href="/monitor" class="btn btn-secondary">Monitor</a>
            </div>
          </div>
        </div>
      </div>
    """
    return render_page("Dashboard", body)


@app.route("/crawl", methods=["GET", "POST"])
def crawl():
    if request.method == "POST":
        urls = request.form.get("urls", "")
        depth = int(request.form.get("depth", "1"))
        domains = request.form.get("domains", "")
        url_list = [u.strip() for u in urls.split(",") if u.strip()]
        try:
            resp = requests.post(
                f"{MASTER_URL}/seed",
                json={"urls": url_list, "depth": depth, "domains": domains},
                timeout=5,
            )
            resp.raise_for_status()
            logger.info("Sent %s URLs to master (%s)", len(url_list), resp.status_code)
        except Exception as exc:
            logger.error("Error contacting master: %s", exc)
        return redirect(url_for("home"))

    form_html = """
      <div class="row justify-content-center">
        <div class="col-md-8">
          <div class="card shadow-sm">
            <div class="card-header bg-primary text-white">Start a Crawl</div>
            <div class="card-body">
              <form method="post">
                <div class="mb-3">
                  <label class="form-label">URLs (comma-separated)</label>
                  <input type="text" name="urls" class="form-control" placeholder="https://example.com, https://outlier.org">
                </div>
                <div class="mb-3">
                  <label class="form-label">Crawl Depth</label>
                  <input type="number" name="depth" class="form-control" value="1" min="1" max="10">
                </div>
                <div class="mb-3">
                  <label class="form-label">Restrict to Domains (optional)</label>
                  <input type="text" name="domains" class="form-control" placeholder="example.com, outlier.org">
                </div>
                <button type="submit" class="btn btn-primary w-100">Launch Crawl</button>
              </form>
            </div>
          </div>
        </div>
      </div>
    """
    return render_page("Start a Crawl", form_html)


@app.route("/search", methods=["GET", "POST"])
def search():
    indexer = IndexerNode()
    results, query = [], ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        results = indexer.search(query)

    search_html = """
      <div class="row justify-content-center">
        <div class="col-md-8">
          <div class="card shadow-sm">
            <div class="card-header bg-success text-white">Search the Index</div>
            <div class="card-body">
              <form method="post" class="d-flex mb-3">
                <input type="text" name="query" class="form-control me-2" placeholder="keyword or phrase"
                       value="{{query}}">
                <button class="btn btn-success" type="submit">Search</button>
              </form>

              {% if results %}
                <h5 class="mb-3">Results ({{results|length}}):</h5>
                <table class="table table-striped table-hover">
                  <thead><tr><th>#</th><th>URL</th></tr></thead>
                  <tbody>
                    {% for url in results %}
                      <tr><td>{{loop.index}}</td><td><a href="{{url}}" target="_blank">{{url}}</a></td></tr>
                    {% endfor %}
                  </tbody>
                </table>
              {% elif query %}
                <div class="alert alert-warning">No results for “{{query}}”.</div>
              {% endif %}
            </div>
          </div>
        </div>
      </div>
    """
    return render_page("Search", search_html, results=results, query=query)


@app.route("/monitor")
def monitor():
    try:
        data = requests.get(f"{MASTER_URL}/state", timeout=5).json()
        active_crawlers = data.get("active_crawlers", [])
        active_indexers = data.get("active_indexers", [])
        urls_in_queue   = data.get("urls_in_queue",   [])
        urls_crawled    = data.get("urls_crawled",    [])
    except Exception as exc:
        # Show a friendly error message if the master is unreachable
        error_html = f"""
          <div class="alert alert-danger" role="alert">
            Could not contact master node: {exc}
          </div>
        """
        return render_page("Monitor", error_html)


    monitor_html = """
      <h2 class="mb-4">Cluster Status</h2>

      <div class="row text-center mb-4">
        <div class="col-md-3 mb-3">
          <div class="card shadow-sm border-success h-100">
            <div class="card-body">
              <h6 class="card-subtitle text-muted">Active Crawlers</h6>
              <h2 class="display-6 text-success">{{ ac|length }}</h2>
            </div>
          </div>
        </div>
        <div class="col-md-3 mb-3">
          <div class="card shadow-sm border-info h-100">
            <div class="card-body">
              <h6 class="card-subtitle text-muted">Active Indexers</h6>
              <h2 class="display-6 text-info">{{ ai|length }}</h2>
            </div>
          </div>
        </div>
        <div class="col-md-3 mb-3">
          <div class="card shadow-sm border-warning h-100">
            <div class="card-body">
              <h6 class="card-subtitle text-muted">URLs in Queue</h6>
              <h2 class="display-6 text-warning">{{ q|length }}</h2>
            </div>
          </div>
        </div>
        <div class="col-md-3 mb-3">
          <div class="card shadow-sm border-secondary h-100">
            <div class="card-body">
              <h6 class="card-subtitle text-muted">URLs Crawled</h6>
              <h2 class="display-6 text-secondary">{{ c|length }}</h2>
            </div>
          </div>
        </div>
      </div>

      <!-- Detailed lists ------------------------------------------------- -->
      <div class="row">
        <div class="col-md-6">
          <h4 class="mb-3">Queue (next&nbsp;20)</h4>
          {% if q %}
            <ul class="list-group small">
              {% for url in q[:20] %}
                <li class="list-group-item text-truncate" title="{{url}}">{{ url }}</li>
              {% endfor %}
            </ul>
          {% else %}
            <p class="text-muted">Queue is empty.</p>
          {% endif %}
        </div>

        <div class="col-md-6">
          <h4 class="mb-3">Recently Crawled (last&nbsp;20)</h4>
          {% if c %}
            <ul class="list-group small">
              {% for url in c[-20:] %}
                <li class="list-group-item text-truncate" title="{{url}}">{{ url }}</li>
              {% endfor %}
            </ul>
          {% else %}
            <p class="text-muted">No pages crawled yet.</p>
          {% endif %}
        </div>
      </div>
    """
    return render_page(
        "Monitor",
        monitor_html,
        ac=active_crawlers,
        ai=active_indexers,
        q=urls_in_queue,
        c=urls_crawled,
    )



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)