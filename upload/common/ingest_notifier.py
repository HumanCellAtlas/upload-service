import json
import os
import uuid
import requests
import jwt
import time
import base64

from tenacity import retry, stop_after_attempt, wait_fixed

from .exceptions import UploadException
from .logging import get_logger
from .database import UploadDB
from .upload_config import UploadConfig, UploadAuthConfig

logger = get_logger(__name__)


class IngestNotifier:

    FILE_UPLOADED_ENDPOINT = "messaging/fileUploadInfo"
    FILE_VALIDATED_ENDPOINT = "messaging/fileValidationResult"

    def __init__(self, notification_type):
        self.upload_config = UploadConfig()
        self.auth_config = UploadAuthConfig()
        if notification_type == "file_uploaded":
            self.ingest_notification_url = f"https://{self.ingest_api_host}/{self.FILE_UPLOADED_ENDPOINT}"
        elif notification_type == "file_validated":
            self.ingest_notification_url = f"https://{self.ingest_api_host}/{self.FILE_VALIDATED_ENDPOINT}"
        else:
            raise Exception("Unknown notification type for ingest")
        self.db = UploadDB()

    @property
    def ingest_api_host(self):
        return self.upload_config.ingest_api_host

    @property
    def auth_audience(self):
        return self.auth_config.auth_audience

    @property
    def service_credentials(self):
        encoded_creds = self.auth_config.service_credentials
        return json.loads(base64.b64decode(encoded_creds).decode())

    def format_and_send_notification(self, payload):
        self._validate_payload(payload)
        notification_id = str(uuid.uuid4())
        self._create_or_update_db_notification(notification_id, "DELIVERING", payload)
        body = json.dumps(payload)
        self._send_notification(notification_id, body)
        self._create_or_update_db_notification(notification_id, "DELIVERED", payload)
        return notification_id

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def _send_notification(self, notification_id, body):
        jwt_token = self.get_service_jwt()
        headers = {'Authorization': f"Bearer {jwt_token}"}
        response = requests.post(self.ingest_notification_url, headers=headers, json=body)
        if not response.status_code == requests.codes.accepted:
            self._create_or_update_db_notification(notification_id, "FAILED", json.loads(body))
            raise UploadException(status=response.status_code,
                                  title=f"Failed Notification",
                                  detail=f"Notification {body} failed to post")

    def get_service_jwt(self):
        # This function is taken directly from auth best practice docs in hca gitlab
        iat = time.time()
        exp = iat + 3600
        payload = {'iss': self.service_credentials["client_email"],
                   'sub': self.service_credentials["client_email"],
                   'aud': self.auth_audience,
                   'iat': iat,
                   'exp': exp,
                   'https://auth.data.humancellatlas.org/email': self.service_credentials["client_email"],
                   'https://auth.data.humancellatlas.org/group': 'hca',
                   'scope': ["openid", "email", "offline_access"]
                   }
        additional_headers = {'kid': self.service_credentials["private_key_id"]}
        signed_jwt = jwt.encode(payload, self.service_credentials["private_key"], headers=additional_headers,
                                algorithm='RS256').decode()
        return signed_jwt

    def _create_or_update_db_notification(self, notification_id, status, payload):
        notification_props = self._format_notification_props(notification_id, status, payload)
        if self.db.get_pg_record("notification", notification_id):
            self.db.update_pg_record("notification", notification_props)
        else:
            self.db.create_pg_record("notification", notification_props)

    def _format_notification_props(self, notification_id, status, payload):
        upload_area_id = payload["upload_area_id"]
        file_name = payload["name"]
        notification_props = {
            "id": notification_id,
            "file_id": f"{upload_area_id}/{file_name}",
            "payload": payload,
            "status": status
        }
        return notification_props

    def _validate_payload(self, payload):
        assert type(payload) is dict, "payload is not dict"
        assert payload.get("upload_area_id") is not None, "upload_area_id is not in payload"
        assert payload.get("name") is not None, "name is not in payload"
