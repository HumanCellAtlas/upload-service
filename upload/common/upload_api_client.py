import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

url = os.environ["API_HOST"]
api_version = "v1"
header = {'Content-type': 'application/json'}


def update_event(event, payload, client=requests):
    event_type = type(event).__name__
    if event_type == "ValidationEvent":
        action = 'update_validation'
    elif event_type == "ChecksumEvent":
        action = 'update_checksum'

    data = {"status": event.status,
            "job_id": event.job_id,
            "payload": payload
            }
    upload_area_uuid = payload["upload_area_id"]
    event_id = event.id
    api_url = f"https://{url}/{api_version}/area/{upload_area_uuid}/{action}/{event_id}"
    logger.debug(f"update_event: sending to {api_url}: {data}")
    response = client.post(api_url, headers=header, data=json.dumps(data))
    return response
