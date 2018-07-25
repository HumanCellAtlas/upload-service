from upload.lambdas.checksum_daemon import ChecksumDaemon


def call_checksum_daemon(event, context):
    ChecksumDaemon(context).consume_event(event)
