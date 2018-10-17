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
    },
    'small_file': {
        'checksums': {
            "s3_etag": "d44dbb8da5d736652e7b53e7482f2ecc",
            "sha1": "e5e331f8bc6347607cf69ea242982f483ab53523",
            "sha256": "7830bee1d57cb253d2aefc4e117e2ddcb056d523d92c164611a5bffe25b0444b",
            "crc32c": "C80D954E"
        },
        's3_tagset': [
            {'Key': "hca-dss-s3_etag", 'Value': "d44dbb8da5d736652e7b53e7482f2ecc"},
            {'Key': "hca-dss-sha1", 'Value': "e5e331f8bc6347607cf69ea242982f483ab53523"},
            {'Key': "hca-dss-sha256", 'Value': "7830bee1d57cb253d2aefc4e117e2ddcb056d523d92c164611a5bffe25b0444b"},
            {'Key': "hca-dss-crc32c", 'Value': "C80D954E"}
        ]
    },
    '10241MB_file': {
        'checksums': {
            "s3_etag": "db6ab9e24571a6e710acd7a724a32f44-161",
            "sha1": "667b2330e0fbb7ec838aff4b29fb4f52e708ba89",
            "sha256": "f9212050708ba0513663538eb98dc2a4687d63821d3956f07fb6db0a4d061027",
            "crc32c": "68AF9466"
        },
        's3_tagset': [
            {'Key': "hca-dss-s3_etag", 'Value': "db6ab9e24571a6e710acd7a724a32f44-161"},
            {'Key': "hca-dss-sha1", 'Value': "667b2330e0fbb7ec838aff4b29fb4f52e708ba89"},
            {'Key': "hca-dss-sha256", 'Value': "f9212050708ba0513663538eb98dc2a4687d63821d3956f07fb6db0a4d061027"},
            {'Key': "hca-dss-crc32c", 'Value': "68AF9466"}
        ]
    }
}


def fixture_file_path(filename):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', filename))
