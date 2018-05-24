resource "aws_ecs_task_definition" "pgbouncer" {
  family                = "pgbouncer-service-${var.deployment_stage}"
  requires_compatibilities = ["FARGATE"]
  container_definitions = <<DEFINITION
[
  {
    "portMappings": [
      {
        "hostPort": 5432,
        "protocol": "tcp",
        "containerPort": 5432
      }
    ],
    "environment": [
      {
        "name": "DATABASE_URL",
        "value": "postgresql://${var.db_username}:${var.db_password}@${aws_rds_cluster.upload.endpoint}/upload_${var.deployment_stage}"
      },
      {
        "name": "DEFAULT_POOL_SIZE",
        "value": "20"
      },
      {
        "name": "MAX_CLIENT_CONN",
        "value": "2000"
      },
      {
        "name": "POOL_MODE",
        "value": "transaction"
      }
    ],
    "memory": 1024,
    "cpu": 512,
    "image": "quay.io/humancellatlas/docker-pgbouncer:master",
    "name": "pgbouncer-${var.deployment_stage}"
  }
]
DEFINITION
  network_mode          = "awsvpc"
  cpu                   = "512"
  memory                = "1024"
}

resource "aws_ecs_cluster" "pgbouncer" {
  name = "pgbouncer-${var.deployment_stage}"
}

resource "aws_ecs_service" "pgbouncer" {
  name            = "pgbouncer-${var.deployment_stage}"
  cluster         = "${aws_ecs_cluster.pgbouncer.id}"
  task_definition = "${aws_ecs_task_definition.pgbouncer.arn}"
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    security_groups = ["${var.vpc_rds_security_group_id}"]
    subnets         = ["${var.subnet_id}"]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = "${aws_lb_target_group.pgbouncer.id}"
    container_name   = "pgbouncer-${var.deployment_stage}"
    container_port   = "5432"
  }

  depends_on = [
    "aws_lb_listener.front_end",
  ]
}

resource "aws_lb_listener" "front_end" {
  load_balancer_arn = "${aws_lb.main.id}"
  port              = "5432"
  protocol          = "TCP"

  default_action {
    target_group_arn = "${aws_lb_target_group.pgbouncer.id}"
    type             = "forward"
  }

}

resource "aws_lb" "main" {
  name            = "pgbouncer-${var.deployment_stage}"
  subnets         = ["${var.subnet_ids}"]
  load_balancer_type = "network"
  internal           = false
}

resource "aws_lb_target_group" "pgbouncer" {
  name        = "pgbouncer-${var.deployment_stage}"
  port        = "5432"
  protocol    = "TCP"
  vpc_id      = "${var.vpc_id}"
  target_type = "ip"
}