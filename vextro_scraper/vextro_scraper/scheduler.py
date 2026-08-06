import time
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

def trigger_priceoye_spider():
    """Triggers the Scrapy spider command in the terminal."""
    print(f"\n==========================================")
    print(f"⏰ [SCHEDULER] Starting automated run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==========================================")
    
    try:
        # Executes the scrapy crawl command as a subprocess
        result = subprocess.run(
            ["scrapy", "crawl", "priceoye_smartphones"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ [SCHEDULER] Crawl completed successfully.")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ [SCHEDULER] Crawl failed with error:\n{e.stderr}")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    
    # Schedule the spider to run every 12 hours
    scheduler.add_job(trigger_priceoye_spider, 'interval', hours=12)
    
    # Run once immediately on startup
    trigger_priceoye_spider()
    
    scheduler.start()
    print("🚀 Vextro 12-Hour Crawler Scheduler running. Press Ctrl+C to exit.")

    # Keep the main process alive
    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("🛑 Scheduler stopped gracefully.")