import ubelt as ub
import pandas as pd
import kwutil
import kwplot
sns = kwplot.sns
fpaths = list(ub.Path('~/misc/pkg_analysis/download_stats/').expand().glob('*bquxjob*.json'))
fpaths = list(ub.Path('~/misc/pkg_analysis/download_stats/daily').expand().glob('*.json'))


rows = []
for fpath in fpaths:
    rows += kwutil.Json.coerce(fpath)

for row in rows:
    row['num_downloads'] = int(row['num_downloads'])
    row['day'] = kwutil.datetime.coerce(row['day'])


# Remove any dups
unique_rows = list(ub.unique(rows, key=ub.hash_data))
daily = pd.DataFrame(unique_rows)

daily['month'] = daily['day'].dt.to_period('M').apply(lambda x: kwutil.datetime.coerce(str(x) + '-01'))
daily['week'] = daily['day'].dt.to_period('W').apply(lambda x: kwutil.datetime.coerce(x.start_time))
daily['year'] = daily['day'].dt.to_period('Y').apply(lambda x: kwutil.datetime.coerce(x.start_time))

yearly = daily.groupby(['package_name', 'year']).agg({'num_downloads': 'sum'}).reset_index()
weekly = daily.groupby(['package_name', 'week']).agg({'num_downloads': 'sum'}).reset_index()
monthly = daily.groupby(['package_name', 'month']).agg({'num_downloads': 'sum'}).reset_index()

is_popular = monthly.groupby(['package_name'])['num_downloads'].max() > 10_000
import kwarray
flags = kwarray.isect_flags(monthly['package_name'], is_popular[is_popular].index)
popular_monthly = monthly[flags]

if 0:
    ax = sns.lineplot(data=daily, x='day', y='num_downloads', hue='package_name')
    # ax.set_yscale('symlog')

    ax = sns.lineplot(data=yearly, x='year', y='num_downloads', hue='package_name')
    ax.set_yscale('log', base=10)

if 0:
    # from kwplot.util_seaborn import histplot_splity
    # histplot_splity(data=weekly, x='week')
    ax = sns.lineplot(data=weekly, x='week', y='num_downloads', hue='package_name')
    ax.set_yscale('log', base=10)

if 1:
    ax = sns.lineplot(data=popular_monthly, x='month', y='num_downloads', hue='package_name')
    # ax.set_yscale('linear')
    ax.set_yscale('log', base=10)
