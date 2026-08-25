# Methodology

## Research question

Across the 50 U.S. states in 2023, how were unemployment and median household income associated with FBI-reported violent-crime rates?

The design is deliberately cross-sectional and descriptive. It estimates adjusted associations; it does not identify causal effects.

## Unit of analysis and scope

- Unit: U.S. state.
- Reference year: 2023.
- Geography: 50 states. The District of Columbia and U.S. territories are excluded because the stated question concerns states and because D.C. is structurally unlike a state-level observation.
- Primary sample: 43 states with mean monthly FBI population coverage of at least 90%.

The regression is unweighted, so every state is one analytical unit. Population weighting would answer a different question about the average resident rather than the average state.

## Outcome construction

The acquisition workflow requests the FBI Crime Data Explorer `violent-crime` endpoint for each state from January through December 2023. It stores 600 state-month rows with:

- reported violent offenses;
- total state population;
- participating-agency population;
- the FBI-provided monthly rate per 100,000; and
- percent of population covered by reporting agencies.

Every monthly rate is validated against `reported offenses / participating population × 100,000`, allowing for the FBI endpoint's two-decimal rounding. A state's annual reported violent-crime rate is the sum of its 12 monthly rates. Mean and minimum coverage are retained as quality fields.

The primary model excludes states with mean coverage below 90%. This rule is set before modeling in [`config/project.json`](../config/project.json). Exclusion avoids interpreting obvious reporting gaps as genuinely low crime, but it cannot eliminate all selection bias from voluntary UCR participation.

## Predictor construction

Both predictors come directly from 2023 ACS 1-year state estimates:

- `median_household_income`: table B19013 estimate B19013_E001, in 2023 inflation-adjusted dollars;
- `unemployment_rate_pct`: B23025_E005 unemployed divided by B23025_E003 civilian labor force, multiplied by 100.

Using direct state estimates fixes the earlier workflow's ecological aggregation error: medians and rates should not be reconstructed by taking an unweighted mean of county values.

## Primary model

The fitted equation is:

`violent_crime_rate = β0 + β1(unemployment_rate_pct) + β2(median_income_10k) + ε`

where `median_income_10k` is median household income divided by $10,000. Ordinary least squares coefficients are paired with HC3 heteroskedasticity-robust standard errors and 95% confidence intervals.

The primary model uses 43 states. The coefficient table, exact p-values, and intervals are in [`outputs/tables/model_coefficients.csv`](../outputs/tables/model_coefficients.csv).

## Diagnostics

The workflow publishes:

- R² and adjusted R²;
- root mean squared error;
- Jarque-Bera residual-normality diagnostic;
- Breusch-Pagan heteroskedasticity diagnostic;
- condition number;
- variance inflation factors;
- leverage, studentized residuals, and Cook's distance; and
- a Cook's-distance flag at `4 / n`.

Diagnostics are evidence about model behavior, not automatic pass/fail rules. HC3 uncertainty is used regardless of the Breusch-Pagan result because the sample is small and state residual variance need not be constant.

## Sensitivity specifications

Five specifications are reported:

1. Primary: 90% mean reporting-coverage floor.
2. All 50 states: shows the effect of retaining low-coverage observations.
3. Higher coverage: 95% mean reporting-coverage floor.
4. Log outcome: addresses positive skew and changes interpretation to approximate proportional differences.
5. Influence diagnostic: removes the two highest Cook's-distance observations from the primary sample. This is diagnostic only, not a preferred model selected to improve significance.

The unemployment estimate remains positive in every specification. The income estimate remains negative, but its p-value is sensitive to sample and specification choices; the README therefore does not call the primary income result statistically significant.

## Reproducibility and provenance

The analysis runs from committed compact source snapshots. [`data/source/source_manifest.csv`](../data/source/source_manifest.csv) records source URLs, retrieval time, upstream download hashes, compact-artifact hashes, and variable notes. This separates exact portfolio reproduction from an intentional refresh of mutable public endpoints.

`scripts/download_data.py` refreshes public inputs. `scripts/run_analysis.py` rebuilds the processed dataset and statistical tables. `scripts/render_dashboard.py` regenerates the SVG dashboard. Tests verify source shape, rate reconciliation, the coverage rule, exact output reproduction, and headline claims.

## Limitations

- Cross-sectional association cannot establish direction, mechanism, or causation.
- UCR data are voluntarily submitted; a coverage floor does not guarantee representative reporting.
- Summing monthly CDE rates preserves the endpoint's participating-population denominator but does not create an FBI national estimate for nonreporting agencies.
- ACS values are estimates with sampling error; margins of error are not incorporated into the regression.
- Fifty states provide a small sample, and the primary model uses 43.
- State averages conceal within-state variation and must not be applied to individuals (ecological fallacy).
- Many plausible confounders are omitted, including age structure, urbanization, inequality, policing, incarceration, and regional conditions.
- State legal definitions and reporting practices can differ even under UCR standards.
