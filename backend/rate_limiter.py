import time
import threading
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status
import os

class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter with tiered limits by IP."""

    def __init__(self):
        self.lock = threading.Lock()
        # Storage: { tier: { ip: [timestamp1, timestamp2, ...] } }
        self.requests: Dict[str, Dict[str, List[float]]] = {}
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes

        # Tier limits from environment or defaults (requests, window_seconds)
        self.limits = {
            "auth": (int(os.getenv("RATE_LIMIT_AUTH_RPM", "10")), 60),
            "admin": (int(os.getenv("RATE_LIMIT_ADMIN_RPM", "30")), 60),
            "general": (int(os.getenv("RATE_LIMIT_API_RPM", "120")), 60),
        }

    def _get_client_ip(self, request: Request) -> str:
        # Check standard reverse proxy headers safely
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP in list is original client IP
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _cleanup_old_entries(self, now: float):
        """Purge records older than the longest window to prevent memory leaks."""
        if now - self.last_cleanup < self.cleanup_interval:
            return
        self.last_cleanup = now
        for tier in list(self.requests.keys()):
            _, window = self.limits.get(tier, (120, 60))
            cutoff = now - window
            for ip in list(self.requests[tier].keys()):
                valid = [ts for ts in self.requests[tier][ip] if ts > cutoff]
                if valid:
                    self.requests[tier][ip] = valid
                else:
                    del self.requests[tier][ip]

    def check_rate_limit(self, request: Request, tier: str = "general") -> Tuple[int, int, int]:
        """Check if request is within limits.
        Returns: (limit, remaining, retry_after)
        Raises HTTPException(429) if exceeded.
        """
        now = time.time()
        client_ip = self._get_client_ip(request)
        max_requests, window_seconds = self.limits.get(tier, self.limits["general"])

        with self.lock:
            self._cleanup_old_entries(now)
            if tier not in self.requests:
                self.requests[tier] = {}
            if client_ip not in self.requests[tier]:
                self.requests[tier][client_ip] = []

            # Filter timestamps in current window
            cutoff = now - window_seconds
            timestamps = [ts for ts in self.requests[tier][client_ip] if ts > cutoff]
            self.requests[tier][client_ip] = timestamps

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(earliest + window_seconds)),
                    },
                )

            # Record this request
            timestamps.append(now)
            remaining = max_requests - len(timestamps)
            return max_requests, remaining, 0

# Global limiter instance
rate_limiter = SlidingWindowRateLimiter()
