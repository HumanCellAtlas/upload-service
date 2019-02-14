import json
import os
from tempfile import TemporaryDirectory

import responses
import tenacity
from mock import patch

from upload.common.exceptions import UploadException
from upload.docker_images.validator.validator_harness import ValidatorHarness
from .. import UploadTestCaseUsingMockAWS, EnvironmentSetup


class TestValidatorHarness(UploadTestCaseUsingMockAWS):

    def setUp(self):
        super().setUp()

        self.validation_id = '123'
        self.environment = {
            'BUCKET_NAME': self.upload_config.bucket_name,
            'AWS_BATCH_JOB_ID': '1',
            'AWS_BATCH_JOB_ATTEMPT': '1',
            'VALIDATION_ID': str(self.validation_id)
        }
        self.environmentor = EnvironmentSetup(self.environment)
        self.environmentor.enter()

        # Put a file in the bucket we can validate
        self.upload_area_id = "testtest-test-test-test-teeeeeeeeest"
        self.filename = "test_file"
        self.file_contents = "foobar\n"
        self.s3_object_key = f"{self.upload_area_id}/{self.filename}"
        s3obj = self.upload_bucket.Object(self.s3_object_key)
        s3obj.put(Body=self.file_contents)
        self.s3_url = f"s3://{self.upload_config.bucket_name}/{self.s3_object_key}"

    def tearDown(self):
        super().tearDown()
        self.environmentor.exit()

    def test__stage_files_to_be_validated__downloads_file_from_s3(self):
        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator=None,
                                       s3_urls_of_files_to_be_validated=[self.s3_url],
                                       staging_folder=staging_dir)

            harness._stage_files_to_be_validated()

            expected_file_path = f"{staging_dir}/{self.upload_area_id}/{self.filename}"
            self.assertTrue(os.path.isfile(expected_file_path))
            with open(expected_file_path, 'r') as fp:
                self.assertEqual(self.file_contents, fp.read())

    def _mock_stage_file_succeeding_on_the_5th_try(self, s3_bucket_name, s3_object_key, staged_file_path):
        if self.mock_download_file_call_count < 4:
            pass
        else:
            with open(self.expected_file_path, 'w') as fp:
                fp.write(self.file_contents)
        self.mock_download_file_call_count += 1

    def _mock_stage_file_never_succeeding(self, s3_bucket_name, s3_object_key, staged_file_path):
        self.mock_download_file_call_count += 1

    @patch('upload.docker_images.validator.validator_harness.ValidatorHarness._download_file_from_bucket_to_filesystem')
    def test__stage_files_to_be_validated__retries_5_times(self, mock_download_file):

        mock_download_file.side_effect = self._mock_stage_file_succeeding_on_the_5th_try

        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator=None,
                                       s3_urls_of_files_to_be_validated=[self.s3_url],
                                       staging_folder=staging_dir)
            harness._stage_files_to_be_validated.retry.wait = tenacity.wait_none()  # Speed things up

            self.expected_file_path = f"{staging_dir}/{self.upload_area_id}/{self.filename}"
            self.mock_download_file_call_count = 0

            harness._stage_files_to_be_validated()

            self.assertEqual(5, self.mock_download_file_call_count)
            self.assertTrue(os.path.isfile(self.expected_file_path))

    @patch('upload.docker_images.validator.validator_harness.ValidatorHarness._download_file_from_bucket_to_filesystem')
    def test__stage_files_to_be_validated__gives_up_after_5_tries(self, mock_download_file):

        mock_download_file.side_effect = self._mock_stage_file_never_succeeding

        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator=None,
                                       s3_urls_of_files_to_be_validated=[self.s3_url],
                                       staging_folder=staging_dir)
            harness._stage_files_to_be_validated.retry.wait = tenacity.wait_none()  # Speed things up

            self.expected_file_path = f"{staging_dir}/{self.upload_area_id}/{self.filename}"
            self.mock_download_file_call_count = 0

            with self.assertRaises(UploadException):
                harness._stage_files_to_be_validated()

            self.assertEqual(5, self.mock_download_file_call_count)

    def test__unstage_files__removes_staged_file(self):
        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator=None,
                                       s3_urls_of_files_to_be_validated=[self.s3_url],
                                       staging_folder=staging_dir)
            harness._stage_files_to_be_validated()
            expected_file_path = f"{staging_dir}/{self.upload_area_id}/{self.filename}"
            self.assertTrue(os.path.isfile(expected_file_path))

            harness._unstage_files()

            self.assertFalse(os.path.isfile(expected_file_path))

    def test__run_validator__runs_binary_and_returns_results_dict_for_validator_running_successfully(self):
        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator='/usr/bin/sum',
                                       s3_urls_of_files_to_be_validated=[self.s3_url],
                                       staging_folder=staging_dir)
            harness._stage_files_to_be_validated()
            expected_file_path = f"{staging_dir}/{self.upload_area_id}/{self.filename}"
            self.assertTrue(os.path.isfile(expected_file_path))

            results = harness._run_validator()

            results_keys = list(results.keys())
            results_keys.sort()
            self.assertEqual(['command', 'duration_s', 'exception', 'exit_code',
                              'status', 'stderr', 'stdout', 'validation_id'], results_keys)
            self.assertEqual(results['command'], f"/usr/bin/sum {expected_file_path}")
            self.assertEqual(results['exception'], None)
            self.assertEqual(results['exit_code'], 0)
            self.assertEqual(results['status'], 'completed')
            self.assertEqual(results['stderr'], '')
            self.assertIn("32883", results['stdout'])
            self.assertEqual(results['validation_id'], self.validation_id)
            harness._unstage_files()

    def test__run_validator__runs_binary_and_catches_exit_code_and_stderr_for_validation_with_errors(self):
        filename = "a_file_that_does_not_exist"
        s3_url = f"s3://{self.upload_config.bucket_name}/{self.upload_area_id}/{filename}"

        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator='/usr/bin/sum',
                                       s3_urls_of_files_to_be_validated=[s3_url],
                                       staging_folder=staging_dir)

            expected_file_path = f"{staging_dir}/{self.upload_area_id}/{filename}"
            harness.staged_file_paths = [expected_file_path]  # hack to make harness happy as we didn't stage

            results = harness._run_validator()

            results_keys = list(results.keys())
            results_keys.sort()
            self.assertEqual(['command', 'duration_s', 'exception', 'exit_code',
                              'status', 'stderr', 'stdout', 'validation_id'], results_keys)
            self.assertEqual(results['exception'], None)
            self.assertEqual(results['exit_code'], 1)
            self.assertEqual(results['status'], 'completed')
            self.assertIn(f"sum: {expected_file_path}: No such file or directory", results['stderr'])
            self.assertEqual(results['stdout'], '')
            self.assertEqual(results['validation_id'], self.validation_id)

    @responses.activate
    def test__validate__contacts_upload_api_to_update_validation_record(self):
        responses.add(responses.POST,
                      "https://{api_host}/v1/area/{upload_area_id}/update_validation/{validation_id}".format(
                          api_host=os.environ['API_HOST'],
                          upload_area_id=self.upload_area_id,
                          validation_id=self.validation_id
                      ),
                      status=204)

        with TemporaryDirectory() as staging_dir:
            harness = ValidatorHarness(path_to_validator='/usr/bin/sum',
                                       s3_urls_of_files_to_be_validated=[self.s3_url],
                                       staging_folder=staging_dir)

            harness.validate()

            self.assertEqual(2, len(responses.calls))
            expected_body_1 = {
                "status": "VALIDATING", "job_id": "1",
                "payload": {"upload_area_id": self.upload_area_id, "names": [self.filename]}
            }
            self.assertEqual(expected_body_1,
                             json.loads(responses.calls[0].request.body))

            body_2 = json.loads(responses.calls[1].request.body)
            body_2['payload'].pop('duration_s')
            staged_file_path = f"{staging_dir}/{self.upload_area_id}/{self.filename}"
            self.assertEqual(list(body_2.keys()), ['status', 'job_id', 'payload'])
            self.assertEqual(body_2['status'], 'VALIDATED')
            self.assertEqual(body_2['job_id'], '1')
            self.assertEqual(body_2['payload']['validation_id'], self.validation_id)
            self.assertEqual(body_2['payload']['command'], f"/usr/bin/sum {staged_file_path}")
            self.assertEqual(body_2['payload']['exit_code'], 0)
            self.assertEqual(body_2['payload']['status'], 'completed')
            self.assertIn("32883", body_2['payload']['stdout'])  # OS X and Linux /usr/bin/sum output differs
            self.assertEqual(body_2['payload']['stderr'], "")
            self.assertEqual(body_2['payload']['exception'], None)
            self.assertEqual(body_2['payload']['upload_area_id'], self.upload_area_id)
            self.assertEqual(body_2['payload']['names'], [self.filename])
