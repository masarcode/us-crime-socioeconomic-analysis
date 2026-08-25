# Data dictionary

## Processed state dataset

File: [`data/processed/state_analysis_2023.csv`](../data/processed/state_analysis_2023.csv)

| Field | Type | Definition |
|---|---|---|
| `state_fips` | string | Two-digit Census state FIPS code. |
| `state_abbr` | string | Two-letter postal abbreviation. |
| `state` | string | State name. |
| `reported_violent_offenses` | integer | Sum of the 12 monthly FBI CDE reported violent-offense counts. |
| `fbi_population` | integer | FBI CDE total state population denominator for 2023. |
| `mean_participating_population` | number | Mean of the 12 monthly populations represented by participating agencies. |
| `violent_crime_rate_per_100k` | number | Sum of 12 monthly FBI CDE rates per 100,000 participating-population residents. |
| `mean_population_coverage_pct` | number | Mean monthly share of state population covered by reporting agencies. |
| `min_population_coverage_pct` | number | Lowest monthly population coverage in 2023. |
| `median_household_income` | integer | ACS B19013 state estimate in 2023 inflation-adjusted dollars. |
| `civilian_labor_force` | integer | ACS B23025 civilian labor-force estimate. |
| `unemployed` | integer | ACS B23025 unemployed estimate. |
| `unemployment_rate_pct` | number | `unemployed / civilian_labor_force × 100`. |
| `median_income_10k` | number | Median household income divided by $10,000 for coefficient interpretation. |
| `eligible_primary_model` | boolean | True when mean FBI population coverage is at least 90%. |
| `exclusion_reason` | string | Documented reason an observation is omitted from the primary model. |
| `fbi_source_refresh_date` | date | UCR refresh date returned by the CDE endpoint. |

## Reporting tables

| File | Purpose |
|---|---|
| `model_coefficients.csv` | Primary HC3 estimates, standard errors, p-values, and 95% intervals. |
| `model_diagnostics.csv` | Fit, residual, heteroskedasticity, collinearity, and influence diagnostics. |
| `sensitivity_analysis.csv` | Comparable results across five documented specifications. |
| `influence_diagnostics.csv` | State leverage, studentized residuals, and Cook's distance. |
| `correlations.csv` | Pearson correlations in the primary sample. |
| `descriptive_summary.csv` | Count, mean, dispersion, and quantiles in the primary sample. |

## Source variables

| Source field | Publisher | Use |
|---|---|---|
| `B19013_E001` | U.S. Census Bureau ACS | Median household income. |
| `B23025_E003` | U.S. Census Bureau ACS | Civilian labor force denominator. |
| `B23025_E005` | U.S. Census Bureau ACS | Unemployed numerator. |
| `offenses.actuals` | FBI CDE | Monthly reported violent-offense count. |
| `offenses.rates` | FBI CDE | Monthly reported violent-offense rate per 100,000. |
| `participated_population` | FBI CDE | Monthly population represented by participating agencies. |
| `Percent of Population Coverage` | FBI CDE | Monthly reporting-coverage quality field. |
