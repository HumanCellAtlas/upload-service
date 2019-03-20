from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup


class TestHealthcheckEndpoint(UploadTestCaseUsingMockAWS):

    def test_heathcheck_endpoint(self):
        self.client = client_for_test_api_server()

        response = self.client.get(f"/health")

        self.assertEqual(response.status_code, 200)
