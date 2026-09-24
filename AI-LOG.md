# LLM Gateway: AI-LOG

## Which AI tools/models you used, and for what
I used Codex as a development assistant to review the project structure, explain design choices, identify issues and provide code snippets. I used LiteLLM in the application itself to provide one common interface for OpenAI and Gemini. My project is inspired by this Github repo ("https://github.com/dkyol/llm-gateway-proxy/tree/main") which I reviewed to create a template for my project.

## One place the AI was wrong or misleading, and how you caught it
The gemini model was giving error unlike the open ai model which was giving response perfectly. Codex initialy assumed that Gemini needed additional Google Application Default Credentials. Testing the actual Gemini request showed that the real issue was different. LiteLLM uses a strict naming convention for the models and was not recognizing gemini, and the running server was not reliably loading the Gemini API key. I verified this by making a minimal direct request and reading the provider error.

## One place you overrode the AI’s suggestion, and why
I kept SQLite instead of moving immediately to Postgres. SQLite was the better choice for this small project because it avoided extra infrastructure and kept the setup simple.

## How you stayed in control of code you did not type by hand
I reviewed the generated code before using it and tested the important paths manually. I checked that provider keys stayed in environment variables, not source code; that budget updates were protected with a lock and database transaction. I also tested both OpenAI and Gemini through the deployed gateway.

## Something you had to learn from scratch this weekend, and how you got up to speed
Actually most of my time went into learning how exactly does LLM Gateway work. For this I referred to resources such as AI, Youtube videos, repos etc. I had to learn what is LiteLLM. Only after I was thoroughly clear what I had to build did I start. I worked through the error messages, used AI, manually tested the codebase, and fixed issues based on the result.