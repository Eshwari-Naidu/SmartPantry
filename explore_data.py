import pandas as pd
import json

df = pd.read_csv('archive_extracted/epi_r.csv')
print('CSV Columns (first 20):', df.columns.tolist()[:20])
print('CSV Head:\n', df[['title', 'calories', 'protein', 'fat', 'sodium']].head())

with open('archive_extracted/full_format_recipes.json', 'r') as f:
    data = json.load(f)

print('\nJSON keys for first recipe:', data[0].keys())
print('JSON example:\n', {k: data[0][k] for k in ['title', 'calories', 'protein', 'fat'] if k in data[0]})
