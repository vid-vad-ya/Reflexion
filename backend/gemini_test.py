from app.services.llm import llm

print(
    llm.generate_text(
        "Say hello in one sentence"
    )
)