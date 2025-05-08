

import os
import logging
import threading
import time
from flask import Flask, request, jsonify
from master_node import MasterNode            

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("master-service")


master = MasterNode()


app = Flask("master-service")

@app.route("/seed", methods=["POST"])
def seed():
    """
    Body:
      {
        "urls":    ["https://…", "https://…"],
        "depth":    1,
        "domains":  ""
      }
    """
    data = request.get_json(force=True, silent=False)
    urls    = data.get("urls", [])
    depth   = int(data.get("depth", 1))
    domains = data.get("domains", "")
    master.add_seed_urls(urls)
    master.set_crawl_options(depth, domains)
    return jsonify({"queued": len(urls)}), 202

@app.route("/state")
def state():
    """Return the same JSON you previously showed on /monitor."""
    return jsonify({
        "active_crawlers":  list(master.active_crawlers),
        "active_indexers":  list(master.active_indexers),
        "urls_in_queue":    list(master.url_queue),
        "urls_crawled":     list(master.crawled_urls),
    })

@app.route("/health")
def health():
    """Simple liveness probe for ALB / Kubernetes, etc."""
    return "OK", 200

def _loop():
    """
    Runs forever in a daemon thread:
      • distribute tasks from url_queue to Celery (SQS)
      • monitor worker heart-beats
      • process finished crawl results
    """
    while True:
        try:
            master.distribute_tasks()
            master.monitor_workers()
            master.monitor_finished_tasks()
        except Exception:
            log.exception("Error in master loop")
        time.sleep(1)


if __name__ == "__main__":
    threading.Thread(target=_loop, daemon=True).start()

    host = os.getenv("HOST", "0.0.0.0")
    log.info("Master service listening on %s:6000", host)
    app.run(host=host, port=6000, debug=False, use_reloader=False)