import pytrms
import pandas as pd

m = pytrms.measure('C:/Data/', 'localhost')

m.start()

series = []
for row in m.iterrows():
    if row['Cycle'] > 10:
        break
    series.append(row)
    
df = pd.concat(series, axis='columns').T

