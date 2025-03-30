from typing import List
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

def read_file(file_path: str) -> pd.DataFrame:
    return pd.read_excel(file_path, usecols=["Permalink"])

def get_column_data(file_paths: List[str]) -> List[str]:
    try:
        with ThreadPoolExecutor() as executor:
            dataframes = list(executor.map(read_file, file_paths))
        
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # Extract the column as a list
        combined_data_list = combined_df["Permalink"].tolist()
        return combined_data_list
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return []
    except KeyError as e:
        print(f"Error: Column not found - {e}")
        return []







