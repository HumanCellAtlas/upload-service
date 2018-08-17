#!/usr/bin/env python3.6

import json

from tests.unit import UploadTestCaseUsingMockAWS, EnvironmentSetup
from tests.unit.lambdas.api_server import client_for_test_api_server
from upload.common.upload_config import UploadVersion, UploadConfig


class TestVersionEndpoint(UploadTestCaseUsingMockAWS):
    def setUp(self):
        super().setUp()
        self.upload_service_version = 'best_version'
        self.upload_version = UploadVersion()
        self.upload_version.set({
            'upload_service_version': self.upload_service_version,
        })

        # Setup app
        self.client = client_for_test_api_server()

    def test_get_version(self):
        response = self.client.get(f"/version")

        self.assertEqual(200, response.status_code)
        data = json.loads(response.data)

        self.assertEquals(self.upload_service_version, data['upload_service_version'])
