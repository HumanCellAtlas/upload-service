#!/usr/bin/env python

"""
Staging service
"""

import logging

import flask
import connexion
from connexion.resolver import RestyResolver
from flask_failsafe import failsafe


def get_logger():
    try:
        return flask.current_app.logger
    except RuntimeError:
        return logging.getLogger(__name__)

@failsafe
def create_app():
    app = connexion.App(__name__)
    resolver = RestyResolver("staging.api", collection_endpoint_name="list")
    app.add_api('../staging-api.yml', resolver=resolver, validate_responses=True)
    return app
