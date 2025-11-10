## Goal

Build a simple question-answering system that can answer natural-language questions about member data provided by our public API.
Examples of the questions include:

“When is Layla planning her trip to London?”

“How many cars does Vikram Desai have?”

“What are Amira’s favorite restaurants?”

Your system should expose a simple API endpoint (for example /ask) that we can call with a question and receive an answer.

## API

Use the GET /messages endpoint described in Swagger:
👉 https://november7-730026606190.europe-west1.run.app/docs#/default/get_messages_messages__get

Example Response:


## Requirements

Build a small API service that accepts a natural-language question and responds with an answer inferred from the member messages.

It can be implemented in any language and framework.

Output format:

```json
{ "answer": "..." }
```


The service must be deployed and publicly accessible.

## Bonus Goals
### Bonus 1: Design Notes

In your README.md, describe several alternative approaches you considered for building the question-answering system.

### Bonus 2: Data Insights

Analyze the dataset and identify anomalies or inconsistencies in the member data. Summarize your findings briefly in your README.md.



## Submission


1. Create a public GitHub repository.
2. Deploy your service.
3. [optionally] Provide a short (1–2 min) screen recording or Loom video demonstrating example queries.
4. Share your work with us.