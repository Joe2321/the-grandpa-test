# Contributing to The Grandpa Test

Thanks for your interest in contributing! Here's how you can help expand the benchmark.

## Submitting New Model Results

### 1. Run the test

```bash
# Set your API key
export OPENAI_API_KEY="sk-..."  # or ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY

# Run the test
python run_test.py --model your-model-name
```

If your model isn't in the built-in list, you can:
- Add it to the `MODELS` list in `run_test.py` and submit that change with your PR
- Or run the prompt manually and save the result in the expected format

### 2. Verify the output

Check your result file in `results/raw/`:
- JSON file should contain: `model_name`, `model_id`, `provider`, `timestamp`, `elapsed_seconds`, `response`
- The response should contain answers to all 6 questions

### 3. Score the result

Use the [scoring rubric](rubric.md) to grade each question (0, 0.5, or 1 point). Include your scoring in the PR description.

### 4. Open a Pull Request

- Add your result file(s) to `results/raw/`
- In the PR description, include:
  - Model name and version
  - Provider
  - Total score (X/6)
  - Per-question scores (Q1-Q6)
  - Any notable observations
  - Your scoring rationale for borderline cases

### 5. Alternative: Open an Issue

If you'd rather not submit a PR, use the **[New Model Result](../../issues/new?template=new-model-result.md)** issue template to share your findings.

## Adding a New Provider

If your model uses a different API (not OpenAI, Anthropic, Google, or xAI):

1. Add a caller function in `run_test.py` following the existing pattern
2. Add the provider to `PROVIDER_CALLERS`
3. Add your models to the `MODELS` list
4. Test it works
5. Submit a PR

## Scoring Guidelines

- Be **consistent** — use the [rubric](rubric.md) strictly
- Q3 is the critical differentiator — be strict about whether the model identifies the stranger relationship
- When in doubt, give **0.5** (partial credit) rather than rounding up or down
- Include your reasoning for any borderline scores

## Code Style

- Python 3.9+ compatible
- Keep `run_test.py` dependency-light (`requests` only for core functionality)
- No unnecessary abstractions — the script should be readable by anyone

## Reporting Issues

- **Wrong score in the leaderboard?** Open an issue with the model name and your proposed correction
- **Script bug?** Open an issue with the error message and your environment details
- **Suggestion?** Open a discussion or issue — we're open to ideas

## Code of Conduct

Be respectful. This is a research project. Disagreements about scoring are welcome; personal attacks are not.
