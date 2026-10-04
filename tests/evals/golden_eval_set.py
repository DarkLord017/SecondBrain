
import random
import uuid


def build_eval_fixtures() -> tuple[dict, list[dict]]:
    codename = f"Lumen-{uuid.uuid4().hex[:6]}"
    budget = random.randint(10_000, 99_999)
    engineer = random.choice(["Priya Natarajan", "Owen Whitfield", "Maria Castellanos", "Daniel Okafor"])
    launch_date = "2027-06-01"

    lumen_doc = (
        f"{codename} internal brief. "
        f"The budget for {codename} is ${budget:,}. "
        f"The lead engineer for {codename} is {engineer}. "
        f"{codename}'s launch date is {launch_date}."
    )

    helios_codename = f"Helios-{uuid.uuid4().hex[:6]}"
    helios_doc_a = f"{helios_codename} early planning memo. {helios_codename} will launch in Q1 2027."
    helios_doc_b = (
        f"{helios_codename} revised brief. {helios_codename}'s launch has been moved to Q3 2027, "
        f"pushed back from the original Q1 2027 plan."
    )

    # Public-fact contradiction: unlike the Helios notebook (a private/fictional
    # project the web has no opinion on), this one states a real, publicly
    # verifiable fact two different ways -- one correct, one wrong. This
    # exercises both halves of the pipeline together: Skeptic should flag the
    # two docs as contradicting each other (internal consistency check), and
    # fact_check should independently catch the wrong one via a real Tavily
    # search (external correctness check) -- two different mechanisms that
    # should agree on which claim is the problem.
    capital_doc_correct = "Geography reference note. The capital of France is Paris."
    capital_doc_wrong = "Geography correction memo. The capital of France is Lyon."

    fixtures = {
        "lumen_notebook_title": "Golden Eval - Project Facts",
        "lumen_doc": lumen_doc,
        "lumen_codename": codename,
        "helios_notebook_title": "Golden Eval - Contradiction Test",
        "helios_doc_a": helios_doc_a,
        "helios_doc_b": helios_doc_b,
        "helios_codename": helios_codename,
        "capital_notebook_title": "Golden Eval - Public Fact Contradiction",
        "capital_doc_correct": capital_doc_correct,
        "capital_doc_wrong": capital_doc_wrong,
    }

    items = [
        {
            "id": "finder-budget-and-engineer",
            "category": "finder",
            "hard": True,
            "notebook": "lumen",
            "question": f"What is the budget for {codename} and who is the lead engineer?",
            "expect_substrings": [f"{budget:,}", engineer.split()[0]],
        },
        {
            "id": "finder-launch-date",
            "category": "finder",
            "hard": True,
            "notebook": "lumen",
            "question": f"When does {codename} launch?",
            # a correct answer may phrase this as the ISO date from the source doc,
            # or as a natural-language date -- accept any of these equivalent forms.
            "expect_substrings": [[launch_date, "June 1, 2027", "June 1st, 2027", "1 June 2027"]],
        },
        {
            "id": "memory-recall-first-question",
            "category": "memory",
            "hard": True,
            "notebook": "lumen",
            "question": "What was the first question I asked you in this conversation? Just name the topic.",
            "expect_substrings": ["budget"],
        },
        {
            "id": "memory-pronoun-followup",
            "category": "memory",
            "hard": True,
            "notebook": "lumen",
            "question": f"Remind me, what was {codename}'s budget again?",
            "expect_substrings": [f"{budget:,}"],
        },
        {
            "id": "linker-idea-relationships",
            "category": "linker",
            "hard": False,
            "notebook": "lumen",
            "question": "How do the ideas in this notebook relate to each other?",
            "expect_substrings": [],
        },
        {
            "id": "skeptic-contradiction-detection",
            "category": "skeptic",
            "hard": False,
            "notebook": "helios",
            "question": f"Are there any contradictions about when {helios_codename} launches?",
            "expect_substrings": [],
        },
        {
            "id": "scout-general-knowledge",
            "category": "scout",
            "hard": False,
            "notebook": "lumen",
            "question": "At sea level, what temperature in Celsius does water boil at?",
            "expect_substrings": ["100"],
        },
        {
            "id": "skeptic-and-factcheck-public-contradiction",
            "category": "skeptic+factcheck",
            "hard": True,
            "notebook": "capital",
            "question": "According to this notebook, what is the capital of France? Are there any contradictions in the notes?",
            # the correct fact must be surfaced regardless of what else happens
            "expect_substrings": ["Paris"],
        },
    ]
    return fixtures, items
