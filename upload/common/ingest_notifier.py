import base64
import json
import time
import uuid

import requests
from jwt import encode

from .database import UploadDB
from .logging import get_logger
from .upload_config import UploadConfig, UploadOutgoingIngestAuthConfig

logger = get_logger(__name__)


class IngestNotifier:
    INGEST_ENDPOINTS = {"file_uploaded": "messaging/fileUploadInfo",
                        "file_validated": "messaging/fileValidationResult"}

    def __init__(self, notification_type, file_id):
        self.upload_config = UploadConfig()
        self.file_id = file_id
        self.outgoing_ingest_auth_config = UploadOutgoingIngestAuthConfig()
        self.ingest_notification_url = f"https://{self.ingest_api_host}/{self.INGEST_ENDPOINTS[notification_type]}"
        self.db = UploadDB()

    @property
    def ingest_api_host(self):
        return self.upload_config.ingest_api_host

    @property
    def dcp_auth0_audience(self):
        return self.outgoing_ingest_auth_config.dcp_auth0_audience

    @property
    def gcp_service_acct_creds(self):
        encoded_creds = self.outgoing_ingest_auth_config.gcp_service_acct_creds
        return json.loads(base64.b64decode(encoded_creds).decode())

    def format_and_send_notification(self, payload):
        self._validate_payload(payload)

        if self._is_dev_upload_area(payload):
            logger.info(f"Skipping sending notification for area {payload.get('upload_area_id')} because it was "
                        f"identified as a development upload area.")
            return None

        notification_id = str(uuid.uuid4())
        self._create_or_update_db_notification(notification_id, "DELIVERING", payload)
        notification_successful = False
        attempts = 0
        while not notification_successful and attempts < 15:
            attempts += 1
            if self._send_notification(notification_id, payload):
                self._create_or_update_db_notification(notification_id, "DELIVERED", payload)
                notification_successful = True
            else:
                time.sleep(2)
        if not notification_successful:
            self._create_or_update_db_notification(notification_id, "FAILED", payload)
        return notification_id

    def _send_notification(self, notification_id, payload):
        try:
            logger.info(f"attempting notification_id:{notification_id}, payload:{payload}, \
                          url:{self.ingest_notification_url}")
            jwt_token = self.get_service_jwt()
            headers = {'Authorization': f"Bearer {jwt_token}"}
            response = requests.post(self.ingest_notification_url, headers=headers, json=payload)
            if not response.status_code == requests.codes.ok:
                logger.info(f"failed to send notification_id:{notification_id}, payload:{payload}, \
                              response:{str(response.json())}, url:{self.ingest_notification_url}")
                return None
            else:
                logger.info(f"successfully sent notification_id:{notification_id}, payload:{payload}, \
                          url:{self.ingest_notification_url}")
                return True
        except Exception as e:
            logger.info(f"failed to send notification {notification_id} with payload {payload} and error {str(e)}")
            return None

    def get_service_jwt(self):
        # This function is taken directly from auth best practice docs in hca gitlab
        # https://allspark.dev.data.humancellatlas.org/dcp-ops/docs/wikis/Security/Authentication%20and
        # %20Authorization/Setting%20up%20DCP%20Auth
        iat = time.time()
        exp = iat + 3600
        payload = {'iss': self.gcp_service_acct_creds["client_email"],
                   'sub': self.gcp_service_acct_creds["client_email"],
                   'aud': self.dcp_auth0_audience,
                   'iat': iat,
                   'exp': exp,
                   'https://auth.data.humancellatlas.org/email': self.gcp_service_acct_creds["client_email"],
                   'https://auth.data.humancellatlas.org/group': 'hca',
                   'scope': ["openid", "email", "offline_access"]
                   }
        additional_headers = {'kid': self.gcp_service_acct_creds["private_key_id"]}
        signed_jwt = encode(payload, self.gcp_service_acct_creds["private_key"],
                            headers=additional_headers, algorithm='RS256').decode()
        return signed_jwt

    def _create_or_update_db_notification(self, notification_id, status, payload):
        notification_props = self._format_notification_props(notification_id, status, payload)
        if self.db.get_pg_record("notification", notification_id):
            self.db.update_pg_record("notification", notification_props)
        else:
            self.db.create_pg_record("notification", notification_props)

    def _format_notification_props(self, notification_id, status, payload):
        notification_props = {
            "id": notification_id,
            "file_id": self.file_id,
            "payload": payload,
            "status": status
        }
        return notification_props

    def _is_dev_upload_area(self, payload):
        if payload.get("upload_area_id").startswith("deadbeef"):
            return True
        return False

    def _validate_payload(self, payload):
        """ Validates the payload by making sure that the payload is of a dictionary structure and contains an
        upload_area_id."""
        assert type(payload) is dict, "payload is not dict"
        assert payload.get("upload_area_id") is not None, "upload_area_id is not in payload"
