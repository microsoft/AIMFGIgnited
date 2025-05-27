@description('The name of the storage account.')
param storageAccountName string

@description('The location for the storage account.')
param location string

@description('The SKU of the storage account.')
param skuName string = 'Standard_LRS'

@description('Tags to apply to the storage account.')
param tags object = {}

param allowedAppOrigin string

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: skuName
  }
  kind: 'StorageV2'
  properties: {
    allowSharedKeyAccess: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
      defaultAction: 'Allow'
    }
  }
  tags: tags
}

resource bloblservices 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: [
        {
          allowedOrigins: [
            '*'
          ]
          allowedMethods: [
            'GET'
            'POST'
          ]
          maxAgeInSeconds: 0
          exposedHeaders: [
            ''
          ]
          allowedHeaders: [
            ''
          ]
        }
      ]
    }
    deleteRetentionPolicy: {
      allowPermanentDelete: false
      enabled: false
    }
  }
}

output accountId string = storageAccount.id
output accountName string = storageAccount.name
output accountPrimaryEndpoints object = storageAccount.properties.primaryEndpoints
