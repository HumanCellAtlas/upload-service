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
    '4097MB_file': {
        'checksums': {
            "s3_etag": "d87ac6ddedb0d2befaeb43d88738aae1-65",
            "sha1": "77fbc4153b43e90d872c83aef8614bf06ddd577b",
            "sha256": "c99de3d018e7bfbb81b8e1fd1c3c581b364abe03fb42440a115fbbcbef3c85d2",
            "crc32c": "5215CEF6"
        },
        's3_tagset': [
            {'Key': "hca-dss-s3_etag", 'Value': "d87ac6ddedb0d2befaeb43d88738aae1-65"},
            {'Key': "hca-dss-sha1", 'Value': "77fbc4153b43e90d872c83aef8614bf06ddd577b"},
            {'Key': "hca-dss-sha256", 'Value': "c99de3d018e7bfbb81b8e1fd1c3c581b364abe03fb42440a115fbbcbef3c85d2"},
            {'Key': "hca-dss-crc32c", 'Value': "5215CEF6"}
        ]
    }
}


def fixture_file_path(filename):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', filename))
