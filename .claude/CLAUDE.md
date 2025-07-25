# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run configuration test
python3 simple_config_test.py

# Run specific test files
python3 tests/test_complete_scribe_workflow.py
python3 tests/oauth_personal_consumer.py

# Deploy to Azure
func azure functionapp publish az-scr-func-udjyyas4iaywk --python
```

### Testing

```bash
# Unit tests
python3 -m pytest tests/unit/

# Integration tests
python3 -m pytest tests/integration/

# Complete workflow test
python3 tests/test_complete_scribe_workflow.py

# OAuth workflow test
python3 tests/test_oauth_workflow.py
```

### Health Checks

```bash
# Test deployed function health
curl https://az-scr-func-udjyyas4iaywk.azurewebsites.net/api/health

# Check configuration
curl https://az-scr-func-udjyyas4iaywk.azurewebsites.net/api/config

# Check OAuth status
curl https://az-scr-func-udjyyas4iaywk.azurewebsites.net/api/oauth-status
```

## Architecture Overview

This is a production-ready Azure Functions app that processes voice email attachments using OAuth authentication and Azure AI Foundry for transcription.

### Core Components

**OAuth-Based Architecture (v3.0)**

- Personal Microsoft account authentication (`julianthant@gmail.com`)
- Automatic token refresh via `src/helpers/oauth_helpers.py`
- Persistent token storage with secure caching

**Main Processors**

- `EmailProcessor` (`src/processors/email_processor.py`): OAuth-based email processing
- `TranscriptionProcessor` (`src/processors/transcription_processor.py`): Azure AI Foundry Fast Transcription API integration
- `ExcelProcessor` (`src/processors/excel_processor.py`): OneDrive Excel file updates

**Workflow Orchestration**

- `WorkflowOrchestrator` (`src/core/workflow_orchestrator.py`): Coordinates the complete email processing workflow
- HTTP and timer-based triggers via `function_app.py`

### Key Features

**Azure AI Foundry Integration**

- Fast Transcription API with speaker diarization
- Multi-language support with auto-detection
- Handles up to 2 hours of audio, 300MB file limit
- Supports: WAV, MP3, OPUS/OGG, FLAC, WMA, AAC, ALAW, MULAW, AMR, WebM, SPEEX

**Production Configuration**

- API Endpoint: `https://eastus.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2024-11-15`
- Authentication: `Ocp-Apim-Subscription-Key`
- Deployed Function: `az-scr-func-udjyyas4iaywk` (Central US)

### Environment Variables Required

```bash
# Azure AI Foundry
AI_FOUNDRY_API_KEY=your_foundry_api_key
AI_FOUNDRY_ENDPOINT=https://ai-julianthant9350ai432449042523.cognitiveservices.azure.com/
AI_FOUNDRY_STT_ENDPOINT=https://eastus.stt.speech.microsoft.com

# OAuth Configuration
MICROSOFT_GRAPH_CLIENT_ID=e66e235d-1ca5-416f-929a-1d9334743a76
MICROSOFT_GRAPH_TENANT_ID=common
TARGET_USER_EMAIL=julianthant@gmail.com

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=voice-attachments

# Application Settings
EXCEL_FILE_NAME=Scribe.xlsx
SCRIBE_LOG_LEVEL=INFO
```

### OAuth Setup (One-time)

Run `python3 tests/oauth_personal_consumer.py` to:

1. Open browser for Microsoft account login
2. Grant permissions for Mail.ReadWrite and Files.ReadWrite.All
3. Save tokens automatically for infinite use

### Workflow Process

1. **Email Processing**: Scans personal email for voice attachments
2. **Audio Upload**: Uploads attachments to Azure Blob Storage
3. **Transcription**: Uses Azure AI Foundry Fast Transcription API
4. **Excel Integration**: Logs structured data to OneDrive `Scribe.xlsx`
5. **Email Organization**: Moves processed emails to "Scribe Processed" folder

### Important Notes

- The system uses OAuth 2.0 for personal Microsoft account access
- All processors require initialization before use via their `initialize()` methods
- Error handling is centralized through `ScribeErrorHandler` in `src/core/error_handler.py`
- Structured logging via `ScribeLogger` in `src/core/logger.py`
- Configuration management via `ScribeConfigurationManager` in `src/core/configuration_manager.py`

When testing or debugging, always run `simple_config_test.py` first to validate environment configuration.

## Writing Functions Best Practices

When evaluating whether a function you implemented is good or not, use this checklist:

1. Can you read the function and HONESTLY easily follow what it's doing? If yes, then stop here.
2. Does the function have very high cyclomatic complexity? (number of independent paths, or, in a lot of cases, number of nesting if if-else as a proxy). If it does, then it's probably sketchy.
3. Are there any common data structures and algorithms that would make this function much easier to follow and more robust? Parsers, trees, stacks / queues, etc.
4. Are there any unused parameters in the function?
5. Are there any unnecessary type casts that can be moved to function arguments?
6. Is the function easily testable without mocking core features (e.g. sql queries, redis, etc.)? If not, can this function be tested as part of an integration test?
7. Does it have any hidden untested dependencies or any values that can be factored out into the arguments instead? Only care about non-trivial dependencies that can actually change or affect the function.
8. Brainstorm 3 better function names and see if the current name is the best, consistent with rest of codebase.

IMPORTANT: you SHOULD NOT refactor out a separate function unless there is a compelling need, such as:

- the refactored function is used in more than one place
- the refactored function is easily unit testable while the original function is not AND you can't test it any other way
- the original function is extremely hard to follow and you resort to putting comments everywhere just to explain it

## Writing Tests Best Practices

When evaluating whether a test you've implemented is good or not, use this checklist:

1. SHOULD parameterize inputs; never embed unexplained literals such as 42 or "foo" directly in the test.
2. SHOULD NOT add a test unless it can fail for a real defect. Trivial asserts (e.g., expect(2).toBe(2)) are forbidden.
3. SHOULD ensure the test description states exactly what the final expect verifies. If the wording and assert don’t align, rename or rewrite.
4. SHOULD compare results to independent, pre-computed expectations or to properties of the domain, never to the function’s output re-used as the oracle.
5. SHOULD follow the same lint, type-safety, and style rules as prod code (prettier, ESLint, strict types).
6. SHOULD express invariants or axioms (e.g., commutativity, idempotence, round-trip) rather than single hard-coded cases whenever practical. Use `fast-check` library e.g.

```
import fc from 'fast-check';
import { describe, expect, test } from 'vitest';
import { getCharacterCount } from './string';

describe('properties', () => {
  test('concatenation functoriality', () => {
    fc.assert(
      fc.property(
        fc.string(),
        fc.string(),
        (a, b) =>
          getCharacterCount(a + b) ===
          getCharacterCount(a) + getCharacterCount(b)
      )
    );
  });
});
```

7. Unit tests for a function should be grouped under `describe(functionName, () => ...`.
8. Use `expect.any(...)` when testing for parameters that can be anything (e.g. variable ids).
9. ALWAYS use strong assertions over weaker ones e.g. `expect(x).toEqual(1)` instead of `expect(x).toBeGreaterThanOrEqual(1)`.
10. SHOULD test edge cases, realistic input, unexpected input, and value boundaries.
11. SHOULD NOT test conditions that are caught by the type checker.

## Code Organization

- `packages/api` - Fastify API server
  - `packages/api/src/publisher/*.ts` - Specific implementations of publishing to social media platforms
- `packages/web` - Next.js 15 app with App Router
- `packages/shared` - Shared types and utilities
  - `packages/shared/social.ts` - Character size and media validations for social media platforms
- `packages/api-schema` - API contract schemas using TypeBox

## Remember Shortcuts

Remember the following shortcuts which the user may invoke at any time.

### QNEW

When I type "qnew", this means:

```
Understand all BEST PRACTICES listed in CLAUDE.md.
Your code SHOULD ALWAYS follow these best practices.
```

### QPLAN

When I type "qplan", this means:

```
Analyze similar parts of the codebase and determine whether your plan:
- is consistent with rest of codebase
- introduces minimal changes
- reuses existing code
```

## QCODE

When I type "qcode", this means:

```
Implement your plan and make sure your new tests pass.
Always run tests to make sure you didn't break anything else.
Always run `prettier` on the newly created files to ensure standard formatting.
Always run `turbo typecheck lint` to make sure type checking and linting passes.
```

### QCHECK

When I type "qcheck", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR code change you introduced (skip minor changes):

1. CLAUDE.md checklist Writing Functions Best Practices.
2. CLAUDE.md checklist Writing Tests Best Practices.
3. CLAUDE.md checklist Implementation Best Practices.
```

### QCHECKF

When I type "qcheckf", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR function you added or edited (skip minor changes):

1. CLAUDE.md checklist Writing Functions Best Practices.
```

### QCHECKT

When I type "qcheckt", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR test you added or edited (skip minor changes):

1. CLAUDE.md checklist Writing Tests Best Practices.
```

### QUX

When I type "qux", this means:

```
Imagine you are a human UX tester of the feature you implemented.
Output a comprehensive list of scenarios you would test, sorted by highest priority.
```

### QGIT

When I type "qgit", this means:

```
Add all changes to staging, create a commit, and push to remote.

Follow this checklist for writing your commit message:
- SHOULD use Conventional Commits format: https://www.conventionalcommits.org/en/v1.0.0
- SHOULD NOT refer to Claude or Anthropic in the commit message.
- SHOULD structure commit message as follows:
<type>[optional scope]: <description>
[optional body]
[optional footer(s)]
- commit SHOULD contain the following structural elements to communicate intent:
fix: a commit of the type fix patches a bug in your codebase (this correlates with PATCH in Semantic Versioning).
feat: a commit of the type feat introduces a new feature to the codebase (this correlates with MINOR in Semantic Versioning).
BREAKING CHANGE: a commit that has a footer BREAKING CHANGE:, or appends a ! after the type/scope, introduces a breaking API change (correlating with MAJOR in Semantic Versioning). A BREAKING CHANGE can be part of commits of any type.
types other than fix: and feat: are allowed, for example @commitlint/config-conventional (based on the Angular convention) recommends build:, chore:, ci:, docs:, style:, refactor:, perf:, test:, and others.
footers other than BREAKING CHANGE: <description> may be provided and follow a convention similar to git trailer format.
```
