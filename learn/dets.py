"""
References:
    https://chatgpt.com/c/68390eaf-a1b4-8002-b901-540bb73c31f8
    https://www.reddit.com/r/mathmemes/comments/1kyluq1/i_hope_euler_would_be_proud/
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider


def plot_all_parallelograms(ax):
    """Plot the family of parallelograms and trace the determinant tip."""
    ax.set_aspect('equal')
    ax.set_xlim(-2, 2)
    ax.set_ylim(-2, 2)
    ax.set_title("All Parallelograms for θ ∈ [0, 2π]")
    ax.set_xlabel("Re")
    ax.set_ylabel("Im")

    det_tips = []

    for theta in np.linspace(0, 2 * np.pi, 30):
        v1 = np.array([np.cos(theta), 1])
        v2 = np.array([-np.sin(theta), -1])

        origin = np.array([0, 0])
        points = np.array([
            origin,
            v1,
            v1 + v2,
            v2,
            origin
        ])
        ax.plot(points[:, 0], points[:, 1], color='lightblue', alpha=0.3)

        det = -np.cos(theta) + 1j * np.sin(theta)
        det_tips.append([det.real, det.imag])

    det_tips = np.array(det_tips)
    ax.plot(det_tips[:, 0], det_tips[:, 1], color='darkred', label='det = -cos(θ) + i sin(θ)')
    ax.legend()
    ax.grid(True)


def plot_single_parallelogram(ax, theta):
    """Draw the parallelogram and determinant vector for a given theta."""
    ax.clear()
    plot_all_parallelograms(ax)

    v1 = np.array([np.cos(theta), 1])
    v2 = np.array([-np.sin(theta), -1])
    det = -np.cos(theta) + 1j * np.sin(theta)

    origin = np.array([0, 0])
    points = np.array([
        origin,
        v1,
        v1 + v2,
        v2,
        origin
    ])
    ax.plot(points[:, 0], points[:, 1], color='cornflowerblue', alpha=0.8, linewidth=2)
    ax.arrow(0, 0, v1[0], v1[1], head_width=0.1, color='blue', length_includes_head=True, label='v1')
    ax.arrow(0, 0, v2[0], v2[1], head_width=0.1, color='green', length_includes_head=True, label='v2')
    ax.arrow(0, 0, det.real, det.imag, head_width=0.1, linestyle='--',
             color='darkred', length_includes_head=True, label='det')

    ax.set_aspect('equal')
    ax.set_xlim(-2, 2)
    ax.set_ylim(-2, 2)
    ax.set_title(f'θ = {theta:.2f} rad')
    ax.grid(True)
    ax.legend()


def interactive_slider_plot():
    fig, ax = plt.subplots(figsize=(6, 6))
    plt.subplots_adjust(bottom=0.25)

    # Initial plot
    initial_theta = 0.0
    plot_single_parallelogram(ax, initial_theta)

    # Add slider
    ax_slider = plt.axes([0.2, 0.1, 0.6, 0.03])
    theta_slider = Slider(ax_slider, 'θ (radians)', 0, 2 * np.pi, valinit=initial_theta)

    def update(val):
        theta = theta_slider.val
        plot_single_parallelogram(ax, theta)
        fig.canvas.draw_idle()

    theta_slider.on_changed(update)
    plt.show()


def main():
    # Interactive visualization
    interactive_slider_plot()


if __name__ == '__main__':
    main()
