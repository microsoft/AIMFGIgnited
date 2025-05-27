metadata description = 'Creates an Azure AI Search instance.'
param name string
param location string = resourceGroup().location

param sku object = {
  name: 'standard'
}

@allowed([
  'default'
  'highDensity'
])
param hostingMode string = 'default'
@allowed([
  'enabled'
  'disabled'
])
param publicNetworkAccess string = 'enabled'
param partitionCount int = 1
param replicaCount int = 1
@allowed([
  'disabled'
  'free'
  'standard'
])
param semanticSearch string = 'free'

var searchIdentityProvider = {
  type: 'SystemAssigned'
}

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: name
  location: location
  identity: searchIdentityProvider
  properties: {
    disableLocalAuth: true
    hostingMode: hostingMode
    partitionCount: partitionCount
    publicNetworkAccess: publicNetworkAccess
    replicaCount: replicaCount
    semanticSearch: semanticSearch
  }
  sku: sku
}

output id string = search.id
output endpoint string = 'https://${name}.search.windows.net/'
output name string = search.name
output principalId string = !empty(searchIdentityProvider) ? search.identity.principalId : ''
