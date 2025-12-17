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

Understanding the relationship between economic conditions and crime is essential for informed public policy and social planning.

In this project, I analyzed 3,000+ U.S. counties to examine how key socioeconomic factors—specifically median income and unemployment rates—relate to violent crime rates. Using Python for data extraction, cleaning, and OLS regression analysis, I found a statistically significant negative relationship (p < 0.05) between median income and crime rates, indicating that higher-income areas tend to experience lower levels of violent crime.

To make these insights accessible and interactive, I built a Tableau dashboard that allows users to explore crime patterns geographically and analyze income–crime relationships at the state level. This combination of statistical analysis and visualization demonstrates how data-driven insights can support evidence-based decision-making in economics and public policy.

## Visualization
Interactive Tableau dashboard:
🔗 https://public.tableau.com/app/profile/masar.salim/viz/USCrime_17659805895990/CrimeIncomeandUnemploymentAcrossU_S_States

## Files
- `crime_analysis.ipynb` – Data cleaning, analysis, and regression
- `final_dashboard_data.csv` – Cleaned dataset used for Tableau
