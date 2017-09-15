from staging import StagingArea
from .ingest_notifier import IngestNotifier


class ChecksumDaemon:

    def __init__(self, context):
        self._context = context
        self.log("Ahm ahliiivvve!")

    def consume_event(self, event):
        for record in event['Records']:
            if record['eventName'] != 'ObjectCreated:Put':
                self.log(f"WARNING: Unexpected event: {record['eventName']}")
                continue
            file_key = record['s3']['object']['key']
            staged_file = self._retrieve_file(file_key)
            self._checksum_file(staged_file)
            self._notify_ingest(staged_file)

    def _retrieve_file(self, file_key):
        self.log(f"File: {file_key}")
        area_uuid = file_key.split('/')[0]
        filename = file_key[len(area_uuid) + 1:]
        return StagingArea(area_uuid).staged_file(filename)

    def _checksum_file(self, staged_file):
        staged_file.compute_checksums()
        tags = staged_file.save_tags()
        self.log(f"Checksummed and tagged with: {tags}")

    def _notify_ingest(self, staged_file):
        payload = staged_file.info()
        status = IngestNotifier().file_was_staged(payload)
        self.log(f"Notified Ingest: payload={payload}, status={status}")

    def log(self, message):
        self._context.log(message)
