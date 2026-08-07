import time
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

def trigger_spiders():
    """Triggers both Scrapy spider commands in the terminal."""
    print(f"\n==========================================")
    print(f"⏰ [SCHEDULER] Starting automated run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==========================================")
    
    spiders = ["priceoye_smartphones", "daraz_smartphones"]
    
    for spider in spiders:
        try:
            print(f"🕷️ [SCHEDULER] Triggering spider: {spider}")
            # Executes the scrapy crawl command as a subprocess
            result = subprocess.run(
                ["scrapy", "crawl", spider],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ [SCHEDULER] Crawl completed successfully for {spider}.")
            # print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"❌ [SCHEDULER] Crawl failed for {spider} with error:\n{e.stderr}")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    
    # Schedule the spider to run every 12 hours
    scheduler.add_job(trigger_spiders, 'interval', hours=12)
    
    # Run once immediately on startup
    trigger_spiders()
    
    scheduler.start()
    print("🚀 Vextro 12-Hour Crawler Scheduler running. Press Ctrl+C to exit.")

    # Keep the main process alive
    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("🛑 Scheduler stopped gracefully.")