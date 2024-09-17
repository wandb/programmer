import pandas as pd
import sys

if len(sys.argv) < 2:
    print("Usage: python script.py <input_parquet_file>")
    sys.exit(1)

input_file = sys.argv[1]
output_file = input_file.rsplit(".", 1)[0] + ".csv"

# Read the Parquet file into a pandas DataFrame
df = pd.read_parquet(input_file)

# Write the DataFrame to a CSV file
df.to_csv(output_file, index=False)

print(f"Converted {input_file} to {output_file}")
