from . import client_for_test_api_server
from ... import UploadTestCaseUsingMockAWS, EnvironmentSetup

# The following line is a HACK to stop database.yml opening a connection when file upload-api.yml is read.
from upload.common.database import get_pg_record


class TestHealthcheckEndpoint(UploadTestCaseUsingMockAWS):

    def test_heathcheck_endpoint(self):
        self.client = client_for_test_api_server()

        response = self.client.get(f"/v1/health")

        self.assertEqual(response.status_code, 200)
