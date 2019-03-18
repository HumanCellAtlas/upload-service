import os

from urllib3.util import parse_url


class FixtureFile:
    """
    FixtureFile is used to provide data and metadata about known files exclusively for testing purposes.
    """

    fixture_files = {}

    @classmethod
    def register(cls, name, contents=None, url=None, checksums=None,
                 content_type='application/octet-stream; dcp-type=data'):
        ff = cls(name, content_type, contents, url, checksums)
        cls.fixture_files[name] = ff

    @classmethod
    def factory(cls, filename):
        return cls.fixture_files[filename]

    def __init__(self, name, content_type, contents=None, url=None, checksums=None):
        self.name = name
        self.content_type = content_type
        self.url = url
        if not contents and not url:
            raise RuntimeError("you must provide either contents or content_url")
        self._contents = contents
        self.contents_url = url
        self.checksums = checksums

    @property
    def size(self):
        if self._contents:
            return len(self._contents)
        else:
            try:
                len(self.contents)
            except Exception:
                raise RuntimeError(
                    f"size() is only available when the file type is of type file (the file inputted is of type "
                    f"{parse_url(self.contents_url).scheme}) or if the contents was set during initialization of the "
                    f"object.")

    @property
    def e_tag(self):
        return self.checksums['s3_etag']

    @property
    def crc32c(self):
        return self.checksums['crc32c']

    @property
    def s3_tagset(self):
        tags = {f"hca-dss-{csum_name}": csum for csum_name, csum in self.checksums.items()}
        tagset = [{'Key': tagname, 'Value': csum} for tagname, csum in tags.items()]
        return sorted(tagset, key=lambda x: x['Key'])

    @property
    def path(self):
        if self.contents_url:
            url = parse_url(self.contents_url)
            if url.scheme == 'file':
                return self.fixture_file_path(self.name)
            elif url.scheme == 's3':
                raise RuntimeError("This file is an S3 file. You probably meant to call .url instead of .path")
            else:
                raise RuntimeError(f"path() not supported for file of type {url.scheme}")

    @property
    def contents(self):
        if self._contents:
            return self._contents
        else:
            url = parse_url(self.contents_url)
            if url.scheme == 'file':
                with open(self.fixture_file_path(self.name)) as f:
                    self._contents = f.read()
                return self._contents
            else:
                raise RuntimeError(f'contents() not supported for URL of type {url.scheme}')

    @staticmethod
    def fixture_file_path(filename):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures', filename))


FixtureFile.register(name="foo",
                     contents="exquisite corpse",
                     checksums={
                         "s3_etag": "18f17fbfdd21cf869d664731e10d4ffd",
                         "sha1": "b1b101e21cf9cf8a4729da44d7818f935eec0ce8",
                         "sha256": "29f5572dfbe07e1db9422a4c84e3f9e455aab9ac596f0bf3340be17841f26f70",
                         "crc32c": "FE9ADA52"
                     })

FixtureFile.register(name='small_file',
                     url='file://small_file',
                     checksums={
                         "s3_etag": "90bb15802d139f86139a6ca72d61611b",
                         "sha1": "1039d0969f1fb147292dedfd9116fb5d447430e1",
                         "sha256": "513ede16ce2c0a32fdbe2b4177356b919bfa40523c1e5919d5ea024a53a07b7a",
                         "crc32c": "00CED75A"
                     })

FixtureFile.register(name='small_invalid_file',
                     url='file://small_invalid_file',
                     checksums={
                         "s3_etag": "98b503a28b4117eae0bdce852598f1ad",
                         "sha1": "3687cdcbdbaca09bf19bdb9323ba8902db8587a5",
                         "sha256": "1e981bfa26ebbb6b4916ad7ce3571705d0bd854d7655a2a9cee3dd6270dcf42b",
                         "crc32c": "81259BFD"
                     })

FixtureFile.register(name='small_invalid_file',
                     url='file://small_invalid_file',
                     checksums={
                         "s3_etag": "945cf6cb1e6d6ad82831bef65997ef64",
                         "sha1": "b41a77c28b3134122ba1f520535ef8c491e15336",
                         "sha256": "d2cf8f92b6a2f66555c7cfe76ed90676fd89a6003f9d1cfa7a1c9375a570d020",
                         "crc32c": "9B0F0C97"
                     })

FixtureFile.register(name='10241MB_file',
                     url='s3://org-humancellatlas-dcp-test-data/upload_service/10241MB_file',
                     checksums={
                         "s3_etag": "db6ab9e24571a6e710acd7a724a32f44-161",
                         "sha1": "667b2330e0fbb7ec838aff4b29fb4f52e708ba89",
                         "sha256": "f9212050708ba0513663538eb98dc2a4687d63821d3956f07fb6db0a4d061027",
                         "crc32c": "68AF9466"
                     })

FixtureFile.register(name='metadata_file.json',
                     contents={'test_obj': 'test_obj'},
                     checksums={
                         "s3_etag": "98b3a7471805e97a493c0e42763abe14",
                         "sha1": "f3c6f383698e3abf90721e9705d99d065708d405",
                         "sha256": "e08097457644aef76b6129423d5f3fcbd800d39d207dbf8491db534c1d93968f",
                         "crc32c": "EA784DAF"
                     })
