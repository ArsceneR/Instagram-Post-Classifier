from typing import List
import pandas as pd

def get_column_data(file_paths: List[str]) -> List[str]:
    try:
        # Read the Excel files
        dataframes = [pd.read_excel(file_path) for file_path in file_paths]
        
        combined_df = pd.concat(dataframes, ignore_index=True)
        combined_data_list = combined_df["Permalink"].tolist()
        

        # Convert the column data to a list
        return combined_data_list
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return []
    except KeyError as e:
        print(f"Error: Column not found - {e}")
        return []






