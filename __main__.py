# EXAMPLE MAIN FOR VISUALISING HOW IT SHOULD LOOK
from sandbox import Sandbox
from llm import FakeAI


def main():

    sandbox = Sandbox()
    ai = FakeAI()

    print("=== MINI AI SANDBOX ===")
    print("Write 'exit' to quit.\n")

    while True:

        task = input("Task > ")

        if task.lower() == "exit":
            break

        print("\n=== AI GENERATING CODE ===")

        code = ai.generate_code(task)

        print(code)

        print("=== EXECUTING IN SANDBOX ===")

        sandbox.run(code)

        print()


if __name__ == "__main__":
    main()
