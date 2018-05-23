import os

FIXTURE_DATA_CHECKSUMS = {
    'exquisite corpse': {
        'checksums': {
            "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
            "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
            "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70",
            "crc32c": "FE9ADA52"
        },
        's3_tagset': [
            {'Key': "hca-dss-s3_etag", 'Value': "18f17fbfdd21cf869d664731e10d4ffd"},
            {'Key': "hca-dss-sha1", 'Value': "b1b101e21cf9cf8a4729da44d7818f935eec0ce8"},
            {'Key': "hca-dss-sha256", 'Value': "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70"},
            {'Key': "hca-dss-crc32c", 'Value': "FE9ADA52"}
        ]
    }
}


def fixture_file_path(filename):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', filename))
