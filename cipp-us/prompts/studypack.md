You are an expert IAPP CIPP/US exam tutor. Below is one chapter of the official study textbook ("U.S. Private-Sector Privacy", 4th edition).

Produce a JSON object with exam-drill material for this chapter. The JSON must have exactly this shape:

{
  "key_terms": [ {"term": "...", "definition": "..."} ],
  "qa": [ {"q": "...", "a": "..."} ]
}

Rules:
- "key_terms": 12-20 of the chapter's most exam-relevant terms, laws, doctrines, and agencies. Definitions must be one or two sentences, precise, and self-contained (understandable without the chapter open).
- "qa": 20-30 active-recall question/answer pairs covering the chapter. These will be read ALOUD as an audio drill (question, four-second pause, answer), so:
  - Questions must be answerable from memory in a few seconds — no "list all twelve..." questions.
  - Answers must be short: one sentence, or a term plus a clarifying phrase. Lead with the answer itself, then at most one sentence of why.
  - Write out acronyms on first use within each item, e.g. "the Fair Credit Reporting Act, or FCRA".
  - Prioritize what the CIPP/US exam tests: definitions, scope ("who is covered"), thresholds, which agency enforces what, preemption, penalties, and commonly confused concept pairs.
  - Mix difficulty: about a third easy recall, a half core exam material, and the rest tricky distinctions.
- Base everything strictly on the chapter text. Do not invent statute numbers, dates, or thresholds not present in the text.
- Output ONLY the JSON object. No markdown code fences, no commentary.

CHAPTER TEXT:

