import timeit

# Measure the old version
old_duration = timeit.timeit(
    stmt="get_column_data(file_paths)",
    setup="from read_data import get_column_data; file_paths = ['./ConversationStreamDistribution/ConversationStreamDistribution_3d42a086-f00d-490c-86c6-39c6b783c1b0_2.xlsx', './ConversationStreamDistribution/ConversationStreamDistribution_ac4cea66-b9fb-4b10-8023-d032dc646d1f_1.xlsx']",
    number=20
)

# Measure the new version
new_duration = timeit.timeit(
    stmt="get_column_data(file_paths)",
    setup="from new_read_data import get_column_data; file_paths = ['./ConversationStreamDistribution/ConversationStreamDistribution_3d42a086-f00d-490c-86c6-39c6b783c1b0_2.xlsx', './ConversationStreamDistribution/ConversationStreamDistribution_ac4cea66-b9fb-4b10-8023-d032dc646d1f_1.xlsx']",
    number=20
)

# Print the results
print(f"Old Version Average Duration: {old_duration / 10:.4f} seconds")
print(f"New Version Average Duration: {new_duration / 10:.4f} seconds")