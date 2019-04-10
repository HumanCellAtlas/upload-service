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
