# Feature To Excel

Offline Python desktop tool for converting Gherkin `.feature` files into Excel test case sheets.

## What It Generates

The generated workbook contains these columns:

- ID
- Labels
- Lan
- Test Summary
- Description
- Action
- Expected Result
- Data
- Auto Assessment
- POD
- MALCODE
- Test Repository Path

## Main Rule

Each `Examples` data row creates one Excel test case row.

Example:

```gherkin
Examples:
  | SSOUser            | MMSUser           |
  | RETAIL_AdminUserId | MMSRB_FieldUserId |
  | RETAIL_BMUserId    | MDDS_FieldName    |
```

This creates three Excel test cases.

## Run

Install dependency:

```bash
pip install openpyxl
```

Run the app:

```bash
python feature_to_excel.py
```

Then select:

1. input `.feature` file
2. output `.xlsx` file path
3. Generate Excel

## Important Files

- `feature_to_excel.py` - main generator app
- `FEATURE_FIELD_TO_EXCEL_MAPPING.md` - explains how feature fields map to Excel columns
- `feature_to_excel_mapping_template.feature` - template showing all supported mapping fields
- `test_multiple_examples.feature` - test file proving multiple Examples rows generate multiple Excel rows

## Notes

- The generator does not use AI.
- It does mechanical conversion from feature text into Excel.
- Meaningful Excel output requires meaningful feature input.
- Use `TestSummary` and `Description` columns in Examples when you need exact company wording.
