import json
import uuid

from tenacity import stop_after_attempt

from upload.common.exceptions import UploadException
from upload.common.sqs_queue import DeletionSQSQueue, CsumSQSQueue
from upload.common.upload_area import UploadArea
from .. import UploadTestCaseUsingMockAWS


class SqsQueueTest(UploadTestCaseUsingMockAWS):
    """ Unit tests for the SQSQueue class and its subclasses DeletionSQSQueue and CsumSQSQueue. """

    def setUp(self):
        super().setUp()

        self.upload_area_id = str(uuid.uuid4())
        self.upload_area = UploadArea(self.upload_area_id)

    def test__enqueue_csum_sqs_queue__successful(self):
        filename = "some.json"

        CsumSQSQueue(self.upload_area, filename).enqueue()

        message = self.sqs.meta.client.receive_message(QueueUrl='csum_sqs_url')
        message_body = json.loads(message['Messages'][0]['Body'])
        s3_key = message_body['Records'][0]['s3']['object']['key']
        s3_bucket = message_body['Records'][0]['s3']['bucket']['name']

        self.assertEqual(s3_key, f"{self.upload_area_id}/{filename}")
        self.assertEqual(s3_bucket, "bogobucket")

    def test__enqueue_csum_sqs_queue__fails(self):
        # Disable retries for test
        DeletionSQSQueue.enqueue.retry.stop = stop_after_attempt(1)

        self.upload_area.config.csum_upload_q_url = "some_bogus_url"
        filename = "some.json"

        with self.assertRaises(UploadException):
            CsumSQSQueue(self.upload_area, filename).enqueue()

    def test__enqueue_deletion_sqs_queue__successful(self):
        DeletionSQSQueue(self.upload_area).enqueue()

        message = self.sqs.meta.client.receive_message(QueueUrl='delete_sqs_url')
        message_body = json.loads(message['Messages'][0]['Body'])
        self.assertEqual(message_body['area_uuid'], self.upload_area_id)

    def test__enqueue_deletion_sqs_queue__fails(self):
        # Disable retries for test
        DeletionSQSQueue.enqueue.retry.stop = stop_after_attempt(1)

        self.upload_area.config.area_deletion_q_url = "some_bogus_url"

        with self.assertRaises(UploadException):
            DeletionSQSQueue(self.upload_area).enqueue()
