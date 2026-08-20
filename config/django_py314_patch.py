"""
Python 3.14 compatibility patch for Django template context.
Fixes AttributeError: 'super' object has no attribute 'dicts'
"""

import logging

logger = logging.getLogger(__name__)

def patch_django_context():
    """Monkey patch Django's context classes for Python 3.14 compatibility"""
    try:
        from django.template import context
        
        def patched_base_context_copy(self):
            """Fixed __copy__ for BaseContext"""
            duplicate = self.__class__()
            duplicate.dicts = self.dicts[:]
            return duplicate
        
        def patched_request_context_copy(self):
            """Fixed __copy__ for RequestContext"""  
            duplicate = object.__new__(self.__class__)
            duplicate.__dict__.update(self.__dict__)
            duplicate.dicts = self.dicts[:]
            return duplicate
        
        # Apply patches
        context.BaseContext.__copy__ = patched_base_context_copy
        context.RequestContext.__copy__ = patched_request_context_copy
        
        logger.debug("Applied Python 3.14 compatibility patch for Django admin")
        return True
    except Exception as e:
        logger.warning("Failed to patch Django context: %s", e)
        return False
