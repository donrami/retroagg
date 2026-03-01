"""
Background Scheduler - Periodic RSS feed fetching
"""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services import fetch_and_store_all


logger = logging.getLogger("app.scheduler")


class FetchScheduler:
    """Scheduler for periodic RSS fetching with proper resource management"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self._fetch_lock = asyncio.Lock()
        self.logger = logging.getLogger("app.scheduler")
        self._last_fetch_time = None
        self._fetch_count = 0
    
    async def fetch_job(self):
        """Job to fetch all RSS feeds with concurrency control"""
        # Prevent overlapping fetches
        if self._fetch_lock.locked():
            self.logger.warning("Previous fetch still in progress, skipping this run")
            return
        
        now = datetime.utcnow()
        
        # DIAGNOSTIC: Log fetch timing
        if self._last_fetch_time:
            time_since_last = (now - self._last_fetch_time).total_seconds() / 60
            self.logger.info(f"[DIAGNOSTIC] Time since last fetch: {time_since_last:.1f} minutes (interval: {settings.FETCH_INTERVAL_MINUTES} min)")
        else:
            self.logger.info(f"[DIAGNOSTIC] First fetch - interval set to: {settings.FETCH_INTERVAL_MINUTES} minutes")
        
        async with self._fetch_lock:
            self.logger.info("Scheduled RSS fetch triggered.")
            try:
                count = await fetch_and_store_all()
                self._last_fetch_time = datetime.utcnow()
                self._fetch_count += 1
                self.logger.info("Scheduled fetch complete. New articles: %d (total fetches: %d)", count, self._fetch_count)
                return count
            except Exception as e:
                self.logger.exception("Scheduled fetch error: %s", str(e))
                return 0
    
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            return
        
        # DIAGNOSTIC: Log the fetch interval being used
        logger.warning(f"[DIAGNOSTIC] Starting scheduler with FETCH_INTERVAL_MINUTES = {settings.FETCH_INTERVAL_MINUTES}")
        
        # Add job to run every FETCH_INTERVAL_MINUTES
        self.scheduler.add_job(
            self.fetch_job,
            trigger=IntervalTrigger(minutes=settings.FETCH_INTERVAL_MINUTES),
            id='rss_fetch',
            name='RSS Feed Fetcher',
            replace_existing=True,
            misfire_grace_time=300,  # 5 minutes grace period for missed jobs
        )
        
        self.scheduler.start()
        self.is_running = True
        self.logger.info("Scheduler started. Fetching every %d minutes.", settings.FETCH_INTERVAL_MINUTES)
    
    def stop(self):
        """Stop the scheduler with proper shutdown"""
        if self.is_running:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            self.logger.info("Scheduler stopped.")
    
    async def run_once(self):
        """Run fetch once immediately - bypasses lock for manual refresh.
        
        Manual refresh should always work even if a scheduled fetch is running.
        """
        self.logger.info("Manual refresh triggered - bypassing lock")
        
        # Directly call the fetch logic without the lock
        # This allows manual refresh to work even during scheduled fetch
        try:
            count = await fetch_and_store_all()
            self._last_fetch_time = datetime.utcnow()
            self._fetch_count += 1
            self.logger.info("Manual refresh complete. New articles: %d", count)
            return count
        except Exception as e:
            self.logger.exception("Manual refresh error: %s", str(e))
            return 0


# Global scheduler instance
scheduler = FetchScheduler()


def start_scheduler():
    """Convenience function to start the scheduler"""
    scheduler.start()


def stop_scheduler():
    """Convenience function to stop the scheduler"""
    scheduler.stop()


async def manual_fetch():
    """Convenience function for manual fetch"""
    return await scheduler.run_once()
