# Glue crawler turns the FOCUS Parquet files into a table; Athena queries it.
resource "aws_glue_catalog_database" "finops" {
  name = "finops"
}

data "aws_iam_policy_document" "glue_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "crawler" {
  name_prefix        = "${var.name_prefix}-crawler-"
  assume_role_policy = data.aws_iam_policy_document.glue_trust.json
}

resource "aws_iam_role_policy_attachment" "crawler_service" {
  role       = aws_iam_role.crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "crawler_s3" {
  role = aws_iam_role.crawler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.finops.arn, "${aws_s3_bucket.finops.arn}/focus/*"]
    }]
  })
}

resource "aws_glue_crawler" "focus" {
  name          = "${var.name_prefix}-focus"
  database_name = aws_glue_catalog_database.finops.name
  role          = aws_iam_role.crawler.arn
  schedule      = "cron(0 6 * * ? *)" # daily, after the export refreshes
  s3_target {
    path       = "s3://${aws_s3_bucket.finops.bucket}/focus/"
    exclusions = ["**.json", "**.yml", "**.sql", "**.csv.metadata"]
  }
  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }
}

resource "aws_athena_workgroup" "finops" {
  name          = var.name_prefix
  force_destroy = true
  configuration {
    enforce_workgroup_configuration = true
    bytes_scanned_cutoff_per_query  = 1073741824 # 1 GB guardrail per query
    result_configuration {
      output_location = "s3://${aws_s3_bucket.finops.bucket}/athena-results/"
    }
  }
}
