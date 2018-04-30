#!/usr/bin/env python
"""
This script parses a terraform secrets string with db credentials
"""

import json
import sys


def handler(args):
    secrets_string = args["secret_string"]
    secrets_object = json.loads(secrets_string)
    output = {
        "password": secrets_object["password"],
        "username": secrets_object["username"],
        "db_name": secrets_object["dbname"]
    }
    json.dump(output, sys.stdout)
    exit(0)

if __name__ == '__main__':
    args = json.load(sys.stdin)
    handler(args)