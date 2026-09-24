# LLM Gateway: Decisions

## What I built:

I have built a mini LLM Gateway in Python(FastAPI) using OpenAI and Gemini as the two LLM providers and SQLite as the lightweight db. Instead of exposing provider keys directly to the end user, it gives caller a gateway API key through which they can access the models (with each key having a usage limit of 10,00,000 tokens). It also limits token use per gateway api key and records both successful and failed requests in SQLite. I have also designed to include automatic fall-back mechanism to shift to different model when the main model returns an error while processing request. I have chosen the gateway to return only non-streaming completions so that it is easier to account for token usage against each gateway key. 

## Moving parts and request lifecycle

The application is made of five main files:

- main.py   --> FastAPI application and endpoints such as  `/v1/chat/completions`, `/usage`, and `/health`.
- auth.py    --> Checks the caller's `x-api-key` against `ALLOWED_API_KEYS`.
- rate_limiter.py  --> Contains functions to reserve and reconcile token budgets.
- db.py --> Setting up SQLite db and initializing tables `budgets` and  `usage_log`
- log.py  --> Query and save data in the SQLite tables mentioned above.




A request follows this path:

```text
Client
  | POST /v1/chat/completions + x-api-key + model-name
  v
FastAPI gateway
  |-- validate gateway key
  |-- validate requested model against ALLOWED_MODELS
  |-- estimate prompt tokens + max_tokens
  v
SQLite budget reservation
  |-- atomic check: is this key still below its limit?
  |-- reserve the total estimated tokens limits and write the data in the budgets table
  v
LiteLLM -> requested provider (OpenAI or Gemini)
  |-- success: reconcile estimated usage with actual usage (release remaining tokens limits back to the client)
  |            write success row to usage_log
  |            return provider response
  |-- error:   release all the token limits that were reserved 
  |            write error row to usage_log
  |            try the alternate LLM provider
  v
Client response, or HTTP 503 if every attempted provider fails
```

`GET /usage` is also authenticated with the same gateway key. It info about shows api key's usage (by extracting data from `usage_log` table) and returns request count, token count, and an approximate cost till now.

## Important decisions

### 1. SQLite for data storage and querying

**Options considered:**  
A. SQLite  
B. Redis     
C. Postgres

**Picked:** local SQLite database for its minimal setup and no initializing of a separate database server. I have also configured SQLite to handle concurrent transactions and enabled WAL mode for smoother handling of reads and writes

**Tradeoff accepted:** this is simple to run locally, but it is intended for one process/instance and not suitable for scalability.

### 2. Reserve estimated tokens before calling a provider

**Options considered:**  
A. Record only final usage after a response.  
B. Reserve an estimate no. of tokens first and reconcile later.

**Picked:** Option B. I first reserved an estimate, then adjusted the reservation to actual provider usage instead of waiting for the final usage after response. I did so to prevent the issue of budget exceeding while handling concurrent requests.

**Tradeoff accepted:** Estimates can be imperfect. And it adds an extra layer of proccessing and writing data to the table.

### 3. One provider abstraction with controlled fallback

**Options considered:**   
A. Expose provider-specific endpoints  
B. Implement two provider SDKs directly  
C. Or use LiteLLM behind an OpenAI-compatible endpoint.

**Picked:** LiteLLM as it simplifies provider integration through one common interface instead of designing integrations for each LLM provide. Its library also includes built-in utilities such as `token_counter` eliminating need to write custom logic.

**Tradeoff accepted:** LiteLLM simplifies provider integration but adds a dependency and its model/provider naming rules. For e.g.: to access gemini models, naming convention should be "gemini/gemini-2.5-flash-lite" instead of just "gemini-2.5-flash-lite".

### 4. Non-streaming responses only

**Options considered:**   
A. Support streaming immediately  
B. Go for non streaming responses

**Picked:** I went for non-streaming as it has to handle than a non-streaming response and gateway can correctly calculate usage after a complete response is recieved. Non-streaming also has simpler error handling.

**Tradeoff accepted:** The gateway cannot display tokens as they arrive and clients must wait for the full answer.

## Concurrency near an exhausted budget

If two requests from the same nearly exhausted key arrive at almost the same time, each request must reserve its estimated tokens before it calls a provider. The gateway takes a process-level `threading.Lock` and starts a SQLite `BEGIN IMMEDIATE` transaction to update the database one request at a time. The first request reads and updates the budget, whereas the second request waits until the first request is processed, and then reads the already-updated value. If its estimated tokens exceed `MONTHLY_BUDGET`, it is rejected.

## Fallback policy

The normal path is OpenAI first and Gemini second, configured by `PRIMARY_MODEL` and `FALLBACK_MODEL`. A provider error releases the initially reserved tokens, writes an error row, and attempts the other configured model. This keeps the gateway available through a provider outage or invalid provider credential.

## Why enforce budgets at the gateway instead of trusting callers?

The gateway is the single place every request passes through before it costs money. If each caller tracked its own budget, a bug, retry loop, or misuse could easily exceed the limit. Enforcing it centrally keeps provider keys protected and spending predictable.

## What I deliberately did not build, and why
I did not build streaming responses, user management, an admin dashboard, exact billing, or a separate production database. The goal was to keep the project focused on core functionalities such as budgets, fallback, and logging.

## The decision I’m least confident about
Automatic provider fallback is the decision I am least certain about.
It is helpful because users still get a response when OpenAI or Gemini has an outage. However, switching providers can change response quality, cost, latency, or data-handling expectations. In a more complete version, callers should be able to choose whether fallback is allowed.

## Where it breaks, and what I’d do with one more week

Once the api keys provided by gateway exhaust there limits, they cant be reset therefore rendering them useless.
Also, SQLite deployed on Free version of Render resets after restarts or redeploys therefore deleting any previously saved data. 
With another week, I would create a frontend, move data to Postgres, add proper monthly budget resets, improve request validation and error handling, and make fallback behavior configurable per request.
