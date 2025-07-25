/*
  Azure Infrastructure for Scribe Voice Email Processing Function
  
  This template creates:
  - Function App with Python runtime for voice email processing  
  - Azure OpenAI for transcription and analysis
  - Storage Account for function storage and email attachments
  - Application Insights for monitoring
  - Log Analytics workspace for centralized logging
  - System-assigned managed identity for secure access
  
  Architecture decisions:
  - Consumption plan for cost-effective serverless execution
  - System-assigned managed identity for secure service access
  - Centralized logging through Application Insights and Log Analytics
*/

targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

// User-configurable parameters for the function app
@description('Target user email address for processing')
param targetUserEmail string = ''

@description('Log level for the Scribe function app')
param scribeLogLevel string = 'INFO'

// Generate a unique token for resource naming
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var resourcePrefix = 'scr'

// Tags to be applied to all resources
var commonTags = {
  'azd-env-name': environmentName
}

// Service-specific tags for the Function App
var functionAppTags = union(commonTags, {
  'azd-service-name': 'scribe-function'
})

// User-assigned managed identity for secure resource access
resource userManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'az-${resourcePrefix}-id-${resourceToken}'
  location: location
  tags: commonTags
}

// Storage Account for Azure Functions runtime and email attachments
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'az${resourcePrefix}st${resourceToken}'
  location: location
  tags: commonTags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Log Analytics workspace for centralized logging
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'az-${resourcePrefix}-log-${resourceToken}'
  location: location
  tags: commonTags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights for application monitoring
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'az-${resourcePrefix}-ai-${resourceToken}'
  location: location
  tags: commonTags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

// Azure AI Speech Service for fast transcription
resource speechService 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: 'az-${resourcePrefix}-speech-${resourceToken}'
  location: location
  tags: commonTags
  kind: 'SpeechServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'az-${resourcePrefix}-speech-${resourceToken}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}


// Role assignments for user-assigned managed identity to access storage
resource storageDataOwnerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, userManagedIdentity.id, 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b') // Storage Blob Data Owner
    principalId: userManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, userManagedIdentity.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: userManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageQueueDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, userManagedIdentity.id, '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88') // Storage Queue Data Contributor
    principalId: userManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageTableDataContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, userManagedIdentity.id, '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3') // Storage Table Data Contributor
    principalId: userManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource monitoringMetricsPublisherRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(applicationInsights.id, userManagedIdentity.id, '3913510d-42f4-4e42-8a64-420c390055eb')
  scope: applicationInsights
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb') // Monitoring Metrics Publisher
    principalId: userManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// App Service Plan for Function App (Consumption plan)
resource hostingPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'az-${resourcePrefix}-plan-${resourceToken}'
  location: location
  tags: commonTags
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true  // Required for Linux consumption plan
  }
}

// Function App for voice email processing
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: 'az-${resourcePrefix}-func-${resourceToken}'
  location: location
  tags: functionAppTags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userManagedIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: hostingPlan.id
    reserved: true
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: false  // Not available in consumption plan
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower('az-${resourcePrefix}-func-${resourceToken}')
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsights.properties.ConnectionString
        }
        // Azure Speech Service configuration for fast transcription
        {
          name: 'AZURE_AI_SERVICES_ENDPOINT'
          value: speechService.properties.endpoint
        }
        {
          name: 'AZURE_SPEECH_ENDPOINT'
          value: speechService.properties.endpoint
        }
        // Microsoft Graph API configuration
        {
          name: 'GRAPH_API_ENDPOINT'
          value: 'https://graph.microsoft.com/v1.0'
        }
        {
          name: 'GRAPH_API_SCOPE'
          value: 'https://graph.microsoft.com/.default'
        }
        // Storage configuration for email attachments
        {
          name: 'AZURE_STORAGE_ACCOUNT_NAME'
          value: storageAccount.name
        }
        {
          name: 'AZURE_STORAGE_CONTAINER_NAME'
          value: 'email-attachments'
        }
        // User-configurable settings
        {
          name: 'TARGET_USER_EMAIL'
          value: targetUserEmail
        }
        {
          name: 'SCRIBE_LOG_LEVEL'
          value: scribeLogLevel
        }
      ]
      cors: {
        allowedOrigins: ['*']
        supportCredentials: false
      }
    }
  }
}

// Connect Function App to Log Analytics workspace
resource functionDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'function-logs'
  scope: functionApp
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'FunctionAppLogs'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

// Required outputs for azd
output RESOURCE_GROUP_ID string = resourceGroup().id

// Service endpoints for application configuration
output AZURE_AI_SERVICES_ENDPOINT string = speechService.properties.endpoint
output AZURE_STORAGE_ACCOUNT_NAME string = storageAccount.name
output FUNCTION_APP_NAME string = functionApp.name
output FUNCTION_APP_URL string = 'https://${functionApp.properties.defaultHostName}'
output APPLICATION_INSIGHTS_CONNECTION_STRING string = applicationInsights.properties.ConnectionString
