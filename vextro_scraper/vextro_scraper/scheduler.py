import subprocess
import sys
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler


SCRAPER_PROJECT_ROOT = Path(__file__).resolve().parents[1]

def trigger_spiders():
    """Triggers both Scrapy spider commands in the terminal."""
    print("\n==========================================", flush=True)
    print(
        "[SCHEDULER] Starting automated run at: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        flush=True,
    )
    print("==========================================", flush=True)
    
    spiders = ["priceoye_smartphones", "daraz_smartphones"]
    
    for spider in spiders:
        try:
            print(f"[SCHEDULER] Triggering spider: {spider}", flush=True)
            # Executes the scrapy crawl command as a subprocess
            result = subprocess.run(
                [sys.executable, "-m", "scrapy", "crawl", spider],
                cwd=SCRAPER_PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True
            )
            print(
                f"[SCHEDULER] Crawl completed successfully for {spider}.",
                flush=True,
            )
            # print(result.stdout)
        except (subprocess.CalledProcessError, OSError) as e:
            error_output = getattr(e, "stderr", None) or str(e)
            print(
                f"[SCHEDULER] Crawl failed for {spider} "
                f"with error:\n{error_output}",
                flush=True,
            )

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    
    # Schedule the spider to run every 12 hours
    scheduler.add_job(
        trigger_spiders,
        'interval',
        hours=12,
        id='vextro-marketplace-refresh',
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        next_run_time=datetime.now(),
    )

    print(
        "VEXTRO crawler scheduler is running now and every 12 hours.",
        flush=True,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped gracefully.", flush=True)
