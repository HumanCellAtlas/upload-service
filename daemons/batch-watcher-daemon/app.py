from upload.common.logging import get_logger
from upload.lambdas.batch_watcher.batch_watcher import BatchWatcher


def batch_watcher_handler(event, context):
    BatchWatcher().run()
