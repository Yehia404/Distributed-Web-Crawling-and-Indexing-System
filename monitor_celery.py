# monitor_celery.py
import time, csv, datetime as dt
from celery import Celery
from config import Config

app = Celery('crawler' ,broker=Config.REDIS_URL)     # same broker your workers use
state = app.events.State()
app.control.enable_events()               # ② ensure events are flowing

def main(run_name):
    with open(f"{run_name}.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["ts", "crawl_done", "index_done"])

        start      = time.time()
        crawl_done = 0
        index_done = 0

        def on_event(event):
            nonlocal crawl_done, index_done, start      # ① include start
            state.event(event)

            if event["type"] == "task-succeeded":
                if event["name"] == "crawl_page":
                    crawl_done += 1
                elif event["name"] == "index_content":
                    index_done += 1

            # dump once per 60-second window
            if time.time() - start >= 60:
                wr.writerow([dt.datetime.utcnow().isoformat(),
                             crawl_done, index_done])
                f.flush()
                crawl_done = index_done = 0
                start = time.time()                     # ← reset window

        with app.connection() as conn:
            recv = app.events.Receiver(conn, handlers={"*": on_event})
            recv.capture(limit=None, timeout=None, wakeup=True)


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "test")