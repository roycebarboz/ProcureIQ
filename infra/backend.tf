terraform {
  backend "azurerm" {
    resource_group_name  = "rg-procureiq-tfstate"
    storage_account_name = "stprocureiqtfstate"
    container_name       = "tfstate"
    key                  = "procureiq.terraform.tfstate"
  }
}
