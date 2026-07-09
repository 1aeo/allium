"""
File: workers.py

API worker functions for fetching data from multiple sources.
Extracted from the original monolithic Relays class for multi-API support.
"""

import base64
import errno
import json
import logging
import os
import random
import time
import urllib.request
import urllib.error
import socket
import threading
from datetime import datetime, timedelta, timezone
from .error_handlers import handle_file_io_errors, handle_http_errors, handle_json_errors

logger = logging.getLogger(__name__)


# ============================================================================
# TOTAL REQUEST TIMEOUT IMPLEMENTATION
# ============================================================================
# Python's urllib timeout only applies to individual socket operations (connect,
# read chunk), NOT the total request time. If a server sends data slowly (even
# 1 byte every few seconds), it will never timeout because each read succeeds.
#
# This implementation reads data in chunks while tracking total elapsed time,
# ensuring the entire request (including slow data transfer) respects the timeout.
# ============================================================================

class TotalTimeoutError(Exception):
    """Raised when a request exceeds the total allowed timeout."""
    pass


def _fetch_url_with_total_timeout(url: str, timeout: int, headers: dict = None) -> bytes:
    """
    Fetch URL content with a guaranteed total timeout.
    
    Unlike urllib's timeout parameter (which only applies to individual socket
    operations), this function enforces a true total timeout for the entire
    request, including connection, waiting for headers, and all data transfer.
    
    Implementation:
    - Uses socket timeout equal to total timeout for initial connection
    - Reads response in chunks while tracking total elapsed time
    - Aborts immediately when total timeout is exceeded
    
    Note: The socket timeout on urlopen() applies to waiting for response headers,
    so setting it to the total timeout ensures the connection phase respects the limit.
    
    Args:
        url: URL to fetch
        timeout: Maximum total time in seconds for the entire request
        headers: Optional dict of HTTP headers to include
        
    Returns:
        bytes: Response content
        
    Raises:
        TotalTimeoutError: If the request exceeds the total timeout
        urllib.error.URLError: On network errors (not timeout)
        urllib.error.HTTPError: On HTTP errors (4xx, 5xx)
    """
    if headers:
        req = urllib.request.Request(url, headers=headers)
    else:
        req = urllib.request.Request(url)
    
    start_time = time.time()
    
    # Phase 1: Open connection with socket timeout equal to total timeout
    # This ensures we don't wait forever for response headers from a hanging server
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except socket.timeout:
        elapsed = time.time() - start_time
        raise TotalTimeoutError(
            f"Connection to {url} timed out waiting for response after {elapsed:.1f}s"
        )
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            elapsed = time.time() - start_time
            raise TotalTimeoutError(
                f"Connection to {url} timed out after {elapsed:.1f}s"
            )
        raise
    
    # Phase 2: Read response in chunks, checking total elapsed time after each chunk
    chunks = []
    chunk_size = 64 * 1024  # 64KB chunks
    
    try:
        while True:
            # Check total elapsed time before reading next chunk
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                response.close()
                raise TotalTimeoutError(
                    f"Request to {url} exceeded total timeout of {timeout}s "
                    f"(elapsed: {elapsed:.1f}s, received: {sum(len(c) for c in chunks)} bytes)"
                )
            
            # Calculate remaining time for this chunk read
            remaining = timeout - elapsed
            
            # Set socket timeout for this read operation
            # Use minimum of remaining time and 5 seconds to check frequently
            read_timeout = min(remaining, 5)
            if hasattr(response, 'fp') and hasattr(response.fp, 'raw'):
                try:
                    response.fp.raw._sock.settimeout(read_timeout)
                except (AttributeError, OSError):
                    pass  # Some response types don't support this
            
            try:
                chunk = response.read(chunk_size)
            except socket.timeout:
                # Individual read timed out - check if total timeout exceeded
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    response.close()
                    raise TotalTimeoutError(
                        f"Request to {url} exceeded total timeout of {timeout}s during read"
                    )
                # Socket timeout but total not exceeded - retry
                continue
            
            if not chunk:
                # End of response
                break
            
            chunks.append(chunk)
        
        return b''.join(chunks)
        
    finally:
        try:
            response.close()
        except Exception:
            pass

# Global constants
ABS_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ABS_PATH), "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

# Ensure directories exist
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Global state lock for thread safety
_state_lock = threading.Lock()

# Worker status tracking
_worker_status = {}

# ============================================================================
# API CACHE CONFIGURATION
# ============================================================================
# These values control the timeout and caching behavior for each API.
# Adjust these values to tune the balance between responsiveness and data freshness.
#
# For each API:
#   - *_CACHE_MAX_AGE_HOURS: Age (in hours) after which cache is considered stale
#   - *_TIMEOUT_FRESH_CACHE: Timeout (in seconds) when cache is fresh (use cache on timeout)
#   - *_TIMEOUT_STALE_CACHE: Timeout (in seconds) when cache is stale or missing
#
# Example adjustments:
#   - For faster responses with older data: increase *_CACHE_MAX_AGE_HOURS
#   - For more patient fetching: increase *_TIMEOUT_STALE_CACHE
#   - For quicker timeouts: decrease *_TIMEOUT_FRESH_CACHE
# ============================================================================

# DETAILS API - Critical for operation, has most relay data
# Details API typically responds quickly but can be slow during high load
DETAILS_CACHE_MAX_AGE_HOURS = 6       # Cache older than this is considered stale
DETAILS_TIMEOUT_FRESH_CACHE = 90      # 90 seconds for fresh cache
DETAILS_TIMEOUT_STALE_CACHE = 300     # 5 minutes for stale/missing cache

# UPTIME API - Often slow, especially around 30 minutes past the hour
# Uptime API often can take up to 10 minutes around 30 minutes past the hour
UPTIME_CACHE_MAX_AGE_HOURS = 12       # Cache older than this is considered stale
UPTIME_TIMEOUT_FRESH_CACHE = 30       # 30 seconds for fresh cache (shorter due to frequent slowness)
UPTIME_TIMEOUT_STALE_CACHE = 1200     # 20 minutes for stale/missing cache

# BANDWIDTH API - Large data, can be slow
BANDWIDTH_CACHE_MAX_AGE_HOURS = 12    # Cache older than this is considered stale
BANDWIDTH_TIMEOUT_FRESH_CACHE = 90    # 90 seconds for fresh cache
BANDWIDTH_TIMEOUT_STALE_CACHE = 600   # 10 minutes for stale/missing cache

# AROI VALIDATION API - External API, may be less reliable
AROI_CACHE_MAX_AGE_HOURS = 1          # Cache older than this is considered stale (1 hour)
AROI_TIMEOUT_FRESH_CACHE = 90         # 90 seconds for fresh cache
AROI_TIMEOUT_STALE_CACHE = 120        # 2 minutes for stale/missing cache

# EXIT DNS HEALTH API - External API for exit relay DNS resolution health
# API updates every 12 hours; cache for 12h matches the update cycle exactly
EXIT_DNS_HEALTH_CACHE_MAX_AGE_HOURS = 12
EXIT_DNS_HEALTH_TIMEOUT_FRESH_CACHE = 90
EXIT_DNS_HEALTH_TIMEOUT_STALE_CACHE = 120

# COLLECTOR CONSENSUS API - Fetches authority votes from CollecTor
COLLECTOR_CACHE_MAX_AGE_HOURS = 1     # Cache older than this is considered stale (1 hour)
COLLECTOR_TIMEOUT_FRESH_CACHE = 90    # 90 seconds when cache is available (fallback on timeout)
COLLECTOR_TIMEOUT_STALE_CACHE = 300   # 5 minutes when no cache exists

# COLLECTOR DESCRIPTORS API - Fetches server descriptors for family-cert analysis
# First run downloads ~30 hourly files (~210MB total), subsequent runs only ~1 new file (~7MB)
DESCRIPTORS_CACHE_MAX_AGE_HOURS = 1   # Cache older than this is considered stale (1 hour)
DESCRIPTORS_TIMEOUT_FRESH_CACHE = 60  # 60 seconds per file when cache available (typically 1 new file)
DESCRIPTORS_TIMEOUT_STALE_CACHE = 300 # 5 minutes when no cache exists (first run: ~18 files)
DESCRIPTORS_SOURCE_FRESH_MAX_HOURS = 2
DESCRIPTORS_SOURCE_DEGRADED_MAX_HOURS = 5
DESCRIPTORS_SOURCE_CRITICAL_MAX_HOURS = 12
DESCRIPTORS_DOWNGRADE_CONFIRM_RUNS = 2
DESCRIPTORS_DOWNGRADE_MIN_PUBLISHED_DELTA_HOURS = 20
# ============================================================================


# ============================================================================
# API CONFIGURATION DATACLASS
# ============================================================================
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable

@dataclass
class APIConfig:
    """Configuration for an API worker with cache, timeout, and retry settings."""
    api_name: str                    # Internal name for caching (e.g., 'onionoo_details')
    display_name: str                # Human-readable name for logging
    cache_max_age_hours: float       # Hours after which cache is considered stale
    timeout_fresh_cache: int         # Timeout (seconds) when cache is fresh
    timeout_stale_cache: int         # Timeout (seconds) when cache is stale/missing
    use_conditional_requests: bool = True   # Whether to use If-Modified-Since header
    custom_headers: Optional[Dict[str, str]] = None  # Additional request headers
    count_field: str = 'relays'      # Field name to count items in response
    # Retry settings
    retry_count: int = 3             # Max retries on transient failures (0 = no retry)
    retry_delay_base: float = 1.0    # Base delay in seconds for exponential backoff
    retry_on_fresh_cache: bool = False  # If True, retry even when fresh cache exists


# Pre-configured API settings
DETAILS_CONFIG = APIConfig(
    api_name='onionoo_details',
    display_name='onionoo details',
    cache_max_age_hours=DETAILS_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=DETAILS_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=DETAILS_TIMEOUT_STALE_CACHE,
    retry_count=3,               # Critical API: retry up to 3 times
    retry_delay_base=2.0,        # 2s → 4s → 8s backoff
)

UPTIME_CONFIG = APIConfig(
    api_name='onionoo_uptime',
    display_name='onionoo uptime',
    cache_max_age_hours=UPTIME_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=UPTIME_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=UPTIME_TIMEOUT_STALE_CACHE,
    retry_count=2,               # Non-critical: retry up to 2 times
    retry_delay_base=2.0,
)

BANDWIDTH_CONFIG = APIConfig(
    api_name='onionoo_bandwidth',
    display_name='onionoo historical bandwidth',
    cache_max_age_hours=BANDWIDTH_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=BANDWIDTH_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=BANDWIDTH_TIMEOUT_STALE_CACHE,
    retry_count=2,               # Non-critical: retry up to 2 times
    retry_delay_base=2.0,
)

AROI_CONFIG = APIConfig(
    api_name='aroi_validation',
    display_name='AROI validation',
    cache_max_age_hours=AROI_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=AROI_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=AROI_TIMEOUT_STALE_CACHE,
    use_conditional_requests=False,
    custom_headers={'User-Agent': 'Allium/1.0'},
    count_field='results',
    retry_count=2,               # External API: retry up to 2 times
    retry_delay_base=1.0,
)

EXIT_DNS_HEALTH_CONFIG = APIConfig(
    api_name='exit_dns_health',
    display_name='Exit DNS Health',
    cache_max_age_hours=EXIT_DNS_HEALTH_CACHE_MAX_AGE_HOURS,
    timeout_fresh_cache=EXIT_DNS_HEALTH_TIMEOUT_FRESH_CACHE,
    timeout_stale_cache=EXIT_DNS_HEALTH_TIMEOUT_STALE_CACHE,
    use_conditional_requests=False,
    custom_headers={'User-Agent': 'Allium/1.0'},
    count_field='results',
    retry_count=2,               # External API: retry up to 2 times
    retry_delay_base=1.0,
)
# ============================================================================


# Use centralized file I/O utilities
from .file_io_utils import create_cache_manager, create_timestamp_manager

# Initialize file managers
_cache_manager = create_cache_manager(CACHE_DIR)
_timestamp_manager = create_timestamp_manager(CACHE_DIR)

def _save_cache(api_name, data):
    """
    Save API data to cache file using centralized cache manager.
    
    Args:
        api_name: Name of the API (e.g., 'onionoo_details')
        data: Data to cache (will be JSON serialized)
    """
    return _cache_manager.save_cache(api_name, data)


def _load_cache(api_name):
    """
    Load API data from cache file using centralized cache manager.
    
    Args:
        api_name: Name of the API (e.g., 'onionoo_details')
        
    Returns:
        Cached data or None if not available
    """
    return _cache_manager.load_cache(api_name)


def _mark_ready(api_name):
    """
    Mark API as successfully completed
    
    Args:
        api_name: Name of the API
    """
    with _state_lock:
        _worker_status[api_name] = {
            "status": "ready",
            "timestamp": time.time(),
            "error": None
        }
        _save_state()


def _mark_stale(api_name, error_msg):
    """
    Mark API as failed/stale
    
    Args:
        api_name: Name of the API
        error_msg: Error message
    """
    with _state_lock:
        _worker_status[api_name] = {
            "status": "stale",
            "timestamp": time.time(),
            "error": str(error_msg)
        }
        _save_state()


@handle_file_io_errors("save state")
def _save_state():
    """Save worker state to file (called with lock held)"""
    state_data = {
        "workers": _worker_status,
        "last_updated": time.time()
    }
    # Atomic write: a crash mid-dump must not corrupt the existing state
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state_data, f, indent=2)
    os.replace(tmp_path, STATE_FILE)


@handle_file_io_errors("load state")
@handle_json_errors("parse state JSON", default_return={})
def _load_state():
    """Load worker state from file"""
    global _worker_status
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state_data = json.load(f)
            _worker_status = state_data.get("workers", {})
    else:
        _worker_status = {}


def get_worker_status(api_name):
    """
    Get status of a specific worker
    
    Args:
        api_name: Name of the API
        
    Returns:
        dict: Status information or None if not found
    """
    with _state_lock:
        return _worker_status.get(api_name, None)


def get_all_worker_status():
    """
    Get status of all workers
    
    Returns:
        dict: All worker status information
    """
    with _state_lock:
        return _worker_status.copy()


def get_cache_age(api_name):
    """
    Get cache file age in seconds for the given API.
    
    Public accessor that wraps the internal cache manager so external
    modules don't need to import the private ``_cache_manager`` symbol.
    
    Args:
        api_name: Internal API name (e.g., 'onionoo_details')
        
    Returns:
        float: Age in seconds, or None if cache file does not exist
    """
    return _cache_manager.get_cache_age(api_name)


@handle_file_io_errors("save timestamp", context="")
def _write_timestamp(api_name, timestamp_str):
    """
    Store encoded timestamp for conditional requests using centralized timestamp manager.
    
    Args:
        api_name: Name of the API
        timestamp_str: Formatted timestamp string
    """
    return _timestamp_manager.write_timestamp(api_name, timestamp_str)


def _read_timestamp(api_name):
    """
    Read stored timestamp for conditional requests using centralized timestamp manager.
    
    Args:
        api_name: Name of the API
        
    Returns:
        str: Timestamp string or None if not available
    """
    return _timestamp_manager.read_timestamp(api_name)


# ============================================================================
# RETRY WITH EXPONENTIAL BACKOFF
# ============================================================================

# Exceptions that indicate transient failures worth retrying
_RETRYABLE_EXCEPTIONS = (
    TotalTimeoutError,
    socket.timeout,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    ConnectionRefusedError,
    BrokenPipeError,
    socket.gaierror,  # transient DNS resolution failures
)

# Network-related errnos worth retrying; anything else (ENOSPC, EACCES,
# EMFILE, ...) indicates a local problem a retry cannot fix.
_RETRYABLE_ERRNOS = frozenset({
    errno.ECONNRESET, errno.ECONNREFUSED, errno.ECONNABORTED,
    errno.EPIPE, errno.ETIMEDOUT, errno.EHOSTUNREACH,
    errno.ENETUNREACH, errno.ENETDOWN, errno.ENETRESET,
})


def _is_retryable_error(exc: Exception) -> bool:
    """
    Determine if an exception represents a transient error worth retrying.

    Retryable:
      - Timeout errors (TotalTimeoutError, socket.timeout, TimeoutError)
      - Connection errors (reset, refused, aborted, broken pipe)
      - urllib URLError wrapping a retryable socket error
      - HTTP 5xx server errors and 429 Too Many Requests

    Not retryable:
      - HTTP 4xx client errors (except 429)
      - JSON parse errors
      - Validation / data structure errors
    """
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return True
    # IMPORTANT: Check HTTPError BEFORE URLError because HTTPError is a subclass of URLError
    if isinstance(exc, urllib.error.HTTPError):
        # Retry on 5xx server errors and 429 rate limiting
        return exc.code >= 500 or exc.code == 429
    if isinstance(exc, urllib.error.URLError):
        # URLError wrapping a retryable socket error
        if isinstance(exc.reason, _RETRYABLE_EXCEPTIONS):
            return True
        # URLError wrapping OSError with retryable errno
        if isinstance(exc.reason, OSError):
            return exc.reason.errno in _RETRYABLE_ERRNOS
        return False
    if isinstance(exc, OSError):
        # Only network-related errnos; ENOSPC/EACCES etc. are not transient
        return exc.errno in _RETRYABLE_ERRNOS
    return False


def _retry_with_backoff(
    fetch_fn: Callable,
    args: tuple = (),
    kwargs: dict = None,
    retry_count: int = 3,
    retry_delay_base: float = 1.0,
    log_fn: Optional[Callable] = None,
    operation_name: str = "fetch",
) -> Any:
    """
    Execute a function with retry and exponential backoff on transient failures.

    Backoff formula: delay = base * (2 ** attempt) + random jitter [0, 1)
    Example with base=2.0: attempt 0 → 2-3s, attempt 1 → 4-5s, attempt 2 → 8-9s

    Args:
        fetch_fn:         Callable to execute
        args:             Positional arguments for fetch_fn
        kwargs:           Keyword arguments for fetch_fn
        retry_count:      Maximum number of retries (0 = no retry, just one attempt)
        retry_delay_base: Base delay in seconds for exponential backoff
        log_fn:           Optional logging function (receives string messages)
        operation_name:   Human-readable name for log messages

    Returns:
        The return value of fetch_fn on success

    Raises:
        The last exception if all retries are exhausted
    """
    if kwargs is None:
        kwargs = {}

    last_exception = None
    max_attempts = 1 + retry_count  # 1 initial attempt + retry_count retries

    for attempt in range(max_attempts):
        try:
            return fetch_fn(*args, **kwargs)
        except Exception as exc:
            last_exception = exc

            # Don't retry if this is not a transient error
            if not _is_retryable_error(exc):
                raise

            # Don't retry if we've exhausted retries
            if attempt >= max_attempts - 1:
                if log_fn:
                    log_fn(f"{operation_name}: all {max_attempts} attempts failed, giving up")
                raise

            # Calculate backoff delay with jitter
            delay = retry_delay_base * (2 ** attempt) + random.random()

            if log_fn:
                log_fn(
                    f"{operation_name}: attempt {attempt + 1}/{max_attempts} failed "
                    f"({type(exc).__name__}), retrying in {delay:.1f}s..."
                )
            else:
                logger.info(
                    f"{operation_name}: attempt {attempt + 1}/{max_attempts} failed "
                    f"({type(exc).__name__}), retrying in {delay:.1f}s..."
                )

            time.sleep(delay)

    # Should not reach here, but just in case
    raise last_exception  # type: ignore[misc]

# ============================================================================


# ============================================================================
# GENERIC API FETCH WITH CACHE FALLBACK
# ============================================================================

def _fetch_with_cache_fallback(
    url: str,
    config: APIConfig,
    progress_logger: Optional[Callable] = None,
    cache_hours_override: Optional[float] = None,
    return_fresh_cache: bool = False,
    validator: Optional[Callable[[dict], bool]] = None,
) -> Optional[dict]:
    """
    Generic function to fetch API data with smart caching and timeout fallback.
    
    This function implements the common pattern used by all API workers:
    1. Check cache age and validate cache can be loaded
    2. Determine timeout based on cache freshness
    3. Make HTTP request with appropriate timeout
    4. Fall back to cached data on timeout
    5. Save new data to cache on success
    
    Args:
        url: URL to fetch data from
        config: APIConfig with timeout and cache settings
        progress_logger: Optional function for progress messages
        cache_hours_override: Override config's cache_max_age_hours (e.g., for bandwidth API)
        return_fresh_cache: If True, return fresh cache immediately without fetching
        validator: Optional function to validate response data structure
        
    Returns:
        dict: Parsed JSON response or cached data, None if unavailable
    """
    api_name = config.api_name
    display_name = config.display_name
    cache_max_age_hours = cache_hours_override or config.cache_max_age_hours
    cache_max_age_seconds = cache_max_age_hours * 3600
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
    
    # Check cache age AND validate cache can be loaded
    cache_age = _cache_manager.get_cache_age(api_name)
    
    # Pre-load cache to verify it's valid (will be reused on timeout fallback)
    cached_data = None
    if cache_age is not None:
        cached_data = _load_cache(api_name)
        if cached_data is None:
            cache_age = None
            log_progress("cache file exists but is invalid, treating as no cache...")
    
    # If cache is fresh and valid, optionally return immediately
    if return_fresh_cache and cache_age is not None and cache_age < cache_max_age_seconds and cached_data:
        log_progress(f"using cached {display_name} data (less than {cache_max_age_hours} hour(s) old)")
        _mark_ready(api_name)
        item_count = len(cached_data.get(config.count_field, []))
        log_progress(f"loaded {item_count} items from {display_name} cache")
        return cached_data
    
    # Determine timeout based on cache state
    if cache_age is None:
        timeout_seconds = config.timeout_stale_cache
        timeout_display = timeout_seconds / 60
        log_progress(f"no valid cache exists, using {timeout_display:.0f} minute timeout for initial fetch...")
    elif cache_age >= cache_max_age_seconds:
        cache_hours_actual = cache_age / 3600
        timeout_seconds = config.timeout_stale_cache
        timeout_display = timeout_seconds / 60
        log_progress(f"cache is {cache_hours_actual:.1f} hours old (>={cache_max_age_hours}h), using {timeout_display:.0f} minute timeout to refresh...")
    else:
        cache_minutes = cache_age / 60
        timeout_seconds = config.timeout_fresh_cache
        log_progress(f"cache is {cache_minutes:.1f} minutes old (<{cache_max_age_hours}h), using {timeout_seconds} second timeout...")
    
    # Build request with optional conditional headers
    headers = dict(config.custom_headers) if config.custom_headers else {}
    if config.use_conditional_requests:
        prev_timestamp = _read_timestamp(api_name)
        if prev_timestamp:
            headers["If-Modified-Since"] = prev_timestamp
    
    if headers:
        conn = urllib.request.Request(url, headers=headers)
    else:
        conn = urllib.request.Request(url)
    
    # Determine retry count: skip retries when fresh cache is available (fast fallback)
    has_fresh_cache = cached_data is not None and cache_age is not None and cache_age < cache_max_age_seconds
    if has_fresh_cache and not config.retry_on_fresh_cache:
        effective_retries = 0
    else:
        effective_retries = config.retry_count
    
    # Try to fetch with TOTAL timeout (not just socket timeout) + retry with backoff
    # Falls back to cache on exhausted retries or non-retryable errors
    fetch_start = time.time()
    try:
        api_response = _retry_with_backoff(
            fetch_fn=_fetch_url_with_total_timeout,
            args=(url, timeout_seconds, headers if headers else None),
            retry_count=effective_retries,
            retry_delay_base=config.retry_delay_base,
            log_fn=log_progress,
            operation_name=display_name,
        )
    except TotalTimeoutError:
        elapsed = time.time() - fetch_start
        log_progress(f"request exceeded total timeout of {timeout_seconds}s after {elapsed:.1f}s total (includes retries)...")
        if cached_data:
            log_progress(f"using cached {display_name} data due to timeout")
            _mark_ready(api_name)
            return cached_data
        else:
            log_progress("no cached data available after timeout")
            _mark_stale(api_name, f"Total timeout after {timeout_seconds}s with no cache")
            return None
    except (socket.timeout, TimeoutError, urllib.error.URLError) as e:
        elapsed = time.time() - fetch_start
        is_timeout = (
            isinstance(e, (socket.timeout, TimeoutError)) or 
            (isinstance(e, urllib.error.URLError) and isinstance(e.reason, (socket.timeout, TimeoutError)))
        )
        
        if is_timeout:
            log_progress(f"request timed out after {elapsed:.1f}s (limit: {timeout_seconds}s)...")
            if cached_data:
                log_progress(f"using cached {display_name} data due to timeout")
                _mark_ready(api_name)
                return cached_data
            else:
                log_progress("no cached data available after timeout")
                _mark_stale(api_name, f"Timeout after {timeout_seconds}s with no cache")
                return None
        else:
            raise
    except urllib.error.HTTPError:
        # Let the @handle_http_errors decorator handle HTTP errors (304, 4xx, 5xx)
        raise
    except Exception as e:
        # Non-retryable error after exhausting retries
        elapsed = time.time() - fetch_start
        log_progress(f"request failed after {elapsed:.1f}s: {type(e).__name__}: {e}")
        if cached_data:
            log_progress(f"using cached {display_name} data due to error")
            _mark_ready(api_name)
            return cached_data
        else:
            log_progress("no cached data available after error")
            _mark_stale(api_name, f"Error: {type(e).__name__}: {e}")
            return None
    
    fetch_elapsed = time.time() - fetch_start
    
    # Parse JSON response with explicit error handling
    log_progress("parsing JSON response...")
    try:
        data = json.loads(api_response.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        log_progress(f"failed to parse JSON response: {e}")
        if cached_data:
            log_progress(f"using cached {display_name} data due to parse error")
            _mark_ready(api_name)
            return cached_data
        _mark_stale(api_name, f"JSON parse error: {e}")
        return None
    
    # Validate response if validator provided
    if validator and not validator(data):
        log_progress(f"warning: invalid {display_name} data structure")
        if cached_data:
            log_progress("using cached data due to invalid response structure")
            _mark_ready(api_name)
            return cached_data
        return None
    
    # Cache the data
    log_progress(f"caching {display_name} data...")
    _save_cache(api_name, data)
    
    # Write timestamp for future conditional requests
    if config.use_conditional_requests:
        timestamp_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time()))
        _write_timestamp(api_name, timestamp_str)
    
    # Mark as ready
    _mark_ready(api_name)
    
    # Log success with elapsed time
    item_count = len(data.get(config.count_field, []))
    retry_info = f" (with {effective_retries} retries available)" if effective_retries > 0 else ""
    log_progress(f"successfully fetched {item_count} items from {display_name} API in {fetch_elapsed:.1f}s{retry_info}")
    
    return data

# ============================================================================


@handle_http_errors("onionoo_details", "onionoo details", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=True, critical=True)
def fetch_onionoo_details(onionoo_url="https://onionoo.torproject.org/details", progress_logger=None):
    """
    Fetch onionoo details data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with DETAILS_CONFIG settings.
    
    Args:
        onionoo_url: URL to fetch data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo API
    """
    return _fetch_with_cache_fallback(
        url=onionoo_url,
        config=DETAILS_CONFIG,
        progress_logger=progress_logger or print,
    )


@handle_http_errors("onionoo_uptime", "onionoo uptime", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=False, critical=False)
def fetch_onionoo_uptime(onionoo_url="https://onionoo.torproject.org/uptime", progress_logger=None):
    """
    Fetch onionoo uptime data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with UPTIME_CONFIG settings.
    
    Args:
        onionoo_url: URL to fetch uptime data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo uptime API
    """
    return _fetch_with_cache_fallback(
        url=onionoo_url,
        config=UPTIME_CONFIG,
        progress_logger=progress_logger,
    )


@handle_http_errors("onionoo_bandwidth", "onionoo historical bandwidth", _load_cache, _save_cache, _mark_ready, _mark_stale, 
                   allow_exit_on_304=False, critical=False)
def fetch_onionoo_bandwidth(onionoo_url="https://onionoo.torproject.org/bandwidth", cache_hours=12, progress_logger=None):
    """
    Fetch onionoo historical bandwidth data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with BANDWIDTH_CONFIG settings.
    Returns fresh cache immediately if available (no fetch needed for fresh data).
    
    Args:
        onionoo_url: URL to fetch historical bandwidth data from
        cache_hours: Hours to cache historical bandwidth data before refreshing (default: 12)
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response from onionoo historical bandwidth API or cached data
    """
    return _fetch_with_cache_fallback(
        url=onionoo_url,
        config=BANDWIDTH_CONFIG,
        progress_logger=progress_logger,
        cache_hours_override=cache_hours,
        return_fresh_cache=True,  # Return fresh cache immediately without fetching
    )


def _validate_aroi_response(data: dict) -> bool:
    """Validator for AROI API response structure."""
    required_keys = ['metadata', 'statistics', 'results']
    return all(key in data for key in required_keys)


@handle_http_errors("aroi_validation", "AROI validation", _load_cache, _save_cache, _mark_ready, _mark_stale,
                   allow_exit_on_304=False, critical=False)
def fetch_aroi_validation(aroi_url="https://aroivalidator.1aeo.com/latest.json", progress_logger=None):
    """
    Fetch AROI validation data with smart caching and timeout fallback.
    
    Uses the generic _fetch_with_cache_fallback helper with AROI_CONFIG settings.
    Returns fresh cache immediately if available (no fetch needed for fresh data).
    Validates response structure and falls back to cache if invalid.
    
    Args:
        aroi_url: URL to fetch AROI validation data from
        progress_logger: Optional function to call for progress updates
        
    Returns:
        dict: JSON response with AROI validation data
    """
    return _fetch_with_cache_fallback(
        url=aroi_url,
        config=AROI_CONFIG,
        progress_logger=progress_logger or print,
        return_fresh_cache=True,  # Return fresh cache immediately without fetching
        validator=_validate_aroi_response,
    )


def _validate_exit_dns_health_response(data) -> bool:
    """Validator for Exit DNS Health API response structure with type checks."""
    if not isinstance(data, dict):
        return False
    metadata = data.get('metadata')
    results = data.get('results')
    if not isinstance(metadata, dict) or not isinstance(results, list):
        return False
    if 'timestamp' not in metadata or 'dns_success_rate_percent' not in metadata:
        return False
    # Validate all result entries are dicts
    for entry in results:
        if not isinstance(entry, dict):
            return False
    return True


@handle_http_errors("exit_dns_health", "Exit DNS Health", _load_cache, _save_cache, _mark_ready, _mark_stale,
                   allow_exit_on_304=False, critical=False)
def fetch_exit_dns_health(exit_dns_health_url="https://exitdnshealth.1aeo.com/latest.json", progress_logger=None):
    """
    Fetch Exit DNS Health data with smart caching and timeout fallback.

    Tests whether Tor exit relays can handle simple DNS queries.
    Data updates every 12 hours.

    Args:
        exit_dns_health_url: URL to fetch exit DNS health data from
        progress_logger: Optional function to call for progress updates

    Returns:
        dict: JSON response with exit DNS health data
    """
    return _fetch_with_cache_fallback(
        url=exit_dns_health_url,
        config=EXIT_DNS_HEALTH_CONFIG,
        progress_logger=progress_logger or print,
        return_fresh_cache=True,
        validator=_validate_exit_dns_health_response,
    )


def fetch_collector_consensus_data(authorities=None, progress_logger=None):
    """
    Fetch CollecTor consensus data including authority votes and bandwidth files.
    
    This function uses the CollectorFetcher to fetch and parse:
    - Authority votes from CollecTor
    - Bandwidth measurement files
    - Flag thresholds from each authority
    
    Args:
        authorities: Optional list of authority dicts discovered from Onionoo
        progress_logger: Optional function to call for progress updates
    
    Returns:
        dict: Parsed CollecTor data with relay index, flag thresholds, etc.
    """
    from .consensus import is_consensus_evaluation_enabled, CollectorFetcher
    
    api_name = "collector_consensus"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    # Check feature flag
    if not is_consensus_evaluation_enabled():
        log_progress("consensus evaluation feature is disabled")
        return None
    
    # Check cache age first - only refresh if older than configured hours
    cache_age = _cache_manager.get_cache_age(api_name)
    cache_max_age_seconds = COLLECTOR_CACHE_MAX_AGE_HOURS * 3600
    if cache_age is not None and cache_age < cache_max_age_seconds:
        log_progress(f"using cached collector consensus data (less than {COLLECTOR_CACHE_MAX_AGE_HOURS} hour(s) old)")
        cached_data = _load_cache(api_name)
        if cached_data and _validate_collector_cache(cached_data):
            _mark_ready(api_name)
            relay_count = len(cached_data.get('relay_index', {}))
            log_progress(f"loaded {relay_count} relays from collector consensus cache")
            return cached_data
    
    # Initialized before the try so the exception handler can always
    # reference them, even if the failure happens before they are set
    cached_data = None
    timeout_seconds = COLLECTOR_TIMEOUT_STALE_CACHE

    try:
        fetch_start = time.time()
        
        # Determine timeout based on cache availability
        cached_data = _load_cache(api_name)
        if cached_data and _validate_collector_cache(cached_data):
            timeout_seconds = COLLECTOR_TIMEOUT_FRESH_CACHE
            log_progress(f"cache is {(cache_age or 0) / 3600:.1f} hours old (>={COLLECTOR_CACHE_MAX_AGE_HOURS}h), using {timeout_seconds} second timeout to refresh...")
        else:
            timeout_seconds = COLLECTOR_TIMEOUT_STALE_CACHE
            log_progress(f"no valid cache exists, using {timeout_seconds // 60} minute timeout for initial fetch...")
        
        # Create fetcher with optional discovered authorities and retry support
        fetcher = CollectorFetcher(
            timeout=timeout_seconds,
            authorities=authorities,
            retry_count=2,           # Retry individual requests within CollectorFetcher
            retry_delay_base=1.0,    # 1s → 2s backoff per request
        )
        
        # Fetch all data (votes, bandwidth files, build index)
        data = fetcher.fetch_all()
        
        # Log any errors that occurred during fetch
        if data.get('errors'):
            for error in data['errors']:
                log_progress(f"warning: {error}")
        
        # Validate data before caching
        if not data.get('relay_index') and not data.get('votes'):
            log_progress("warning: invalid collector consensus data structure")
            _mark_stale(api_name, "No relay data in response")
            # Try to use cache as fallback
            if cached_data:
                log_progress("using cached collector consensus data due to invalid response")
                return cached_data
            return None
        
        # Cache the data
        log_progress("caching collector consensus data...")
        _save_cache(api_name, data)
        _mark_ready(api_name)
        
        # Log success with timing info
        fetch_elapsed = time.time() - fetch_start
        relay_count = len(data.get('relay_index', {}))
        vote_count = len(data.get('votes', {}))
        timings = data.get('timings', {})
        total_time = sum(timings.values()) if timings else 0
        
        log_progress(f"successfully fetched {relay_count} relays from {vote_count} authority votes ({fetch_elapsed:.1f}s total, {total_time:.1f}s fetch)")
        
        return data
        
    except Exception as e:
        error_msg = str(e)
        is_timeout = 'timeout' in error_msg.lower()
        reason = "timeout" if is_timeout else "error"
        
        log_progress(f"request timed out after {timeout_seconds} seconds..." if is_timeout else f"error: {error_msg}")
        _mark_stale(api_name, f"{reason}: {error_msg}")
        
        if cached_data:
            log_progress(f"using cached collector consensus data due to {reason}")
            return cached_data
        log_progress(f"no cached data available after {reason}")
        return None


def _validate_collector_cache(data):
    """
    Validate collector cache data structure.
    
    Args:
        data: Cached collector data
        
    Returns:
        bool: True if cache is valid
    """
    if not isinstance(data, dict):
        return False
    
    required_keys = ['votes', 'relay_index', 'fetched_at', 'consensus_method_info']
    if not all(key in data for key in required_keys):
        return False
    
    # Ensure consensus_method_info has actual data (not empty from old code or error)
    cmi = data.get('consensus_method_info', {})
    if not cmi.get('total_voters'):
        return False
    
    # Check fetched_at is not too old (max 3 hours)
    fetched_at = data.get('fetched_at', '')
    if fetched_at:
        try:
            fetch_time = datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))
            # Normalize to aware UTC datetime to prevent naive/aware TypeError
            if fetch_time.tzinfo is None:
                fetch_time = fetch_time.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - fetch_time).total_seconds() / 3600
            if age_hours > 3:
                return False
        except Exception:
            # Fail closed: unparseable or invalid timestamps invalidate the cache
            return False
    
    return True


def fetch_collector_data(progress_logger=None):
    """
    Legacy wrapper for fetch_collector_consensus_data.
    Maintained for backward compatibility.
    """
    return fetch_collector_consensus_data(progress_logger=progress_logger)


def _parse_descriptor_listing_timestamp(filename):
    """Parse recent descriptor filename timestamp.
    
    Returns timezone-aware UTC datetime for safe comparison with other
    timezone-aware datetimes throughout the codebase.
    """
    if not filename:
        return None
    try:
        ts_str = filename.replace('-server-descriptors', '')
        return datetime.strptime(ts_str, '%Y-%m-%d-%H-%M-%S').replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _classify_descriptor_freshness(source_age_hours):
    """Classify descriptor source freshness by age in hours."""
    if source_age_hours is None:
        return 'unknown'
    if source_age_hours <= DESCRIPTORS_SOURCE_FRESH_MAX_HOURS:
        return 'fresh'
    if source_age_hours <= DESCRIPTORS_SOURCE_DEGRADED_MAX_HOURS:
        return 'degraded'
    return 'stale'


def _flatten_family_key_groups(family_cert_groups):
    """Flatten family key groups to fp->family_key mapping."""
    fp_to_key = {}
    if not isinstance(family_cert_groups, dict):
        return fp_to_key
    for key, fps in family_cert_groups.items():
        if not key or not isinstance(fps, (list, tuple, set)):
            continue
        for fp in fps:
            if not fp:
                continue
            fp_to_key[str(fp).upper()] = key
    return fp_to_key


def _group_family_keys(fp_to_key):
    """Build family_key -> sorted fingerprints from fp->key map."""
    family_groups = {}
    for fp, key in fp_to_key.items():
        family_groups.setdefault(key, []).append(fp)
    return {k: sorted(v) for k, v in family_groups.items() if v}


def _parse_descriptor_published(value):
    """Parse server descriptor published timestamp."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None


def fetch_collector_descriptors(progress_logger=None):
    """
    Fetch CollecTor server-descriptors covering the last 18 hours and extract
    family-cert presence per relay. Achieves full network coverage on every run.
    
    Relays publish new server descriptors every ~18 hours, and CollecTor publishes
    hourly incremental files (~800-2000 descriptors each, ~10k total relays).
    To see every relay, we fetch the last 18 hours of files.
    
    Optimization: Parsed results are cached per-file. On each run, only NEW files
    (typically 1 per hour) are downloaded. Previously-parsed files are loaded from
    the per-file cache. This means the first run downloads ~30 files (~210MB total),
    but subsequent hourly runs only download ~1 new file (~7MB).
    
    Args:
        progress_logger: Optional function for progress updates
    
    Returns:
        dict with 'family_cert_fingerprints' (list), 'all_seen_fingerprints' (list),
        'fetched_at' (str), or None on failure
    """
    import re
    from .consensus import is_consensus_evaluation_enabled
    
    api_name = "collector_descriptors"
    # Separate cache key for per-file parsed results (persistent across runs)
    file_cache_name = "collector_descriptors_files"
    
    # Relays publish descriptors every ~18 hours (dir-spec §2.1). We fetch files
    # from the last 36 hours (2x publishing interval) to handle CollecTor gaps
    # and ensure full coverage. CollecTor publishes files irregularly (~1/hour
    # on average but with multi-hour gaps), so 36 hours ≈ 25-35 files.
    COVERAGE_HOURS = 36
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    # Check feature flag (same as collector_consensus)
    if not is_consensus_evaluation_enabled():
        log_progress("consensus evaluation feature is disabled")
        return None
    
    # Check cache age on the merged result — if fresh, return it
    cached_data = _load_cache(api_name)
    has_valid_cache = cached_data and _validate_descriptors_cache(cached_data)
    cache_age = _cache_manager.get_cache_age(api_name)
    cache_max_age_seconds = DESCRIPTORS_CACHE_MAX_AGE_HOURS * 3600
    if cache_age is not None and cache_age < cache_max_age_seconds and has_valid_cache:
        log_progress(f"using cached descriptor data (less than {DESCRIPTORS_CACHE_MAX_AGE_HOURS} hour(s) old)")
        _mark_ready(api_name)
        cert_count = len(cached_data.get('family_cert_fingerprints', []))
        seen_count = len(cached_data.get('all_seen_fingerprints', []))
        log_progress(f"loaded {seen_count} relays ({cert_count} with family-cert) from cache")
        return cached_data
    
    try:
        fetch_start = time.time()
        
        # Determine timeout
        if has_valid_cache:
            timeout_seconds = DESCRIPTORS_TIMEOUT_FRESH_CACHE
        else:
            timeout_seconds = DESCRIPTORS_TIMEOUT_STALE_CACHE
        
        base_url = 'https://collector.torproject.org'
        descs_path = '/recent/relay-descriptors/server-descriptors/'
        
        # Step 1: Get directory listing (with total timeout + retry)
        log_progress("fetching server descriptor listing...")
        listing_url = f"{base_url}{descs_path}"
        listing_headers = {'User-Agent': 'Allium/1.0'}
        raw_listing = _retry_with_backoff(
            fetch_fn=_fetch_url_with_total_timeout,
            args=(listing_url, timeout_seconds, listing_headers),
            retry_count=2,
            retry_delay_base=1.0,
            log_fn=log_progress,
            operation_name="descriptor listing",
        )
        html = raw_listing.decode('utf-8', errors='replace')
        
        pattern = r'href="([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-server-descriptors)"'
        all_files = sorted(re.findall(pattern, html))
        if not all_files:
            log_progress("warning: no server descriptor files found")
            _mark_stale(api_name, "No descriptor files found")
            return cached_data if has_valid_cache else None
        
        # Freshness gate: classify the source itself before recomputing.
        latest_recent_file_ts = _parse_descriptor_listing_timestamp(all_files[-1])
        source_age_hours = None
        if latest_recent_file_ts is not None:
            source_age_hours = (datetime.now(timezone.utc) - latest_recent_file_ts).total_seconds() / 3600
        source_freshness = _classify_descriptor_freshness(source_age_hours)
        is_critical_stale = (
            source_age_hours is not None
            and source_age_hours > DESCRIPTORS_SOURCE_CRITICAL_MAX_HOURS
        )
        if source_freshness == 'stale' and has_valid_cache:
            lag_msg = (
                f"descriptor source is stale ({source_age_hours:.1f}h old), "
                f"keeping prior cached status"
            )
            if is_critical_stale:
                lag_msg += " [critical]"
            log_progress(lag_msg)
            _mark_stale(api_name, lag_msg)
            return cached_data

        # Step 2: Select files from the last COVERAGE_HOURS by parsing timestamps
        # Filename format: YYYY-MM-DD-HH-MM-SS-server-descriptors
        cutoff = datetime.now(timezone.utc) - timedelta(hours=COVERAGE_HOURS)
        target_files = []
        for fname in all_files:
            file_time = _parse_descriptor_listing_timestamp(fname)
            if file_time and file_time >= cutoff:
                target_files.append(fname)
        
        if not target_files:
            # Fallback: if no files match the time window, take the latest 24
            target_files = all_files[-24:]
        
        # Step 3: Load per-file cache (maps filename → parsed result)
        file_cache = _load_cache(file_cache_name) or {}
        
        # Step 4: Download and parse only NEW files; reuse cached results
        files_downloaded = 0
        files_from_cache = 0
        all_seen_fps = set()
        
        for filename in target_files:
            if filename in file_cache and 'cert_keys' in file_cache[filename]:
                # Reuse cached parse result for this file
                file_result = file_cache[filename]
                all_seen_fps.update(fp.upper() for fp in file_result.get('cert', []))
                all_seen_fps.update(fp.upper() for fp in file_result.get('no_cert', []))
                files_from_cache += 1
            else:
                # Download and parse this new file (with total timeout + retry)
                url = f"{base_url}{descs_path}{filename}"
                try:
                    file_headers = {'User-Agent': 'Allium/1.0'}
                    raw_content = _retry_with_backoff(
                        fetch_fn=_fetch_url_with_total_timeout,
                        args=(url, timeout_seconds, file_headers),
                        retry_count=2,
                        retry_delay_base=1.0,
                        operation_name=f"descriptor file {filename}",
                    )
                    content = raw_content.decode('utf-8', errors='replace')
                    
                    # Single-pass parse: fingerprint + family-cert presence + family key extraction
                    cert_fps = set()
                    no_cert_fps = set()
                    fp_to_family_key = {}
                    cert_published = {}
                    no_cert_published = {}
                    current_fp = None
                    has_cert = False
                    in_cert_block = False
                    cert_b64_lines = []
                    current_family_key = None
                    current_published = None
                    
                    for line in content.splitlines():
                        if in_cert_block:
                            if line.startswith('-----END'):
                                in_cert_block = False
                                try:
                                    cert_bytes = base64.b64decode(''.join(cert_b64_lines))
                                    # Family key is the SIGNING key (ext type 0x04),
                                    # not the certified key (which is per-relay identity).
                                    if len(cert_bytes) > 40:
                                        n_ext = cert_bytes[39]
                                        off = 40
                                        for _ in range(n_ext):
                                            if off + 4 > len(cert_bytes):
                                                break
                                            ext_len = int.from_bytes(cert_bytes[off:off + 2], 'big')
                                            ext_type = cert_bytes[off + 2]
                                            if off + 4 + ext_len > len(cert_bytes):
                                                break
                                            if ext_type == 0x04 and ext_len == 32:
                                                current_family_key = cert_bytes[off + 4:off + 4 + 32].hex().upper()
                                                break
                                            off += 4 + ext_len
                                except (IndexError, ValueError) as e:
                                    logger.debug("family-cert parse failed for %s: %s", current_fp, e)
                                cert_b64_lines = []
                            elif not line.startswith('-----'):
                                cert_b64_lines.append(line.strip())
                            continue
                        
                        if line.startswith('router '):
                            if current_fp is not None:
                                if has_cert:
                                    cert_fps.add(current_fp)
                                    if current_family_key:
                                        fp_to_family_key[current_fp] = current_family_key
                                    if current_published:
                                        cert_published[current_fp] = current_published
                                else:
                                    no_cert_fps.add(current_fp)
                                    if current_published:
                                        no_cert_published[current_fp] = current_published
                            current_fp = None
                            has_cert = False
                            current_family_key = None
                            current_published = None
                        elif line.startswith('fingerprint '):
                            current_fp = line[12:].replace(' ', '').upper()
                        elif line.startswith('published '):
                            current_published = line[10:].strip()
                        elif line.rstrip() == 'family-cert':
                            has_cert = True
                            in_cert_block = True
                            cert_b64_lines = []
                    
                    if current_fp is not None:
                        if has_cert:
                            cert_fps.add(current_fp)
                            if current_family_key:
                                fp_to_family_key[current_fp] = current_family_key
                            if current_published:
                                cert_published[current_fp] = current_published
                        else:
                            no_cert_fps.add(current_fp)
                            if current_published:
                                no_cert_published[current_fp] = current_published
                    
                    # Cache this file's parsed result
                    file_cache[filename] = {
                        'cert': list(cert_fps),
                        'no_cert': list(no_cert_fps),
                        'cert_keys': fp_to_family_key,
                        'cert_published': cert_published,
                        'no_cert_published': no_cert_published,
                    }
                    
                    all_seen_fps.update(fp.upper() for fp in cert_fps)
                    all_seen_fps.update(fp.upper() for fp in no_cert_fps)
                    files_downloaded += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch {filename}: {e}")
                    continue
        
        if not all_seen_fps:
            log_progress("warning: no descriptors parsed from any file")
            _mark_stale(api_name, "No descriptors parsed")
            return cached_data if has_valid_cache else None
        
        # Step 5: Build raw latest-file-wins result from chronological file list.
        raw_line_cert_fps = set()
        raw_seen_fps = set()
        raw_fp_to_key = {}
        raw_cert_published = {}
        raw_no_cert_published = {}
        for filename in target_files:
            if filename in file_cache:
                file_result = file_cache[filename]
                cert_in_file = {fp.upper() for fp in file_result.get('cert', [])}
                no_cert_in_file = {fp.upper() for fp in file_result.get('no_cert', [])}
                cert_keys_in_file = {fp.upper(): key for fp, key in file_result.get('cert_keys', {}).items()}
                cert_published_in_file = {
                    fp.upper(): val
                    for fp, val in file_result.get('cert_published', {}).items()
                }
                no_cert_published_in_file = {
                    fp.upper(): val
                    for fp, val in file_result.get('no_cert_published', {}).items()
                }

                # Later files override earlier.
                raw_line_cert_fps.update(cert_in_file)
                raw_line_cert_fps -= no_cert_in_file
                raw_seen_fps.update(cert_in_file)
                raw_seen_fps.update(no_cert_in_file)

                for fp, key in cert_keys_in_file.items():
                    raw_fp_to_key[fp] = key
                for fp in no_cert_in_file:
                    raw_fp_to_key.pop(fp, None)

                for fp, published in cert_published_in_file.items():
                    raw_cert_published[fp] = published
                    raw_no_cert_published.pop(fp, None)
                for fp, published in no_cert_published_in_file.items():
                    raw_no_cert_published[fp] = published
                    raw_cert_published.pop(fp, None)

        # Policy overlay: default to raw output, then preserve prior status as needed.
        final_line_cert_fps = set(raw_line_cert_fps)
        final_seen_fps = set(raw_seen_fps)
        final_fp_to_key = dict(raw_fp_to_key)
        pending_no_cert = {}
        last_cert_published = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        if has_valid_cache:
            prior_line_cert_fps = {fp.upper() for fp in cached_data.get('family_cert_fingerprints', [])}
            prior_seen_fps = {fp.upper() for fp in cached_data.get('all_seen_fingerprints', [])}
            prior_fp_to_key = _flatten_family_key_groups(cached_data.get('family_cert_groups', {}))

            prev_state = cached_data.get('hf_transition_state', {})
            if isinstance(prev_state, dict):
                for fp, entry in (prev_state.get('pending_no_cert', {}) or {}).items():
                    if isinstance(entry, dict):
                        try:
                            count = int(entry.get('count', 0))
                        except (TypeError, ValueError):
                            count = 0
                        pending_no_cert[str(fp).upper()] = {
                            'count': max(0, count),
                            'first_seen': entry.get('first_seen'),
                            'last_seen': entry.get('last_seen'),
                        }
                for fp, published in (prev_state.get('last_cert_published', {}) or {}).items():
                    if isinstance(published, str):
                        last_cert_published[str(fp).upper()] = published

            for fp, published in raw_cert_published.items():
                if published:
                    last_cert_published[fp] = published

            if source_freshness in {'degraded', 'unknown'}:
                # Degraded source: keep prior status, but allow upgrades.
                final_line_cert_fps.update(prior_line_cert_fps)
                final_seen_fps.update(prior_seen_fps)
                final_fp_to_key = dict(prior_fp_to_key)
                final_fp_to_key.update(raw_fp_to_key)
                for fp in raw_line_cert_fps:
                    pending_no_cert.pop(fp, None)
            elif source_freshness == 'fresh':
                # Fresh source: apply downgrade confirmation.
                downgrade_candidates = (
                    (prior_line_cert_fps - raw_line_cert_fps)
                    | (set(prior_fp_to_key.keys()) - set(raw_fp_to_key.keys()))
                )
                for fp in downgrade_candidates:
                    prev = pending_no_cert.get(fp, {})
                    count = int(prev.get('count', 0)) + 1
                    pending_no_cert[fp] = {
                        'count': count,
                        'first_seen': prev.get('first_seen') or now_iso,
                        'last_seen': now_iso,
                    }
                    is_confirmed = count >= DESCRIPTORS_DOWNGRADE_CONFIRM_RUNS
                    if not is_confirmed:
                        no_cert_published = raw_no_cert_published.get(fp)
                        if no_cert_published:
                            cert_ts = _parse_descriptor_published(last_cert_published.get(fp))
                            no_cert_ts = _parse_descriptor_published(no_cert_published)
                            if cert_ts and no_cert_ts:
                                delta_hours = (no_cert_ts - cert_ts).total_seconds() / 3600
                                if delta_hours >= DESCRIPTORS_DOWNGRADE_MIN_PUBLISHED_DELTA_HOURS:
                                    is_confirmed = True
                    if is_confirmed:
                        pending_no_cert.pop(fp, None)
                    else:
                        final_line_cert_fps.add(fp)
                        if fp in prior_fp_to_key:
                            final_fp_to_key[fp] = prior_fp_to_key[fp]
                for fp in raw_line_cert_fps:
                    pending_no_cert.pop(fp, None)

        # Build final family_cert_groups from final fp->family_key map.
        family_cert_groups = _group_family_keys(final_fp_to_key)

        # Prune transition metadata to relevant relays.
        pending_keys = set(pending_no_cert.keys())
        keep_last_cert_keys = set(final_line_cert_fps) | pending_keys
        last_cert_published = {
            fp: published
            for fp, published in last_cert_published.items()
            if fp in keep_last_cert_keys and isinstance(published, str)
        }

        transition_state = {
            'pending_no_cert': pending_no_cert,
            'last_cert_published': last_cert_published,
        }

        # Step 6: Prune file cache — remove files older than our window
        target_set = set(target_files)
        stale_keys = [k for k in file_cache if k not in target_set]
        for k in stale_keys:
            del file_cache[k]
        
        # Step 7: Save both caches
        _save_cache(file_cache_name, file_cache)
        
        data = {
            'family_cert_fingerprints': sorted(final_line_cert_fps),
            'all_seen_fingerprints': sorted(final_seen_fps),
            'family_cert_groups': family_cert_groups,
            'coverage_hours': COVERAGE_HOURS,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'source_latest_file_ts': latest_recent_file_ts.isoformat() if latest_recent_file_ts else None,
            'source_age_hours': round(source_age_hours, 3) if source_age_hours is not None else None,
            'source_freshness': source_freshness,
            'source_critical_stale': is_critical_stale,
            'hf_transition_state': transition_state,
        }
        _save_cache(api_name, data)
        _mark_ready(api_name)
        
        fetch_elapsed = time.time() - fetch_start
        verified_cert_fps = set(final_fp_to_key.keys())
        cert_without_key = len(set(final_line_cert_fps) - verified_cert_fps)
        key_info = f", {len(verified_cert_fps)} with verified key"
        if cert_without_key > 0:
            key_info += f", {cert_without_key} cert-present-but-key-not-extracted"
        freshness_info = (
            f"{source_freshness}"
            if source_age_hours is None
            else f"{source_freshness}, source_age={source_age_hours:.1f}h"
        )
        log_progress(
            f"{len(final_seen_fps)} relays tracked ({len(final_line_cert_fps)} with family-cert{key_info}) "
            f"from {len(target_files)} hourly files "
            f"({files_downloaded} downloaded, {files_from_cache} cached) in {fetch_elapsed:.1f}s "
            f"[{freshness_info}]"
        )
        return data
        
    except Exception as e:
        error_msg = str(e)
        is_timeout = 'timeout' in error_msg.lower()
        reason = "timeout" if is_timeout else "error"
        
        log_progress(f"request timed out after {timeout_seconds}s..." if is_timeout else f"error: {error_msg}")
        _mark_stale(api_name, f"{reason}: {error_msg}")
        
        if has_valid_cache:
            log_progress(f"using cached descriptor data due to {reason}")
            return cached_data
        log_progress(f"no cached data available after {reason}")
        return None


def _validate_descriptors_cache(data):
    """
    Validate descriptors cache data structure.
    Requires family_cert_groups for Ed25519 key-based Happy Families
    classification. Caches from older code without this field are
    rejected so they get re-fetched with full key extraction.
    """
    if not isinstance(data, dict):
        return False
    if 'family_cert_fingerprints' not in data:
        return False
    if 'all_seen_fingerprints' not in data:
        return False
    if 'family_cert_groups' not in data:
        return False
    return True


def fetch_consensus_health(progress_logger=None):
    """
    Fetch consensus health data using AuthorityMonitor.
    
    Uses TCP socket probes (not HTTP) to check authority responsiveness.
    Falls back to cached data on failure.
    
    Args:
        progress_logger: Optional function to call for progress updates
    
    Returns:
        dict: Consensus health data
    """
    from .consensus import is_consensus_evaluation_enabled, AuthorityMonitor
    
    api_name = "consensus_health"
    
    def log_progress(message):
        if progress_logger:
            progress_logger(message)
        else:
            print(message)
    
    # Check feature flag
    if not is_consensus_evaluation_enabled():
        log_progress("consensus evaluation feature is disabled")
        return None
    
    # Pre-load cache for fallback
    cached_data = _load_cache(api_name)
    
    try:
        log_progress("checking authority health status...")
        fetch_start = time.time()
        
        # Create monitor and check all authorities
        monitor = AuthorityMonitor(timeout=10)
        status = monitor.check_all_authorities()
        summary = monitor.get_summary(status)
        alerts = monitor.get_alerts(status)
        
        elapsed = time.time() - fetch_start
        
        data = {
            'authority_status': status,
            'summary': summary,
            'alerts': alerts,
            'fetched_at': summary.get('checked_at'),
        }
        
        # Cache the data for future fallback
        _save_cache(api_name, data)
        _mark_ready(api_name)
        
        online_count = summary.get('online_count', 0)
        total = summary.get('total_authorities', 0)
        log_progress(f"authority health check complete: {online_count}/{total} online in {elapsed:.1f}s")
        
        return data
        
    except Exception as e:
        error_msg = f"Failed to fetch consensus health: {str(e)}"
        log_progress(f"error: {error_msg}")
        _mark_stale(api_name, error_msg)
        
        # Fall back to cached data if available
        if cached_data:
            log_progress("using cached consensus health data due to error")
            return cached_data
        log_progress("no cached consensus health data available")
        return None


# Initialize state on module import
_load_state() 