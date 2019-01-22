import os

from urllib3.util import parse_url


class FixtureFile:

    """
    FixtureFile is used to provide data and metadata about known files for testing purposes.
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
            raise RuntimeError('size() is only implemented when contents is provided')

    @property
    def e_tag(self):
        return self.checksums['s3_etag']

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
            else:
                raise RuntimeError(f"path() not supported for file of type {url.scheme}")

    @property
    def contents(self):
        if self._contents:
            return self._contents
        else:
            url = parse_url(self.contents_url)
            if url.scheme == 'file':
                with open(self.fixture_file_path(url.path)) as f:
                    return f.read()
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
                         "s3_etag": "d44dbb8da5d736652e7b53e7482f2ecc",
                         "sha1": "e5e331f8bc6347607cf69ea242982f483ab53523",
                         "sha256": "7830bee1d57cb253d2aefc4e117e2ddcb056d523d92c164611a5bffe25b0444b",
                         "crc32c": "C80D954E"
                     })

FixtureFile.register(name='10241MB_file',
                     url='s3://org-humancellatlas-dcp-test-data/upload_service/10241MB_file',
                     checksums={
                         "s3_etag": "db6ab9e24571a6e710acd7a724a32f44-161",
                         "sha1": "667b2330e0fbb7ec838aff4b29fb4f52e708ba89",
                         "sha256": "f9212050708ba0513663538eb98dc2a4687d63821d3956f07fb6db0a4d061027",
                         "crc32c": "68AF9466"
                     })
