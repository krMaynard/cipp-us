You are building an Anki deck for a CIPP/US candidate who already understands privacy concepts and can reason through scenarios, but needs to memorize the SPECIFIC, HARD-TO-REASON facts about U.S. regulations: exact law names, acronyms, years enacted, statutory citations, the enforcing agency, and concrete thresholds/penalties.

From the chapter below, extract every specifically-named U.S. law, regulation, rule, framework, or landmark case that has a memorizable name AND at least one hard fact (a year, a citation, an enforcer, or a numeric threshold). Focus on the rote hooks — skip purely conceptual material the candidate can reason through.

Output a JSON object of this exact shape:

{
  "items": [
    {
      "slug": "FCRA",
      "law": "Fair Credit Reporting Act",
      "acronym": "FCRA",
      "year": "1970",
      "citation": "15 U.S.C. §1681",
      "scope": "Consumer reporting agencies, and users/furnishers of consumer reports.",
      "trigger": "Using a consumer report for a permissible purpose (credit, employment, insurance).",
      "enforcer": "FTC and CFPB; private right of action.",
      "key_facts": "Employment screening requires disclosure + written authorization and pre-/post-adverse-action notice.",
      "scenario": "An employer wants to run a third-party background check on a job applicant and use it to decide whether to hire."
    }
  ]
}

Field rules:
- "slug": short unique key, usually the acronym or a CamelCase short name (e.g. "FCRA", "GLBA", "PrivacyAct1974"). Must be unique within your output.
- "law": the full official name, no acronym.
- "acronym": the common short form. If the law has no acronym, repeat a short form of the name.
- "year": the year enacted or adopted, as a 4-digit string. If genuinely unknown from the text, use "" (empty).
- "citation": the U.S.C./C.F.R. or other statutory citation if the text gives one; else "".
- "scope": one sentence — who/what is regulated.
- "trigger": one sentence — the act or threshold that pulls conduct under the law.
- "enforcer": the agency/agencies, and whether a private right of action exists, if known.
- "key_facts": one sentence with the single most exam-relevant threshold, penalty, deadline, or rule.
- "scenario": ONE concrete, plain-language situation (no law names in it) that should make the candidate think of THIS law. This is the most important field — write it like a mini exam fact-pattern.

Rules:
- Base every fact strictly on the chapter text. Do NOT invent years, citations, or thresholds. If the chapter doesn't state a fact, leave that field "".
- Prefer 6–14 high-value items per chapter. Quality over quantity — only items with a real memorizable name and at least one hard fact.
- Do not include an item that has neither a year, a citation, nor a named enforcer — it isn't a rote-fact card.
- Output ONLY the JSON object. No markdown fences, no commentary.

CHAPTER TEXT:

