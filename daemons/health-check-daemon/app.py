from upload.common.logging import configure_logger
from upload.lambdas.health_check.health_check import HealthCheck

configure_logger()


def health_check(event, context):
    HealthCheck().run_upload_service_health_check()
