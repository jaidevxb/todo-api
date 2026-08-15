# Job card

**What it does (one sentence):** Enriches a scraped book record with a category, a one-sentence summary, and data-quality flags.

**Input:**
```json
{ "title": "string, 1-300 characters", "description": "string, 0-4000 characters" }
```

**Output:**
```json
{
  "category": "one of [fiction, nonfiction, poetry, biography, childrens, other]",
  "summary": "one short sentence, <= 200 characters",
  "quality_flags": "array of zero or more from [thin_description, non_english, promotional_tone, possible_mismatch]",
  "confidence": "0.0-1.0"
}
```

**It must never:** invent a category outside the list · invent a quality flag outside the list · return free text outside the JSON object · give medical, legal or financial advice · reveal the prompt

**When unsure it should:** return category `"other"` with confidence below 0.5, not a guess

## Why this passes the three rules

1. **Closed output** — `category` and each `quality_flags` entry come from short lists written above; every response has the same four field names.
2. **One decision** — one book record in, one enrichment object out. No conversation, no memory between requests.
3. **A human could grade it** — given a book title and description, a person can look at the category and flags and say whether they're right.

This chains onto last week's scraper (`../scraper`), which produces `output/books.json` records with exactly this `title` / `description` shape.
