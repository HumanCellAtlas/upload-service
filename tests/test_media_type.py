#!/usr/bin/env python3.6

import os
import sys
import unittest

if __name__ == '__main__':  # noqa
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # noqa
    sys.path.insert(0, pkg_root)  # noqa

from upload.media_type import MediaType


class TestMediaType(unittest.TestCase):

    TEST_VALUES = {
        'application/json': {
            'top_level_type': 'application', 'subtype': 'json'
        },
        'application/json+zip': {
            'top_level_type': 'application', 'subtype': 'json', 'suffix': '+zip',
        },
        'application/octet-stream+zip; dcp-type=data': {
            'top_level_type': 'application', 'subtype': 'octet-stream',
            'suffix': '+zip', 'parameters': {'dcp-type': 'data'}
        },
        'application/json; dcp-type="metadata/sample"': {
            'top_level_type': 'application', 'subtype': 'json', 'parameters': {'dcp-type': 'metadata/sample'}
        }
    }

    def test_string_generation(self):
        for media_type, attributes in self.TEST_VALUES.items():
            mt = MediaType(**attributes)
            self.assertEqual(media_type, str(mt))

    def test_string_parsing(self):
        for media_type, attributes in self.TEST_VALUES.items():
            mt = MediaType.from_string(media_type)
            self.assertEqual(attributes['top_level_type'], mt.top_level_type)
            self.assertEqual(attributes['subtype'], mt.subtype)
            if 'suffix' in attributes:
                self.assertEqual(attributes['suffix'], mt.suffix)
            if 'parameters' in attributes:
                self.assertEqual(attributes['parameters'], mt.parameters)


if __name__ == '__main__':
    unittest.main()
