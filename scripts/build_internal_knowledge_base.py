"""Pre-embed the internal role and screening-policy materials in Chroma."""

from agentic_hiring.rag_agent import initialize_internal_knowledge_base


def main() -> None:
    path = initialize_internal_knowledge_base()
    print(f"Internal company knowledge base is ready at {path}.")


if __name__ == "__main__":
    main()

