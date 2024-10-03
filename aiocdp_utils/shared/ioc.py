import logging

from aiocdp import ioc, IChrome

_chrome = None


def get_chrome():
    global _chrome

    if not _chrome:
        _chrome = ioc.get_class(IChrome).init(
            host='127.0.0.1',
            port=9222
        )

    return _chrome


def get_logger():
    return logging.getLogger('aiocdp_utils')