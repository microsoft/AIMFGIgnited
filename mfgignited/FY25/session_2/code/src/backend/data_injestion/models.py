from azure.search.documents.indexes.aio import SearchIndexClient, SearchIndexerClient
from azure.storage.blob.aio import BlobServiceClient


class ProcessRequest:
    def __init__(
        self,
        indexName: str,
        blobSource: str,
        knowledgeStoreContainer: str,
        localDataSource: str,
        blobServiceClient: BlobServiceClient,
        indexClient: SearchIndexClient,
        indexerClient: SearchIndexerClient,
        chatCompletionEndpoint: str,
        chatCompletionModel: str,
        chatCompletionDeployment: str,
        aoaiEmbeddingEndpoint: str,
        aoaiEmbeddingDeployment: str,
        aoaiEmbeddingModel: str,
        cognitiveServicesEndpoint: str,
        subscriptionId: str,
        resourceGroup: str,
    ):
        self.indexName = indexName
        self.blobSource = blobSource
        self.knowledgeStoreContainer = knowledgeStoreContainer
        self.localDataSource = localDataSource
        self.blobServiceClient = blobServiceClient
        self.indexClient = indexClient
        self.indexerClient = indexerClient
        self.chatCompletionEndpoint = chatCompletionEndpoint
        self.chatCompletionModel = chatCompletionModel
        self.chatCompletionDeployment = chatCompletionDeployment
        self.aoaiEmbeddingEndpoint = aoaiEmbeddingEndpoint
        self.aoaiEmbeddingDeployment = aoaiEmbeddingDeployment
        self.aoaiEmbeddingModel = aoaiEmbeddingModel
        self.cognitiveServicesEndpoint = cognitiveServicesEndpoint
        self.subscriptionId = subscriptionId
        self.resourceGroup = resourceGroup
