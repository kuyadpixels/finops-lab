# Azure side of the tagging taxonomy: require the same tags on every resource group,
# and let resources inherit them from their resource group (so cost rolls up cleanly).
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" { type = string }

variable "required_tags" {
  type    = list(string)
  default = ["CostCenter", "Environment", "Owner"]
}

data "azurerm_subscription" "current" {}

data "azurerm_policy_definition" "require_rg_tag" {
  display_name = "Require a tag on resource groups"
}

data "azurerm_policy_definition" "inherit_rg_tag" {
  display_name = "Inherit a tag from the resource group if missing"
}

resource "azurerm_subscription_policy_assignment" "require" {
  for_each             = toset(var.required_tags)
  name                 = "require-rg-tag-${lower(each.key)}"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = data.azurerm_policy_definition.require_rg_tag.id
  parameters           = jsonencode({ tagName = { value = each.key } })
}

# Modify-effect policies need a managed identity to add the missing tag.
resource "azurerm_subscription_policy_assignment" "inherit" {
  for_each             = toset(var.required_tags)
  name                 = "inherit-rg-tag-${lower(each.key)}"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = data.azurerm_policy_definition.inherit_rg_tag.id
  parameters           = jsonencode({ tagName = { value = each.key } })
  location             = "southeastasia"
  identity { type = "SystemAssigned" }
}

resource "azurerm_role_assignment" "inherit_tag_contributor" {
  for_each             = azurerm_subscription_policy_assignment.inherit
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Tag Contributor"
  principal_id         = each.value.identity[0].principal_id
}
