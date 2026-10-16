terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Remote state. Bootstrap once (manual): RG `ai-rag-tfstate` + storage `stragstaterl01` + container `tfstate`.
  backend "azurerm" {
    resource_group_name  = "ai-rag-tfstate"
    storage_account_name = "stragstaterl01"
    container_name       = "tfstate"
    key                  = "ai-rag/terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

data "azurerm_client_config" "current" {}
