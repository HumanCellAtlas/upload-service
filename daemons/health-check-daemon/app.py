from upload.lambdas.health_check.health_check import HealthCheck


def health_check(event, context):
    HealthCheck().run_upload_service_health_check()
