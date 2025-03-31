from typing import List
import polars as pl

def get_column_data(file_paths: List[str]) -> List[str]:
    dataframes = []
    
    for file in file_paths:
        try:
            df = pl.read_excel(file, columns=["Permalink"])
            dataframes.append(df)
        except FileNotFoundError:
            print(f"Error: File not found - {file}")
        except KeyError:
            print(f"Error: Column 'Permalink' not found in {file}")

    if not dataframes:
        return []

    # Combine the DataFrames
    combined_df = pl.concat(dataframes)
    
    # Extract the "Permalink" column as a flat list
    return combined_df["Permalink"].to_list()
