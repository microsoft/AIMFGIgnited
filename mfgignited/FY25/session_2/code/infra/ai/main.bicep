@description('Azure region used for the deployment of all resources.')
param aiServicesName string
param location string = resourceGroup().location
param openAILocation string
param cohereLocation string
param oaiDeploymentName string
param oaimodelName string
param oaiEmbeddingModelName string
param cohereModelName string

@description('Set of tags to apply to all resources.')
param tags object = {}



// Dependent resources for the Azure Machine Learning workspace
module aiDependencies 'modules/cogServices.bicep' = {
  name: 'dependencies-${aiServicesName}-deployment'
  params: {
    oaiDeploymentName: oaiDeploymentName
    oaimodelName: oaimodelName
    location: location
    aiServicesName: aiServicesName
    openAILocation: openAILocation
    oaiEmbeddingModelName: oaiEmbeddingModelName

  }
}

module aiHub 'modules/hub.bicep' = {
  name: 'hub-${aiServicesName}-deployment'
  params: {
    location: cohereLocation
    tags: tags
    aiHubName: '${aiServicesName}-hub'
    aiHubFriendlyName: '${aiServicesName}-hub'
    aiHubDescription: 'AI Hub for ${aiServicesName}'
  }
}

module aiProject 'modules/project.bicep' = {
  name: 'project-${aiServicesName}-deployment'
  params: {
    location: cohereLocation
    hubId: aiHub.outputs.aiHubID
    prefix: '${aiServicesName}-hub'
    cohereModelName: cohereModelName
  }
}

output aiServicesEndpoint string = aiDependencies.outputs.aiservicesTarget
output aiservicesID string = aiDependencies.outputs.aiservicesID
output aiservicesTarget string = aiDependencies.outputs.aiservicesTarget
output embbeddingEndpoint string = aiProject.outputs.cohereServerlessEndpoint
output cohereModelName string = cohereModelName
output openAiTarget string = aiDependencies.outputs.openAiTarget
output oaiDeploymentName string = aiDependencies.outputs.oaiDeploymentName
output openAIModelName string = aiDependencies.outputs.openAIModelName
output openAIEmbeddingModelName string = oaiEmbeddingModelName
output embeddingKey string = aiProject.outputs.cohereServerlessKey
