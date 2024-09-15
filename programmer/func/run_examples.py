from rich import print
from .plan import planner

int_sum_problem = "The greatest common divisor of two positive integers less than $100$ is equal to $3$. Their least common multiple is twelve times one of the integers. What is the largest possible sum of the two integers?"

if __name__ == "__main__":
    print(planner.run({"problem": int_sum_problem}))
