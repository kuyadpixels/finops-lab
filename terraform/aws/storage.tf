# Bucket that receives the FOCUS data export, Athena results and waste reports.
resource "aws_s3_bucket" "finops" {
  bucket_prefix = "${var.name_prefix}-"
  force_destroy = true # lab only: lets `terraform destroy` remove exported data
}

resource "aws_s3_bucket_public_access_block" "finops" {
  bucket                  = aws_s3_bucket.finops.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "finops" {
  bucket = aws_s3_bucket.finops.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "finops" {
  bucket = aws_s3_bucket.finops.id
  rule {
    id     = "expire-athena-results"
    status = "Enabled"
    filter { prefix = "athena-results/" }
    expiration { days = 7 }
  }
}

# Lets AWS Data Exports (and legacy CUR) write into the bucket.
# The export itself is created in the console (see docs/setup.md, step 2).
data "aws_iam_policy_document" "exports" {
  statement {
    sid     = "AllowBillingExports"
    effect  = "Allow"
    actions = ["s3:PutObject", "s3:GetBucketPolicy"]
    principals {
      type        = "Service"
      identifiers = ["bcm-data-exports.amazonaws.com", "billingreports.amazonaws.com"]
    }
    resources = [aws_s3_bucket.finops.arn, "${aws_s3_bucket.finops.arn}/*"]
    condition {
      test     = "StringLike"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.me.account_id]
    }
    condition {
      test     = "StringLike"
      variable = "aws:SourceArn"
      values = [
        "arn:aws:cur:us-east-1:${data.aws_caller_identity.me.account_id}:definition/*",
        "arn:aws:bcm-data-exports:us-east-1:${data.aws_caller_identity.me.account_id}:export/*",
      ]
    }
  }
}

resource "aws_s3_bucket_policy" "finops" {
  bucket     = aws_s3_bucket.finops.id
  policy     = data.aws_iam_policy_document.exports.json
  depends_on = [aws_s3_bucket_public_access_block.finops]
}
