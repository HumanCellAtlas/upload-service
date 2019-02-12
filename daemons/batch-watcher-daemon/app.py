from upload.common.logging import configure_logger
from upload.lambdas.batch_watcher.batch_watcher import BatchWatcher

configure_logger()


def batch_watcher_handler(event, context):
    BatchWatcher().run()
