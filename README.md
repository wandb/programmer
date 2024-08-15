# programmer

programmer is a command-line based AI programmer, that will help you get stuff done.

programmer has direct access to your machine, it can run commands, and read and write files, without safety checks. You have been warned!

## Quickstart

```
pip install programmer
programmer 
```

## Usage

Just

```
programmer
```

Alternatively:
```
programmer "<initial_prompt>"
```

To resume from an earlier state:
```
programmer --state <state_ref>
```

## Examples

- "What processes are listening on port 4512?" ... "ok, please kill them"
- "What's in frog.jpg?"
- "Write a function to determine if a tic-tac-toe game is won in a file called tictactoe.py. also write unit tests, and iterate until they pass."

But you can do a lot more than that!

## Improving programmer

programmer is designed to be improved using [weave](https://wandb.me/weave), our toolkit for AI application development. What does this mean?

- you can browse traces and evals in the Weave UI at https://wandb.ai
- programmer can resume from earlier states, with the --state argument
- programmer will log all of your interactions to a local sqlite database, or the central Weave service.
- This data can be used to improve programmer over time, by building Evaluations, fine-tuning, and other techniques.

To run the evaluation:

```
python evaluate.py
```

## roadmap

- [ ] weave server tracking
- [ ] git state tracking
- [ ] user-annotation of good and bad behaviors
- [ ] eval generation