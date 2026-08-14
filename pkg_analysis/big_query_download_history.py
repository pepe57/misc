"""
References:
    https://cloud.google.com/blog/topics/developers-practitioners/analyzing-python-package-downloads-bigquery
    https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=pypi&page=dataset&project=nice-column-438000-v8
"""
import ubelt as ub


def query_package(pkgname):
    """
    pip install google-cloud-bigquery[opentelemetry] opentelemetry-exporter-gcp-trace

    """
    from google.cloud import bigquery

    client = bigquery.Client()

    num_months = 12 * 14
    pkgname = 'ubelt'
    text = ub.codeblock(
        f'''
        #standardSQL
        SELECT
          COUNT(*) AS num_downloads,
          DATE_TRUNC(DATE(timestamp), MONTH) AS `month`
        FROM `bigquery-public-data.pypi.file_downloads`
        WHERE
          file.project = '{pkgname}'
          -- Only query the last N months of history
          AND DATE(timestamp)
            BETWEEN DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL {num_months} MONTH), MONTH)
            AND CURRENT_DATE()
        GROUP BY `month`
        ORDER BY `month` DESC
        ''')
    print(text)

    num_months = 12 * 14
    package_names = [
        # 'ubelt',
        # 'xdoctest',
        # 'timerit',
        # 'kwcoco',
        # 'kwimage',
        # 'kwarray',
        # 'kwplot',
        # 'ndsampler',
        # 'geowatch',
        # 'mkinit',
        # 'scriptconfig',
        # 'xdev',
        'delayed-image',
        'cmd-queue',
        'git-well',
        'line-profiler',
        'liberator',
        'kwimage-ext',
        'netharn',
    ]

    # package_names = [p.strip() for p in """
    #     utool
    #     ibeis
    #     vtool-ibeis
    #     dtool-ibeis
    #     plottool-ibeis
    #     guitool-ibeis
    #     pyhesaff
    #     pyflann-ibeis
    #     graphid
    #     xdev
    #     xinspect
    #     xdoctest
    #     mkinit
    #     git-well
    #     ubelt
    #     timerit
    #     progiter
    #     geowatch
    #     kwarray
    #     kwcoco
    #     kwimage
    #     kwimage-ext
    #     kwplot
    #     kwgis
    #     kwutil
    #     simple-dvc
    #     scriptconfig
    #     cmd-queue
    #     ndsampler
    #     delayed-image
    #     liberator
    #     torch-liberator
    #     netharn
    #     line-profiler
    #     networkx-algo-common-subtree
    # """.strip().split(chr(10)) if p.strip()]

    # hotspotter
    # xcookie
    # mathutf
    # dotfiles
    # vimtk
    # bioharn
    # shitspotter
    # sm64-random-assets
    # pypogo

    project_query_text = ', '.join([f"'{p}'" for p in package_names])
    text = ub.codeblock(
        f'''
        #standardSQL
        SELECT
          file.project AS package_name,
          COUNT(*) AS num_downloads,
          DATE_TRUNC(DATE(timestamp), DAY) AS `day`
        FROM `bigquery-public-data.pypi.file_downloads`
        WHERE
          file.project IN ({project_query_text})  -- Replace with your package names
          AND DATE(timestamp)
            BETWEEN '2015-01-01'
            AND CURRENT_DATE()
        GROUP BY package_name, `day`
        ORDER BY `day` DESC, package_name
        ''')
    print(text)
