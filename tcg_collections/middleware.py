import time
import logging
from django.db.backends.utils import CursorWrapper

logger = logging.getLogger(__name__)

class SlowQueryMiddleware:
    SLOW_QUERY_THRESHOLD = 0.2

    def __init__(self, get_response):
        self.get_response = get_response
        print('Middleware init')
    
    def __call__(self, request):
        from django.db import connections
        for conn in connections.all():
            with conn.execute_wrapper(self.log_query):
                response = self.get_response(request)
        return response
    
    def log_query(self, execute, sql, params, many, context):
        start = time.time()
        try:
            return execute(sql, params, many, context)
        finally:
            duration = time.time() - start
            if duration > self.SLOW_QUERY_THRESHOLD:
                logger.warning(f"Slow query: {duration:.2f}s - {sql[:100]}")