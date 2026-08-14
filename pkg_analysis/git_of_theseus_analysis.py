import ubelt as ub


nodes = [p.strip() for p in """
utool
ibeis
vtool_ibeis
dtool_ibeis
plottool_ibeis
guitool_ibeis
pyhesaff
pyflann_ibeis
graphid

hotspotter

xdev
xinspect
xdoctest

mkinit
git_well
ubelt
xcookie
mathutf
#dotfiles
vimtk
timerit
progiter

geowatch

kwarray
kwcoco
kwcoco_dataloader
kwimage
kwimage_ext
kwplot
kwgis
kwutil

simple_dvc
scriptconfig
cmd_queue
ndsampler
delayed_image

liberator
torch_liberator

netharn
bioharn

shitspotter

pypogo
sm64-random-assets

line_profiler
networkx_algo_common_subtree

""".strip().split(chr(10)) if p.strip()]
nodes = [n for n in nodes if not n.startswith('#')]


def main():
    import cmd_queue
    queue = cmd_queue.Queue.create(backend='tmux', size=4)
    fpaths = []
    for pkgname in nodes:
        dpath = ub.Path(f'$HOME/code/{pkgname}').expand()
        fpaths.append(dpath / 'git-of-theseus/cohorts-stack.png')
        run_cmd = ub.codeblock(
            '''
            git-of-theseus-analyze . \
                --interval "86400" \
                --procs 4 \
                --ignore-whitespace \
                --ignore 'dev/**' \
                --ignore '.gitlab*' \
                --ignore '.github/**' \
                --outdir 'git-of-theseus'
            ''')
        plot_cmd = 'git-of-theseus-stack-plot ./git-of-theseus/cohorts.json --outfile ./git-of-theseus/cohorts-stack.png'
        run_job = queue.submit(run_cmd, name=f'analyze-{pkgname}', cwd=dpath)
        queue.submit(plot_cmd, depends=run_job, name=f'plot-{pkgname}', cwd=dpath)
    queue.print_graph()
    queue.print_commands()
    queue.run()

    import kwimage
    tostack = []
    for fpath in fpaths:
        imdata = kwimage.imread(fpath)
        name = fpath.parent.parent.name
        canvas = kwimage.draw_header_text(imdata, name)

        x, y = kwimage.Box.from_dsize(canvas.shape[0:2][::-1]).boxes.xy_center[0]
        canvas = kwimage.draw_text_on_image(
            imdata, name, org=(x, y), halign='center', valign='center',
            border=10, fontScale=5, thickness=10)
        tostack.append(canvas)
    big_graph = kwimage.stack_images_grid(tostack)
    fpath = 'multirepo-git-of-theseus.png'
    kwimage.imwrite(fpath, big_graph)
    # import kwplot
    # kwplot.autompl()
    # kwplot.imshow(big_graph)


if __name__ == '__main__':
    """
    CommandLine:
        python ~/misc/pkg_analysis/git_of_theseus_analysis.py
    """
    main()
