
# A simple HTTPS server with an endpoint on which
# callers can inject O2DPG_workflow_runner stat json metrics.
# The service is supposed to run as aggregator of these individual metrics
# and to provide high-quality merged statistics on resource estimates. These
# estimates can then be used to improve the scheduling of o2dpg_workflow_runner workflows.

from fastapi import FastAPI
from pydantic import BaseModel
from asyncio import Queue, create_task
import asyncio, json, time
import aiofiles
from fastapi import Request

import sys, os

# add the parent directory of the current file to sys.path to find the o2dpg_sim_metric
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from o2dpg_sim_metrics import merge_stats_into

app = FastAPI()
queue = Queue()
agg = {}          # {(metric_name): {"sum": 0.0, "count": 0}}
flush_interval = 5  # seconds
outfile = "metrics.json"

# Global state
agg_by_tag = {}  # { production_tag: cached_result }


@app.post("/metric")
async def receive_metric(request : Request):
    # just enqueue, return quickly
    payload = await request.json()
    await queue.put(payload)
    return {"status": "ok"}

def init_cache():
    """
    Initializes the cache of results from files
    """
    pass

def flush_to_disc(tag):
    """
    flushes result for tag to disc
    """
    metrics = agg_by_tag.get(tag, {})
    filename = f"aggr_metrics_tag_{tag}.json"
    with open(filename, 'w') as f:
        json.dump(metrics, f)

async def worker():
    """
    Function performing the metrics aggregation
    """
    while True:
        payload = await queue.get()

        # Extract production-tag from metadata
        meta = payload.get("meta-data", {})
        tag = meta.get("production-tag", "default")

        print (f"Worker is treating payload for tag {tag}")

        current = agg_by_tag.get(tag, {})                                  # fetch existing aggregate
        updated = merge_stats_into([payload, current], None, meta)         # merge new payload with cached
        agg_by_tag[tag] = updated                                          # store back in cache

        flush_to_disc(tag)

        queue.task_done()


async def flusher():
    while True:
        await asyncio.sleep(flush_interval)
        snapshot = {
            k: (v["sum"] / v["count"]) if v["count"] else 0
            for k, v in agg.items()
        }
        async with aiofiles.open(outfile, "w") as f:
            await f.write(json.dumps(snapshot, indent=2))
        print(f"Flushed {len(snapshot)} metrics at {time.ctime()}")


@app.on_event("startup")
async def startup():
    # start multiple workers for parallelism
    for _ in range(8):  # one per CPU core
        create_task(worker())
    # create_task(flusher())
