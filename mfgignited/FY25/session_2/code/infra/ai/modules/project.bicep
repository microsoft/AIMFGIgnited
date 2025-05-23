param prefix string
param location string
param hubId string
param cohereModelName string

var projectName = '${prefix}-aiproject'

resource project 'Microsoft.MachineLearningServices/workspaces@2024-01-01-preview' = {
  name: projectName
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: projectName
    hbiWorkspace: false
    v1LegacyMode: false
    publicNetworkAccess: 'Enabled'
    hubResourceId: hubId
  }
}

resource coheredeploymentMktPlace 'Microsoft.MachineLearningServices/workspaces/marketplaceSubscriptions@2025-01-01-preview' = {
  parent: project
  name: 'Cohere-embed-v3-multili-${guid(prefix)}'
  properties: {
    modelId: 'azureml://registries/azureml-cohere/models/${cohereModelName}'
  }
}


resource coheredeploymentServerless 'Microsoft.MachineLearningServices/workspaces/serverlessEndpoints@2025-01-01-preview' = {
  parent: project
  name: 'CohereEmbed-mlv3-${prefix}'
  location: location
  sku: {
    name: 'Consumption'
    tier: 'Free'
  }
  properties: {
    modelSettings: {
      modelId: 'azureml://registries/azureml-cohere/models/${cohereModelName}'
    }
    authMode: 'Key'
    contentSafety: {
      contentSafetyStatus: 'Enabled'
      contentSafetyLevel: 'Blocking'
    }
  }
}

output cohereServerlessEndpoint string = coheredeploymentServerless.properties.inferenceEndpoint.uri
output cohereServerlessKey string = coheredeploymentServerless.listKeys().primaryKey


