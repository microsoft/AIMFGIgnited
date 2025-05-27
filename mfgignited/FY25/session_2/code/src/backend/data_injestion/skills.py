from datetime import timedelta
from azure.search.documents.indexes.models import (
    AzureOpenAIEmbeddingSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    DocumentIntelligenceLayoutSkill,
    ShaperSkill,
    ChatCompletionSkill,
    DocumentIntelligenceLayoutSkillChunkingProperties,
)


def getDocumentIntelligenceLayOutSkill():
    return DocumentIntelligenceLayoutSkill(
        name="document-cracking-skill",
        description="Document Intelligence skill for document cracking",
        context="/document",
        output_mode="oneToMany",
        output_format="text",
        extraction_options=["images", "locationMetadata"],
        markdown_header_depth="",
        chunking_properties=DocumentIntelligenceLayoutSkillChunkingProperties(
            unit="characters",
            maximum_length=2000,
            overlap_length=200,
        ),
        inputs=[InputFieldMappingEntry(name="file_data", source="/document/file_data")],
        outputs=[
            OutputFieldMappingEntry(name="text_sections", target_name="text_sections"),
            OutputFieldMappingEntry(
                name="normalized_images", target_name="normalized_images"
            ),
        ],
    )


def getAzureOpenAIEmbeddingSkill(deploymentId, resourceUri, modelName):
    return AzureOpenAIEmbeddingSkill(
        name="text-embedding-skill",
        context="/document/text_sections/*",
        inputs=[
            InputFieldMappingEntry(
                name="text", source="/document/text_sections/*/content"
            )
        ],
        outputs=[OutputFieldMappingEntry(name="embedding", target_name="text_vector")],
        resource_url=resourceUri,
        deployment_name=deploymentId,
        dimensions=1536,
        model_name=modelName,
    )


def getChatCompletionSkill(uri):
    return ChatCompletionSkill(
        name="chat-completion-skill",
        uri=f"{uri}/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21",
        timeout=timedelta(minutes=1),
        context="/document/normalized_images/*",
        inputs=[
            InputFieldMappingEntry(
                name="systemMessage",
                source='=\'You are tasked with generating concise, accurate descriptions of images, figures, diagrams, or charts in documents. The goal is to capture the key information and meaning conveyed by the image without including extraneous details like style, colors, visual aesthetics, or size.\n\nInstructions:\nContent Focus: Describe the core content and relationships depicted in the image.\n\nFor diagrams, specify the main elements and how they are connected or interact.\nFor charts, highlight key data points, trends, comparisons, or conclusions.\nFor figures or technical illustrations, identify the components and their significance.\nClarity & Precision: Use concise language to ensure clarity and technical accuracy. Avoid subjective or interpretive statements.\n\nAvoid Visual Descriptors: Exclude details about:\n\nColors, shading, and visual styles.\nImage size, layout, or decorative elements.\nFonts, borders, and stylistic embellishments.\nContext: If relevant, relate the image to the broader content of the technical document or the topic it supports.\n\nExample Descriptions:\nDiagram: "A flowchart showing the four stages of a machine learning pipeline: data collection, preprocessing, model training, and evaluation, with arrows indicating the sequential flow of tasks."\n\nChart: "A bar chart comparing the performance of four algorithms on three datasets, showing that Algorithm A consistently outperforms the others on Dataset 1."\n\nFigure: "A labeled diagram illustrating the components of a transformer model, including the encoder, decoder, self-attention mechanism, and feedforward layers."\'',
            ),
            InputFieldMappingEntry(
                name="userMessage",
                source="='Please describe this image.'",
            ),
            InputFieldMappingEntry(
                name="image",
                source="/document/normalized_images/*/data",
            ),
        ],
        outputs=[
            OutputFieldMappingEntry(name="response", target_name="verbalizedImage")
        ],
    )


def getAzureOpenAIEmbeddingSkillForVerbalizedImage(
    deploymentId, resourceUri, modelName
):
    return AzureOpenAIEmbeddingSkill(
        name="verblizedImage-embedding-skill",
        context="/document/normalized_images/*",
        inputs=[
            InputFieldMappingEntry(
                name="text", source="/document/normalized_images/*/verbalizedImage"
            )
        ],
        outputs=[
            OutputFieldMappingEntry(
                name="embedding", target_name="verbalizedImage_vector"
            )
        ],
        resource_url=resourceUri,
        deployment_name=deploymentId,
        dimensions=1536,
        model_name=modelName,
    )


def getShaperSkill(ks_container_name: str):
    return ShaperSkill(
        name="#5",
        context="/document/normalized_images/*",
        inputs=[
            InputFieldMappingEntry(
                name="normalized_images",
                source="/document/normalized_images/*",
                inputs=[],
            ),
            InputFieldMappingEntry(
                name="imagePath",
                source=f"='{ks_container_name}/'+$(/document/normalized_images/*/imagePath)",
                inputs=[],
            ),
        ],
        outputs=[
            OutputFieldMappingEntry(name="output", target_name="new_normalized_images")
        ],
    )
