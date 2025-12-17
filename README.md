# US Crime & Socioeconomic Analysis

This project analyzes the relationship between crime rates and key socioeconomic factors across U.S. states, including median income and unemployment rate.

## Tools & Methods
- Python (Pandas, NumPy, Statsmodels, Matplotlib, Seaborn)
- Data cleaning, aggregation, and regression analysis
- Tableau for interactive visualization

## Key Findings
- Higher unemployment rates are positively associated with higher crime rates.
- Median income shows a statistically significant negative relationship with crime.
- Results were validated using OLS regression (p < 0.05).

## Why This Project Matters

Understanding the relationship between economic conditions and crime is crucial for informed policymaking and effective public safety planning.

In this project, I analyzed U.S. state-level data to examine the relationship between violent crime rates and key socioeconomic indicators, including median household income and unemployment rates. Using Python for data cleaning, exploratory analysis, and ordinary least squares (OLS) regression, I found a statistically significant negative relationship (p < 0.05) between median income and crime rates, indicating that states with higher median incomes tend to experience lower levels of violent crime. I also observed a positive and significant relationship between unemployment and crime rates.

To effectively communicate these findings, I created an interactive Tableau dashboard featuring a geographic crime map and a scatter plot with trend lines, which allows users to explore patterns across states and visually assess the relationships between income, unemployment, and crime.

## Visualization
Interactive Tableau dashboard:
🔗 https://public.tableau.com/app/profile/masar.salim/viz/USCrime_17659805895990/CrimeIncomeandUnemploymentAcrossU_S_States

## Files
- `crime_analysis.ipynb` – Data cleaning, analysis, and regression
- `final_dashboard_data.csv` – Cleaned dataset used for Tableau
