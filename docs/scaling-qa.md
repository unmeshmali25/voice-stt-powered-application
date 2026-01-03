# Scaling Simulation QA

## Context
Current State:
- 10 agents running successfully. Target: 372 agents. Orchestrator uses a sequential loop for agents. Agents currently use direct DB access (SQLAlchemy) rather than HTTP API calls.
- `ShoppingActions` class writes directly to tables (`cart_items`, `orders`).

## Questions for the User

### 1. Agent Execution & Concurrency
- **Current:** Agents are processed sequentially in a loop (`for agent in agents: await _run_agent...`).
- **Issue:** With 372 agents, if each takes even 0.5s, one cycle (1 hour) takes 3 minutes.
- **Question:** Do you want fully parallel execution (asyncio/threading) or batched execution? 
- **Constraint:** Parallel execution requires managing DB connections carefully.
#Unmesh: We can go for batched execution. 

### 2. Interaction Method: API vs Direct DB
- **Observation:** You mentioned "API calls for cart and checkout" in your prompt.
- **Reality:** `app/simulation/agent/actions.py` currently performs direct SQL INSERTs.
- **Question:** Do you want to **refactor** the agents to actually hit `http://localhost:8000/api/...`?
    - *Pros:* Real load test of the API server, tests networking stack.
    - *Cons:* Slower, more complex to orchestrate, requires running the API server alongside.
    - *Alternative:* Stick to direct DB calls for simulation speed.
#Unmesh: Stick to direct DB calls and API endpoints for cart, checkout, offer etc. on Railway remote server.  

### 3. LLM Usage & Rate Limits
- **Question:** Do the agents make live LLM calls (OpenAI/Anthropic) during their shopping loop?
- **Concern:** 372 concurrent agents will likely hit rate limits (TPM/RPM) or rack up high costs.
- **Option:** Should we use mocked responses or a local LLM for the large-scale run?
#Unmesh: The agents do not make live LLM calls during their shopping loop. But I'd like to add that in future. 

### 4. Database Constraints
- **Question:** Are you using a hosted Supabase instance or local Postgres for this run?
- **Concern:** Hosted instances have connection limits (e.g., 60-100 connections).
- **Need:** We might need a connection pooler (PgBouncer) or strict client-side pooling.
#Unmesh: I have a Supabase pro plan that I pay $25 a month for. Make best judgement call for decision. 


### 5. Hardware Specifications
- **Question:** What are the specs of the machine running this? (RAM, CPU cores).
- **Relevance:** 372 concurrent Python tasks/threads consume significant memory.
#Unmesh: 16GB RAM and 8 CPU cores. I have the M1 Pro Macbook Pro. 

### 6. Monitoring & Reliability
- **Question:** "Start from a checkpoint if it fails" - currently, the DB stores state.
- **Clarification:** Does "checkpoint" mean resuming the *simulation clock* and *agent states* from the last successful hour?
- **UI:** Is the current Rich terminal dashboard sufficient, or do you need a web-based dashboard?
#Unmesh: Yes. Last checkpoint can be the last "simulated_time". 

### 7. Time Scale
- **Question:** What is the target `time_scale`? (e.g., 24x = 1 real hour is 24 sim hours).
- **Impact:** Higher speed + more agents = massive load intensity.
#Unmesh: I tested with a time-scale of 96 but I am flexible to go down to time-scale of 48. 

## Final Recommendations & Selected Choices

| Area | Choice | Recommendation |
| :--- | :--- | :--- |
| **Concurrency** | Batched Async | Use batches of 50-75 agents via `asyncio.gather` to balance throughput and connection limits. |
| **Interaction** | Hybrid (API + DB) | Perform Cart/Checkout/Offer via HTTP to Railway; use DB for metadata/agent loading. |
| **Database** | Remote Supabase | Use Transaction mode (PgBouncer) on port 6543 for the Pro plan to handle batch writes. |
| **Checkpoint** | DB-Driven | Auto-resume by querying the latest `created_at` in the orders table. |
| **Time Scale** | 48x (Baseline) | Start at 48x. If CPU/Network latency is < 20% of cycle time, increase to 96x. |
| **Hardware** | Single Instance | M1 Pro handles 372 async tasks easily; no need for distributed workers yet. |