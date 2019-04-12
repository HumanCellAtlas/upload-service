data "aws_route53_zone" "deployment_stage" {
  name = "${var.parent_zone_domain_name}."
}

data "aws_acm_certificate" "deployment_stage" {
  domain   = "*.${var.parent_zone_domain_name}"
  statuses = ["ISSUED"]
  types = ["AMAZON_ISSUED"]
  most_recent = true
}

resource "aws_api_gateway_domain_name" "upload" {
  certificate_arn = "${data.aws_acm_certificate.deployment_stage.arn}"
  domain_name     = "${var.upload_api_fqdn}"

  endpoint_configuration {
    types = ["EDGE"]
  }
}

data "external" "api_gateway" {
  program = ["${path.cwd}/../../../scripts/get_api_id", "--json"]

  query = {
    api_gateway_name = "upload.lambdas.api_server"
    lambda_name = "${aws_lambda_function.upload_api_lambda.function_name}"
  }
}

resource "aws_route53_record" "upload" {
  name    = "${aws_api_gateway_domain_name.upload.domain_name}"
  type    = "A"
  zone_id = "${data.aws_route53_zone.deployment_stage.id}"

  alias {
    evaluate_target_health = false
    name                   = "${aws_api_gateway_domain_name.upload.cloudfront_domain_name}"
    zone_id                = "${aws_api_gateway_domain_name.upload.cloudfront_zone_id}"
  }
}

resource "aws_api_gateway_base_path_mapping" "status_api" {
  api_id      = "${lookup(data.external.api_gateway.result, "api_id")}"
  stage_name  = "${var.deployment_stage}"
  domain_name = "${aws_api_gateway_domain_name.upload.domain_name}"
}
