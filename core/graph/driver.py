import threading
from django.conf import settings
from neo4j import GraphDatabase

_driver = None
_lock = threading.Lock()


def get_driver():
    global _driver
    if _driver is None:
        with _lock:
            if _driver is None:
                _driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                )
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
