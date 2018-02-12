import base64
import json
import os
import random
import subprocess
import sys

import requests


class UploadAreaURN:

    def __init__(self, urn):
        self.urn = urn
        urnbits = urn.split(':')
        assert urnbits[0:3] == ['dcp', 'upl', 'aws'], "URN does not start with 'dcp:upl:aws': %s" % (urn,)
        if len(urnbits) == 5:  # production URN dcp:upl:aws:uuid:creds
            self.deployment_stage = 'prod'
            self.uuid = urnbits[3]
            self.encoded_credentials = urnbits[4]
        elif len(urnbits) == 6:  # non-production URN dcp:upl:aws:stage:uuid:creds
            self.deployment_stage = urnbits[3]
            self.uuid = urnbits[4]
            self.encoded_credentials = urnbits[5]
        else:
            raise RuntimeError("Bad URN: %s" % (urn,))

    def __repr__(self):
        return ":".join(['dcp', 'upl', 'aws', self.deployment_stage, self.uuid])

    @property
    def credentials(self):
        uppercase_credentials = json.loads(base64.b64decode(self.encoded_credentials).decode('ascii'))
        return {k.lower(): v for k, v in uppercase_credentials.items()}


class RestApiTest:

    def __init__(self, verbose=False, pause=False, uuid=None):
        self.verbose = verbose
        self.pause = pause
        self.api_url = f"https://{os.environ['API_HOST']}/v1"
        self.auth_headers = {'Api-Key': os.environ['INGEST_API_KEY']}
        self.upload_area_id = uuid or "deadbeef-dead-dead-dead-%12d" % random.randint(0, 999999999999)

    def run(self):
        response = self._create_upload_area()
        urn = UploadAreaURN(response['urn'])
        self._run("SELECT UPLOAD AREA", ['hca', 'upload', 'select', urn.urn])
        self._run("UPLOAD FILE USING CLI", ['hca', 'upload', 'file', 'LICENSE'])
        self._put_file()
        self._list_files()
        self._get_file_info()
        self._get_files_info()
        self._lock_upload_area()
        self._run("UPLOAD FILE USING CLI (should fail)", ['hca', 'upload', 'file', 'LICENSE'], expected_returncode=1)
        self._unlock_upload_area()
        self._run("UPLOAD FILE USING CLI", ['hca', 'upload', 'file', 'LICENSE'])
        self._delete_upload_area()
        self._run("FORGET UPLOAD AREA", ['hca', 'upload', 'forget', urn.uuid])

    def _create_upload_area(self):
        response = self._make_request(description="CREATE UPLOAD AREA",
                                      verb='POST',
                                      url=f"{self.api_url}/area/{self.upload_area_id}",
                                      headers=self.auth_headers,
                                      expected_status=201)
        return json.loads(response)

    def _delete_upload_area(self):
        self._make_request(description="DELETE UPLOAD AREA",
                           verb='DELETE',
                           url=f"{self.api_url}/area/{self.upload_area_id}",
                           headers=self.auth_headers,
                           expected_status=204)

    def _put_file(self):
        headers = self.auth_headers.copy()
        headers.update({'Content-type': 'application/json; dcp-type="metadata/foo"'})
        self._make_request(description="PUT FILE VIA API",
                           verb='PUT',
                           url=f"{self.api_url}/area/{self.upload_area_id}/foobar.json",
                           headers=headers,
                           data={'some': 'json'},
                           expected_status=201)

    def _list_files(self):
        self._make_request(description="LIST FILES",
                           verb='GET',
                           url=f"{self.api_url}/area/{self.upload_area_id}",
                           expected_status=200)

    def _get_file_info(self):
        self._make_request(description="GET FILE INFO",
                           verb='GET',
                           url=f"{self.api_url}/area/{self.upload_area_id}/LICENSE",
                           expected_status=200)

    def _get_files_info(self):
        self._make_request(description="GET FILES INFO",
                           verb='PUT',
                           url=f"{self.api_url}/area/{self.upload_area_id}/files_info",
                           data=json.dumps(['LICENSE', 'foobar.json']),
                           expected_status=200)

    def _lock_upload_area(self):
        self._make_request(description="LOCK UPLOAD AREA",
                           verb='POST',
                           url=f"{self.api_url}/area/{self.upload_area_id}/lock",
                           headers=self.auth_headers,
                           expected_status=204)

    def _unlock_upload_area(self):
        self._make_request(description="UNLOCK UPLOAD AREA",
                           verb='DELETE',
                           url=f"{self.api_url}/area/{self.upload_area_id}/lock",
                           headers=self.auth_headers,
                           expected_status=204)

    def _make_request(self, description, verb, url, expected_status, **options):
        self._say(description + ": ")
        self._say(f"\n\t{verb.upper()} {url}\n", only_when_verbose=True)

        method = getattr(requests, verb.lower())
        response = method(url, **options)

        self._say(f" -> {response.status_code} ")
        if response.status_code == expected_status:
            self._say("✔︎\n")
        else:
            self._say("✘\n")
            print(response.content)

        if response.content:
            self._say(response.content.decode('utf8'), only_when_verbose=True)

        self._pause()

        return response.content

    def _run(self, description, command, expected_returncode=0):
        self._say(description + ": ")
        self._say(f"\n\t{' '.join(command)}\n", only_when_verbose=True)
        completed_process = subprocess.run(command,
                                           stdout=None if self.verbose else subprocess.PIPE,
                                           stderr=None if self.verbose else subprocess.PIPE)
        if completed_process.returncode == expected_returncode:
            self._say("✔︎\n")
        else:
            self._say(f"{completed_process.returncode} ✘\n" +
                      completed_process.stdout.decode('utf8') +
                      completed_process.stderr.decode('utf8'))
        self._pause()

    def _pause(self):
        if self.pause:
            input("Press enter to continue...")

    def _say(self, message, only_when_verbose=False):
        if not only_when_verbose or (only_when_verbose and self.verbose):
            sys.stdout.write(message)
            sys.stdout.flush()
