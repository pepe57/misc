import numpy as np
import rich
import pandas as pd
ladder_length = np.array([22, 26])

ladder_df = pd.DataFrame([
    {'length_feet': 18 + 10 / 12},
    {'length_feet': 22},
    {'length_feet': 26},
])
# We only step up so high on the ladder
ladder_df['step_height'] = ladder_df['length_feet'] - 3

# for on the side of the house / in an a-frame position
angles = np.deg2rad(np.array([75, 60]))

angle_df = pd.DataFrame([
    {'angle_degrees': 75, 'position': 'lean'},
    {'angle_degrees': 60, 'position': 'a-frame'},
])
angle_df['angle'] = np.deg2rad(angle_df['angle_degrees'])

net_height = np.sin(angle_df['angle']) * ladder_length

person_reach = 7  # I can reach about 7 feet from where I'm standing

results = []
for _, angle_row in angle_df.iterrows():
    new = ladder_df.copy()
    new['position'] = angle_row['position']
    new['angle'] = angle_row['angle']
    new['angle_degrees'] = angle_row['angle_degrees']
    new['net_height'] = ladder_df['length_feet'] * np.sin(angle_row['angle'])
    new['net_step_height'] = ladder_df['step_height'] * np.sin(angle_row['angle'])
    new['net_reach'] = new['net_step_height'] + person_reach
    results.append(new)

final = pd.concat(results).reset_index(drop=True)
rich.print(final)
