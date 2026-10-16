from rag import RAG

QUESTIONS = [
    ("What is the overdraft fee?", "Overdraft Fees and Protection"),
    ("How much does a domestic wire transfer cost?", "Wire Transfer Fees"),
    ("Is there a foreign transaction fee?", "Foreign Transaction Fees"),
    ("What is the minimum balance to waive the checking account fee?", "Minimum Balance Requirements"),
    ("What documents do I need to open an account?", "How to Open an Account"),
    ("What are the interest rates for personal loans?", "Loan Rates and APR"),
    ("What is the APR range for auto loans?", "Auto Loan Overview"),
    ("How do I activate my card?", "Card Activation"),
    ("What should I do if my card is lost or stolen?", "Lost or Stolen Card"),
    ("How do I dispute a transaction?", "Disputing a Transaction"),
    ("What are the branch hours?", "Branch Hours and Locations"),
    ("How do I contact customer service?", "Contact Us"),
    ("Is my money insured?", "General FAQ"),
    ("How do I reset my online banking password?", "General FAQ"),
    ("What is the savings account interest rate?", "Savings Account Overview"),
    ("How much is the premium checking monthly fee?", "Fee Schedule"),
    ("Is there a penalty for paying off my loan early?", "Personal Loan Overview"),
    ("How do I set up direct deposit?", "General FAQ"),
    ("What is the cash back rate on the credit card?", "Credit Card Overview"),
    ("What is the grace period for late loan payments?", "Loan Repayment and Payment Options"),
]


def main():
    rag = RAG()
    correct = 0
    for question, expected in QUESTIONS:
        chunks = rag.hybrid_search(question, top_k=5)
        titles = [c["title"] for c in chunks]
        hit = expected in titles
        if hit:
            correct += 1
        print(f"{'OK' if hit else 'MISS'} | {question} | expected={expected!r} | top={titles}")

    accuracy = correct / len(QUESTIONS)
    print(f"\naccuracy: {correct}/{len(QUESTIONS)} = {accuracy:.0%}")
    print("PASS" if accuracy >= 0.8 else "FAIL")


if __name__ == "__main__":
    main()
