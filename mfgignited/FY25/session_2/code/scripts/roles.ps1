$roles = @(
    "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd",
    "a97b65f3-24c7-4388-baec-2e87135dc908",
    "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
    "7ca78c08-252a-4471-8644-bb5ff32d4ba0",
    "8ebe5a00-799e-43f5-93ac-243d3dce84a7",
    "64702f94-c441-49e6-a78b-ef80e0188fee"

)

Write-Host "AZURE_RESOURCE_GROUP not found. Setting it up."
$AZURE_ENV_NAME=$(azd env get-value AZURE_ENV_NAME)
$AZURE_RESOURCE_GROUP = "$AZURE_ENV_NAME"
azd env set AZURE_RESOURCE_GROUP $AZURE_RESOURCE_GROUP

$AZURE_PRINCIPAL_ID = $(azd env get-value AZURE_PRINCIPAL_ID)
$AZURE_SUBSCRIPTION_ID = $(azd env get-value AZURE_SUBSCRIPTION_ID)
foreach ($role in $roles) {
    az role assignment create `
        --role $role `
        --assignee-object-id $AZURE_PRINCIPAL_ID `
        --scope /subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$AZURE_RESOURCE_GROUP `
        --assignee-principal-type User
}