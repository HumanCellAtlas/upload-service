import logging
import os

"""
This variable keeps track of whether a handler has been attached to the root logger or not. We only want one handler
to be attached to the root logger since we only emit the message in one location. Child loggers will have no handler
since log message are propagated up to the root logger's handler by default.
"""
_root_logging_configured = False
_log_level = getattr(logging, (os.environ['LOG_LEVEL'] if 'LOG_LEVEL' in os.environ else 'DEBUG').upper())


def configure_logger():
    """
    Configures a root logger.

    If a root logger is already configured (indicated by the global variable _root_logging_configured) or if the root
    logger already has a handler, then return without adding any new handlers. Otherwise create and add a handler to
    the
    root logger.
    """
    global _root_logging_configured
    root_logger = logging.getLogger()

    # If root logger already has a handler attached, log this fact and return.
    if _root_logging_configured:
        root_logger.info(
            "Root logger was already configured in this interpreter process. The currently registered handlers, "
            "formatters, filters, and log levels will be left as is.")
        return
    if root_logger.hasHandlers():
        root_logger.warning(
            "Root logger somehow already has a handler attached in this interpreter process. The currently registered "
            "handlers, formatters, filters, and log levels will be left as is.")
        return

    # The root logger hasn't been configured yet with a handler, so create one and attach it.
    logging.basicConfig(level=_log_level)
