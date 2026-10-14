Implement `scripts/summarize.sh FILE`. `FILE` is a JSON array of orders, each `{"id": int, "customer": str, "total": number, "status": str}`. Print exactly four lines to stdout:

```
orders: <number of orders>
paid: <number of orders with status "paid">
revenue: <sum of total over paid orders, two decimals>
top: <customer with the highest paid revenue; ties go to the alphabetically first name; "-" if there are no paid orders>
```

Errors: with no argument, print `usage: summarize.sh FILE` to stderr and exit 2. If the file is missing or is not valid JSON, print an error to stderr and exit 1.

Add tests for the new behaviour in a new test file (pytest is used to run the script). Run the test suite with `python -m pytest -q`.
