// Creates Azure dependent resources for Azure AI Foundry

@description('Azure region of the deployment')
param location string = resourceGroup().location
param openAILocation string

@description('AI services name')
param aiServicesName string

param oaimodelName string
param oaiDeploymentName string
param oaiEmbeddingModelName string

resource aiServices 'Microsoft.CognitiveServices/accounts@2021-10-01' = {
  name: aiServicesName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'CognitiveServices'
  properties: {
    apiProperties: {
      statisticsEnabled: false
    }
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'

  }
}

resource openAi 'Microsoft.CognitiveServices/accounts@2021-10-01' = {
  name: 'openai-${aiServicesName}'
  location: openAILocation
  sku: {
    name: 'S0'
  }
  
  kind: 'OpenAI'
  properties: {
    apiProperties: {
      statisticsEnabled: false
    }
    customSubDomainName: '${aiServicesName}-openai'
    publicNetworkAccess: 'Enabled'
  }
}

resource oaideployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: oaiDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: oaimodelName
      version: '2024-11-20'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    currentCapacity: 50
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource oai_embedding_deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: openAi
  name: oaiEmbeddingModelName
  dependsOn: [
    oaideployment
  ]
  sku: {
    name: 'GlobalStandard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: oaiEmbeddingModelName
      version: '1'
    }
    versionUpgradeOption: 'NoAutoUpgrade'
    currentCapacity: 50
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

output aiservicesID string = aiServices.id
output aiservicesTarget string = 'https://${aiServicesName}.cognitiveservices.azure.com'
output openAiTarget string = openAi.properties.endpoint
output openAIModelName string = oaimodelName
output oaiDeploymentName string = oaiDeploymentName
