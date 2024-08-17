8/17/24
-------

Git tracking is working in a branch now. Here's what it does:
- If you're in a git repo, programmer automatically creates branches while it works.
- The git state is stored in the trajectories that are auto-saved to Weave.
- This means you can roll back programmer to any prior point, and both the conversation, and git repo state will be restored.

Why do this? To improve an AI application like programmer, you need to experiment.

Let's use an example. Suppose you're using programmer, you ask it to run some unit tests, and programmer say something like "OK here's a plan, I'll run the `pytest` command, would you like to proceed?"

This is annoying, we just want it to run the command instead of stopping and asking the user.

We can try to fix this with prompt engineering. We want to experiment with a bunch of different prompts, starting from the prior state of conversation and file system.


OK, above is the beginning of a write up of how to talk about this feature...

Now I want to do a few things:
- think about if the git feature is ready.
- write a new feature using programmer: programmer settings controls.

Bug:
- programmer fails to restore my original branch