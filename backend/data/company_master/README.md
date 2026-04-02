Place your all-company master dataset in this folder to enable full company search.

If a company is not showing in the project, it usually means that company is missing from your local master dataset. Add it here and restart the backend.

Supported formats:
- `.csv`
- `.tsv`
- `.json` array of objects

Recommended file name:
- `company_master.csv`

Minimum useful columns:
- `company_name`
- `cin` or `llpin`

Optional columns the backend will auto-map when present:
- `company_status`
- `company_type`
- `company_category`
- `registered_address`
- `email`
- `phone`
- `website`
- `pan`
- `gstin`
- `listing_status`
- `date_of_incorporation`
- `last_agm_date`
- `last_bs_date`

Example:
- see `sample_company_master.csv`
- you can also add multiple files like `additional_company_master.csv`

After adding or updating a file here, restart the backend:

```powershell
python backend\pipeline.py
```
