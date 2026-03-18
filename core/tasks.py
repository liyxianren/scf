"""Async task runner abstraction.

Current implementation uses daemon threads.
Can be swapped to Celery/RQ later without changing callers.
"""
import threading
from flask import current_app


class TaskRunner:
    """Run functions asynchronously with Flask app context."""

    @staticmethod
    def run_async(func, *args, **kwargs):
        """Run func in a background thread with app context injected."""
        app = current_app._get_current_object()

        def wrapper():
            with app.app_context():
                func(*args, **kwargs)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return thread
