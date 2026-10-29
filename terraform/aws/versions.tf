terraform {
  required_version = ">= 1.6"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.60" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "finops-lab"
      CostCenter  = "platform"
      Environment = "lab"
      Owner       = var.owner
    }
  }
}

data "aws_caller_identity" "me" {}
