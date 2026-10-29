# Setup on a real AWS account

1. **Deploy the stack**
   ```bash
   cd terraform/aws
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform apply
   ```
   Confirm the SNS subscription email that arrives.

2. **Create the FOCUS export (console, management/payer account)**
   Billing and Cost Management → Data Exports → Create.
   - Export type: **FOCUS 1.0 with AWS columns**
   - Format: Parquet, overwrite existing files
   - S3 bucket: the `bucket` output from Terraform, path prefix `focus`

   The first data arrives within about 24 hours. Older months need a backfill request to AWS Support.

3. **Build the table**: after data lands, run the Glue crawler once (`glue_crawler` output) or wait for the daily schedule.

4. **Query**: open Athena, pick the `finops-lab` workgroup, run `sql/athena/00_check_schema.sql` first, adjust the table name and tag-key format, then run the other queries.

5. **Tagging**: activate `CostCenter`, `Environment` and `Owner` as **cost allocation tags** in Billing. Tags only appear in billing data from the day you activate them.

6. **Waste finder**: it runs every Monday 09:00 MYT in dry-run mode and emails a summary. To let it clean up, tag a resource `finops:cleanup=approved` and set `dry_run = false`.

7. **Azure (optional)**
   ```bash
   cd terraform/azure
   terraform init
   terraform apply -var subscription_id=<your-subscription-id>
   ```
   Run `azure/orphaned_resources.kql` in Resource Graph Explorer.

8. **Tear down**: `terraform destroy` in each folder. Delete the Data Export in the console.
